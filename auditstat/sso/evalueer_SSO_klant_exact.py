import math

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import fftconvolve
from scipy.special import betaln, gammaln, nbdtr

from auditstat.geldsteek_gestratificeerd.utils import foutloze_posten_equivalent
from auditstat.sso.compound_postwaarden import (
    kansmassa_compound,
    schat_rekentijd_compound,
)

# Standaard aantal cellen van het euro-rooster waarop de strata worden
# gecombineerd. De roosterfout is positief (conservatief) en bij 20.000
# cellen in de gemeten voorbeelden hooguit ongeveer 0,2% van de grens.
STANDAARD_GRANULARITEIT = 20_000

# Grootste N_klant waarvoor de kansmassa's per post in het geheugen worden
# opgebouwd (een array van N_klant + 1 getallen per type post).
MAX_N_KLANT = 20_000_000


def _cdf_aantal_fouten(model, n, k, N_klant):
    """Geeft een functie ``F(j) = P(X <= j)`` voor het aantal foute posten
    ``X`` bij de klant: Beta-Binomiaal(N_klant, k+1, n-k+1) (binomiaal) resp.
    Negatief-Binomiaal(k+1, n/(n+N_klant)) (poisson).

    De Beta-Binomiaal wordt via de kansmassa's (``gammaln``/``betaln``) en
    een cumulatieve som berekend; ``scipy.stats.betabinom.cdf`` rekent per
    element en is voor grote ``N_klant`` meer dan honderd keer trager.
    """
    a, b = k + 1, n - k + 1
    if model == "binomiaal":
        j = np.arange(0, N_klant + 1)
        log_pmf = (
            gammaln(N_klant + 1)
            - gammaln(j + 1)
            - gammaln(N_klant - j + 1)
            + betaln(j + a, N_klant - j + b)
            - betaln(a, b)
        )
        cdf = np.minimum(np.cumsum(np.exp(log_pmf)), 1.0)
        return lambda x: cdf[np.asarray(x, dtype=np.int64)]
    q = n / (n + N_klant)
    return lambda x: nbdtr(np.asarray(x), k + 1, q)


def _controleer_post(post):
    naam = post.get("naam")
    if not naam or not str(naam).strip():
        raise ValueError("Elk type post moet een niet-lege 'naam' hebben.")
    ontbrekend = [v for v in ("n", "k", "N_klant", "waarde_laag") if v not in post]
    if ontbrekend:
        raise ValueError(
            f"Type post '{naam}' mist verplicht(e) veld(en): {', '.join(ontbrekend)}."
        )
    for veld in ("ihr", "ibr", "car"):
        if post.get(veld, "H") not in ("H", "M", "L"):
            raise ValueError(
                f"Type post '{naam}': veld '{veld}' moet 'H', 'M' of 'L' zijn."
            )
    m = post.get("materialiteit", 0.01)
    if not (0 < m < 1):
        raise ValueError(
            f"Type post '{naam}': materialiteit moet een fractie tussen 0 en 1 zijn."
        )
    for veld in ("waarde_hoog", "fout_hoog"):
        if post.get(veld, 0) not in (0, 0.0, None):
            raise ValueError(
                f"Type post '{naam}': veld '{veld}' wordt door de exacte "
                "methode niet ondersteund (alleen het laagstratum)."
            )
    n, k, N, w = post["n"], post["k"], post["N_klant"], post["waarde_laag"]
    if not (n > 0):
        raise ValueError(f"Type post '{naam}': n moet groter dan 0 zijn.")
    if not (0 <= k <= n):
        raise ValueError(f"Type post '{naam}': k moet tussen 0 en n liggen.")
    if int(N) != N or N < 1:
        raise ValueError(
            f"Type post '{naam}': N_klant moet een geheel getal >= 1 zijn."
        )
    if N > MAX_N_KLANT:
        raise ValueError(
            f"Type post '{naam}': N_klant ({N:,.0f}) is groter dan het "
            f"toegestane maximum ({MAX_N_KLANT:,})."
        )
    if not (w > 0):
        raise ValueError(f"Type post '{naam}': waarde_laag moet groter dan 0 zijn.")
    cv = post.get("cv", 0.0)
    if cv is None or not cv >= 0 or cv == float("inf"):
        raise ValueError(f"Type post '{naam}': cv moet een eindig getal >= 0 zijn.")
    if post.get("postwaarden") is not None:
        waarden = np.asarray(post["postwaarden"], dtype=float)
        if waarden.ndim != 1 or len(waarden) == 0:
            raise ValueError(
                f"Type post '{naam}': postwaarden moet een niet-lege lijst zijn."
            )
        if not (np.all(np.isfinite(waarden)) and np.all(waarden > 0)):
            raise ValueError(
                f"Type post '{naam}': alle postwaarden moeten positief en eindig zijn."
            )


def _cv_van_post(post):
    """De variatiecoëfficiënt waarmee voor deze post gerekend is (0 = gelijke posten)."""
    if post.get("postwaarden") is not None:
        waarden = np.asarray(post["postwaarden"], dtype=float)
        return float(waarden.std() / waarden.mean())
    return float(post.get("cv", 0.0))


def _extra_foutloze_posten(post):
    return float(
        foutloze_posten_equivalent(
            post.get("ihr", "H"),
            post.get("ibr", "H"),
            post.get("car", "H"),
            post.get("materialiteit", 0.01),
        )
    )


def evalueer_SSO_klant_exact(
    post_typen,
    model="binomiaal",
    zekerheid=0.95,
    granulariteit=STANDAARD_GRANULARITEIT,
    voortgang=None,
):
    """
    Evalueert een klant gestratificeerd (één stratum per type post) op basis
    van SSO-steekproeven per type post, zonder de Beta/Gamma-benadering van
    ``moment_match_SSO``.

    Per type post is het aantal foute posten bij de klant exact
    Beta-Binomiaal (binomiaal) resp. Negatief-Binomiaal (poisson), met de
    SSO-steekproef ``(n, k)`` en ``N_klant`` posten bij de klant (dezelfde
    verdeling als ``moment_match_SSO._max_fout_exact``). De euro-fout van de
    klant is ``som_h waarde_laag_h * X_h / N_klant_h``; de typen posten
    hebben onafhankelijke steekproeven, dus de verdeling daarvan is de
    convolutie van de verdelingen per type post. Die convolutie gebeurt via
    FFT op een euro-rooster van ``granulariteit`` cellen over de totale
    ``waarde_laag``.

    Modelaannames (gelijk aan ``moment_match_SSO``): vlakke prior, elke post
    volledig goed of volledig fout (Var(X) <= p(1-p), dus de maximaal
    conservatieve spreiding), onafhankelijke typen posten.

    Roosterfout: de kansmassa van een post wordt naar boven afgerond op een
    roostercel; de grens is daardoor hooguit ongeveer ``1/granulariteit`` per
    stratum te hoog, nooit te laag. Bij het poisson-model kan de foutfractie
    van een type post boven 1 uitkomen; die staart komt in de laatste cel
    (100% fout voor dat type post) terecht.

    HARo-risicocorrectie: ``ihr``, ``ibr``, ``car`` en ``materialiteit``
    (optioneel, standaard H/H/H en 0,01) horen bij de eerste trap, de
    SSO-steekproef. Het aantal foutloze posten dat daarmee overeenkomt
    (``foutloze_posten_equivalent``) wordt bij de SSO-``n`` opgeteld voordat
    de Beta-Binomiaal/Negatief-Binomiaal wordt bepaald (``n_calc = n +
    extra``; ``k`` blijft). De klantsteekproef zelf (``N_klant``) kent geen
    risicocorrectie.

    Variabele postgroottes (niveau 2 en 3 van de theorie): een type post kan
    een ``cv`` (variatiecoëfficiënt; ``Z`` Gamma-verdeeld, niveau 2) of
    ``postwaarden`` (rij van postbedragen; empirische verdeling, herschaald
    naar gemiddelde ``waarde_laag / N_klant``, niveau 3) meekrijgen. Dan is de
    euro-fout de som van ``K`` postwaarden; zie ``compound_postwaarden``.
    Zonder beide (of ``cv = 0``) is het het eerdere model met gelijke posten.

    Beperkingen: alleen het laagstratum (``waarde_hoog``/``fout_hoog`` moeten
    0 zijn). Het geheugengebruik schaalt met ``N_klant`` (maximaal
    ``MAX_N_KLANT``).

    Parameters
    ----------
    post_typen : list[dict]
        Eén dict per type post, met ``naam``, ``n``, ``k``, ``N_klant`` (geheel)
        en ``waarde_laag`` (totale geldwaarde van dit type post bij de klant);
        optioneel ``cv`` of ``postwaarden`` (zie hierboven).
    model : {"binomiaal", "poisson"}
    zekerheid : float
        Tussen 0 en 1.
    granulariteit : int
        Aantal cellen van het euro-rooster.
    voortgang : callable, optional
        ``voortgang(fractie)`` (0 tot 1), regelmatig aangeroepen tijdens de
        berekening, voor een voortgangsbalk.

    Returns
    -------
    dict
        Zelfde sleutels als ``evalueer_geldsteek_gestratificeerd`` voor wat ``plot_kanskromme``
        en de samenvattingen gebruiken (``kanskromme``, ``populatie_totaal``,
        ``max_fout_convolutie`` en ``..._geld``, ``mw_``/``min_``/
        ``mediaan_``/``gemiddelde_fout_convolutie`` en ``..._geld``,
        ``steekproeven``, ``invoer``). ``steekproeven`` bevat ``naam``,
        ``waarde_laag``, ``n_laag`` (= SSO-``n``), ``k_laag`` (= SSO-``k``),
        ``N_klant``, ``waarde_hoog``, ``fout_hoog`` en ``waarde_populatie``.
        De kanskromme is de kansmassa per cel, omgerekend naar een dichtheid en
        voor de weergave licht glad gemaakt; de grenzen komen uit de ongladde
        massa.
    """
    if model not in ("binomiaal", "poisson"):
        raise ValueError(f"model moet 'binomiaal' of 'poisson' zijn, kreeg {model!r}.")
    if not (0 < zekerheid < 1):
        raise ValueError("zekerheid moet strikt tussen 0 en 1 liggen.")
    if int(granulariteit) != granulariteit or granulariteit < 100:
        raise ValueError("granulariteit moet een geheel getal >= 100 zijn.")
    if not post_typen:
        raise ValueError("Geef tenminste 1 type post (stratum) mee.")
    namen = [p.get("naam") for p in post_typen]
    for post in post_typen:
        _controleer_post(post)
    if len(set(namen)) != len(namen):
        raise ValueError("Namen van typen posten moeten uniek zijn.")

    totaal = float(sum(p["waarde_laag"] for p in post_typen))
    dx = totaal / granulariteit

    kansmassa = np.array([1.0])
    for index, post in enumerate(post_typen):

        def _deel(f, index=index):
            if voortgang is not None:
                voortgang((index + f) / len(post_typen))

        n, k, N, w = post["n"], post["k"], int(post["N_klant"]), post["waarde_laag"]
        n_calc = n + _extra_foutloze_posten(post)
        if post.get("postwaarden") is not None:
            massa = kansmassa_compound(
                model,
                n_calc,
                k,
                N,
                w,
                np.asarray(post["postwaarden"]),
                dx,
                voortgang=_deel,
            )
        elif post.get("cv", 0.0) > 0:
            massa = kansmassa_compound(
                model,
                n_calc,
                k,
                N,
                w,
                ("gamma", float(post["cv"])),
                dx,
                voortgang=_deel,
            )
        else:
            cdf = _cdf_aantal_fouten(model, n_calc, k, N)
            cellen = np.arange(0, math.ceil(w / dx) + 1)
            # Cel c bevat de waarden met (j * w / N) in ((c-1)*dx, c*dx].
            j = np.floor(cellen * dx * N / w + 1e-9)
            if model == "binomiaal":
                j = np.minimum(j, N)
            kum = cdf(j)
            massa = np.diff(np.concatenate([[0.0], kum]))
            massa[-1] += 1.0 - kum[-1]
        kansmassa = fftconvolve(kansmassa, massa)
        _deel(1.0)

    kansmassa = np.clip(kansmassa, 0.0, None)
    kansmassa /= kansmassa.sum()
    kum = np.cumsum(kansmassa)
    x = np.arange(len(kansmassa)) * dx / totaal  # foutfractie van de populatie

    def kwantiel(q):
        i = min(int(np.searchsorted(kum, q - 1e-12)), len(x) - 1)
        return float(x[i])

    max_fout = kwantiel(zekerheid)
    min_fout = kwantiel(1 - zekerheid)
    mediaan = kwantiel(0.5)
    gemiddelde = float(np.sum(x * kansmassa))
    modus = float(x[int(np.argmax(kansmassa))])
    # Alleen de getekende kromme wordt glad gemaakt (kern ~ de grootste stap
    # waarde_laag/N_klant); anders geeft een stap die niet op het rooster past
    # een kameffect. Alle kwantielen en kengetallen gebruiken de ongladde massa.
    grootste_stap = max(p["waarde_laag"] / int(p["N_klant"]) for p in post_typen)
    sigma = 0.5 * grootste_stap / dx
    glad = gaussian_filter1d(kansmassa, sigma) if sigma >= 0.5 else kansmassa
    dichtheid = glad / glad.sum() / (dx / totaal)

    extra = [_extra_foutloze_posten(p) for p in post_typen]
    steekproeven = pd.DataFrame({
        "naam": namen,
        "waarde_laag": [float(p["waarde_laag"]) for p in post_typen],
        "n_laag": [p["n"] for p in post_typen],
        "k_laag": [p["k"] for p in post_typen],
        "N_klant": [int(p["N_klant"]) for p in post_typen],
        "cv": [_cv_van_post(p) for p in post_typen],
        "extra_foutloze_posten": extra,
        "waarde_hoog": 0.0,
        "fout_hoog": 0.0,
    })
    steekproeven["waarde_populatie"] = steekproeven["waarde_laag"]

    return {
        "kanskromme": {"x": x, "y": dichtheid},
        "populatie_totaal": totaal,
        "modus_fout_convolutie": modus,
        "modus_fout_convolutie_geld": modus * totaal,
        "mediaan_fout_convolutie": mediaan,
        "mediaan_fout_convolutie_geld": mediaan * totaal,
        "gemiddelde_fout_convolutie": gemiddelde,
        "gemiddelde_fout_convolutie_geld": gemiddelde * totaal,
        "mw_fout_convolutie": modus,
        "mw_fout_convolutie_geld": modus * totaal,
        "min_fout_convolutie": min_fout,
        "min_fout_convolutie_geld": min_fout * totaal,
        "max_fout_convolutie": max_fout,
        "max_fout_convolutie_geld": max_fout * totaal,
        "vergelijk_met": None,
        "steekproeven": steekproeven,
        "invoer": {
            "model": model,
            "zekerheid": zekerheid,
            "methode": "exact (FFT-rooster)",
            "granulariteit": int(granulariteit),
            "start": 0,
            "vergelijk": False,
        },
    }


def schat_rekentijd_exact(
    post_typen, model="binomiaal", granulariteit=STANDAARD_GRANULARITEIT
):
    """Indicatie (seconden) van de rekentijd van ``evalueer_SSO_klant_exact``.

    Alleen typen posten met ``postwaarden`` of ``cv > 0`` kosten merkbaar
    tijd. Een orde-van-grootte-schatting; geeft ``None`` als de berekening
    om een andere reden niet kan (de berekening zelf geeft dan de
    foutmelding).
    """
    try:
        totaal = float(sum(p["waarde_laag"] for p in post_typen))
        dx = totaal / granulariteit
        seconden = 0.0
        for post in post_typen:
            n_calc = post["n"] + _extra_foutloze_posten(post)
            if post.get("postwaarden") is not None:
                z = np.asarray(post["postwaarden"])
            elif post.get("cv", 0.0) > 0:
                z = ("gamma", float(post["cv"]))
            else:
                continue
            seconden += schat_rekentijd_compound(
                model,
                n_calc,
                post["k"],
                int(post["N_klant"]),
                post["waarde_laag"],
                z,
                dx,
            )
        return seconden
    except (ValueError, KeyError, TypeError):
        return None
