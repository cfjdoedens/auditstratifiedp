"""Evaluatie van één steekproef met de binomiale, hypergeometrische, Poisson- of normale verdeling.

Python-omzetting van de SAS-macro ``%eval_distribution`` (Crist-Jan Doedens,
2010-2020). Uit een aselecte steekproef van ``n`` posten met ``k`` foute posten
wordt de kansdichtheid van het foutpercentage ``p`` berekend (vlakke prior),
met daarbij het minimum, het maximum (bij een eenzijdige zekerheid) en de meest
waarschijnlijke fout.

Verschillen met de SAS-macro:

- De band-kans en de kans boven de norm gebruiken bij de hypergeometrische
  verdeling het juiste roostergewicht ``1/(m+1)`` (SAS gebruikte daar ``1/m``).
- De meest waarschijnlijke fout kiest de reeks roosterpunten met (vrijwel)
  maximale dichtheid (relatieve tolerantie 1e-12) in plaats van exacte
  gelijkheid, zodat afrondingsruis geen invloed heeft.
- Resultaten komen terug als dict plus ``pandas.DataFrame``; de plot is een
  matplotlib-figuur (zie ``plot_eval_distribution``).
"""

import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binom, hypergeom, poisson
from scipy.stats import norm as normaal_verdeling

from auditstat._formatting import nl_getal, nl_getal_variabel

_VERDELINGEN = {
    "binomiaal": "binomiaal",
    "b": "binomiaal",
    "poisson": "poisson",
    "p": "poisson",
    "normaal": "normaal",
    "n": "normaal",
    "hypergeometrisch": "hypergeometrisch",
    "h": "hypergeometrisch",
}

# Vanaf dit aantal roosterpunten wordt het gekleurde deel als vlak getekend.
_MAX_PUNTEN_VOOR_VLAK = 200

# Kleuren: gekozen deel onder de kromme (donker) en de rest (licht), en de
# verticale lijnen.
_KLEUR_BINNEN = "blue"
_KLEUR_BUITEN = "lightblue"
_KLEUR_MIN = "green"
_KLEUR_MEEST_WAARSCHIJNLIJK = "goldenrod"
_KLEUR_MAX = "darkorange"
_KLEUR_NORM = "red"

_GEKLEURD_DEEL = (
    "geen",
    "onder_pmax",
    "boven_pmin",
    "tussen_pmin_pmax",
    "band",
    "boven_norm",
)


def _signifdig(waarde: float, cijfers: int) -> float:
    """Rond af op ``cijfers`` significante cijfers, maar verminder alleen de
    precisie van cijfers achter de komma (zoals ``signifdig`` in de SAS-code).

    Voorbeelden: 0,0567 -> 0,057 (2 cijfers); 4,567 -> 4,6; 234,567 -> 235;
    33234,567 -> 33235.
    """
    if waarde == 0:
        return 0.0
    exponent = math.floor(math.log10(abs(waarde)))
    decimalen = max(0, (cijfers - 1) - exponent)
    return round(waarde, decimalen)


def eval_distribution(
    n: int,
    k: int,
    verdeling: str = "hypergeometrisch",
    massa: int = 0,
    zekerheid: float = 0.95,
    norm: float = 0.0,
    m: int = 10000,
    band_links: float = 0.0,
    band_rechts: float = 1.0,
) -> dict:
    """Bereken de kansdichtheid van het foutpercentage uit een steekproef.

    Parameters
    ----------
    n:
        Aantal getrokken posten (>= 0).
    k:
        Aantal foute posten daarin (0 <= k <= n).
    verdeling:
        ``"binomiaal"`` (``"b"``), ``"hypergeometrisch"`` (``"h"``) of
        ``"poisson"`` (``"p"``) of ``"normaal"`` (``"n"``). Normaal
        benadert de verdeling van de foutfractie door een normale verdeling met
        gemiddelde ``f' = k/n`` en standaardafwijking
        ``sqrt(f' (1 - f') / n)`` (Wald): de grenzen zijn ``f' -/+ z * s`` met
        ``z`` bij de eenzijdige ``zekerheid``; dit vraagt ``0 < k < n``, en het
        rooster loopt over [0, 1] (afgekapt). Poisson modelleert het aantal fouten als
        Poisson(``n`` · ``p``); het rooster loopt net als bij binomiaal over
        [0, 1], dus een foutfractie boven 1 is uitgesloten.
    massa:
        Aantal posten in de populatie, ``N`` (>= n bij de hypergeometrische
        verdeling). Bij hypergeometrisch is ``0`` (niet opgegeven) gelijk aan
        ``3 * n`` (``100`` als ``n = 0``); het aantal roosterpunten is ``massa + 1`` en ``m`` wordt
        genegeerd. Bij binomiaal, Poisson en normaal bestaat geen massa (alleen informatief). ``massa_aangenomen`` in het
        resultaat geeft aan of de standaardwaarde ``3 * n`` is gebruikt.
    zekerheid:
        Eenzijdige zekerheid voor minimum en maximum, in [0,5; 1].
    norm:
        Normfout als fractie in [0, 1]; ``0`` betekent geen norm.
    m:
        Aantal roosterpunten bij binomiaal, Poisson en normaal (>= 2); punten liggen op
        ``(stap - 0,5)/m``.
    band_links, band_rechts:
        Grenzen (fracties) van het interval waarvoor de kans wordt bepaald.

    Returns
    -------
    dict met onder andere ``tabel`` (DataFrame met ``p``, ``c_raw``, ``c``,
    ``cc``: onbewerkte kans, kansdichtheid en cumulatieve kans), ``pmin``,
    ``pmax``, ``phigh``, ``kans_boven_norm``, ``band_kans`` en de invoer.
    """
    # --- Invoercontrole ---
    if verdeling not in _VERDELINGEN:
        raise ValueError(
            f"verdeling moet een van {sorted(set(_VERDELINGEN))} zijn, kreeg {verdeling!r}."
        )
    verdeling = _VERDELINGEN[verdeling]
    for naam, waarde in (("n", n), ("k", k), ("massa", massa), ("m", m)):
        if isinstance(waarde, bool) or int(waarde) != waarde:
            raise ValueError(f"{naam} moet een geheel getal zijn, kreeg {waarde!r}.")
    n, k, massa, m = int(n), int(k), int(massa), int(m)
    if n < 0:
        raise ValueError("n moet >= 0 zijn.")
    if not 0 <= k <= n:
        raise ValueError("k moet voldoen aan 0 <= k <= n.")
    if massa < 0:
        raise ValueError("massa moet >= 0 zijn.")
    if not 0.5 <= zekerheid <= 1:
        raise ValueError("zekerheid moet in [0,5; 1] liggen.")
    if not 0 <= norm <= 1:
        raise ValueError("norm moet in [0, 1] liggen.")
    if not (0 <= band_links <= 1 and 0 <= band_rechts <= 1):
        raise ValueError("band_links en band_rechts moeten in [0, 1] liggen.")
    if not band_links < band_rechts:
        raise ValueError("band_links moet kleiner zijn dan band_rechts.")

    # --- Roosterpunten en onbewerkte kansen ---
    massa_aangenomen = False
    if verdeling in ("binomiaal", "poisson", "normaal"):
        if m < 2:
            raise ValueError("m moet >= 2 zijn.")
        p = (np.arange(1, m + 1) - 0.5) / m
        if verdeling == "binomiaal":
            c_raw = binom.pmf(k, n, p)
        elif verdeling == "poisson":
            c_raw = poisson.pmf(k, n * p)
        else:
            if not 0 < k < n:
                raise ValueError(
                    "De normale benadering vraagt 0 < k < n (bij k = 0 of k = n "
                    "is de standaardafwijking 0)."
                )
            f_gevonden = k / n
            c_raw = normaal_verdeling.pdf(
                p, loc=f_gevonden, scale=math.sqrt(f_gevonden * (1 - f_gevonden) / n)
            )
        aantal_stukjes = m
    else:
        if massa == 0:
            # Geen massa opgegeven: standaard 3 maal n, en 100 als n = 0.
            massa = 3 * n if n > 0 else 100
            massa_aangenomen = True
        if massa <= 0:
            raise ValueError("massa moet > 0 zijn bij de hypergeometrische verdeling.")
        if n > massa:
            raise ValueError("n mag niet groter zijn dan massa.")
        m = massa
        stap = np.arange(0, m + 1)
        p = stap / m
        # scipy: hypergeom.pmf(k, populatie, fouten in populatie, getrokken)
        c_raw = hypergeom.pmf(k, massa, stap, n)
        aantal_stukjes = m + 1

    # --- Normalisatie: oppervlak onder de kromme wordt 1 ---
    stukje = c_raw / aantal_stukjes
    totaal = math.fsum(stukje)
    c = c_raw / totaal
    cc = np.cumsum(stukje / totaal)

    # --- Minimum, maximum, meest waarschijnlijke fout ---
    pmin = float(p[np.argmax(cc >= 1 - zekerheid)])
    pmax = float(p[np.argmax(cc >= zekerheid)])
    # Bij k = 0 daalt de dichtheid monotoon (minimum 0, meest waarschijnlijk 0);
    # bij binomiaal/hypergeometrisch is bij k = n het maximum zeker 1. Bij
    # Poisson geldt dat laatste niet (de kans op een foutfractie boven 1 is
    # buiten het rooster gelaten) en bij n = 0 is er geen informatie.
    regel_k_nul = k == 0 and not (verdeling == "poisson" and n == 0)
    regel_k_n = k == n and verdeling != "poisson"
    if regel_k_nul:
        pmin = 0.0
    if regel_k_n:
        pmax = 1.0

    hoogste = np.flatnonzero(np.isclose(c, c.max(), rtol=1e-12, atol=0))
    phigh = float((p[hoogste[0]] + p[hoogste[-1]]) / 2)
    if regel_k_nul:
        phigh = 0.0
    if regel_k_n:
        phigh = 1.0

    boven_norm = p > norm
    kans_boven_norm = float(np.sum(c[boven_norm]) / aantal_stukjes)

    in_band = (band_links <= p) & (p <= band_rechts)
    band_kans = float(np.sum(c[in_band]) / aantal_stukjes)

    tabel = pd.DataFrame({"p": p, "c_raw": c_raw, "c": c, "cc": cc})

    return {
        "tabel": tabel,
        "verdeling": verdeling,
        "n": n,
        "k": k,
        "massa": massa,
        "massa_aangenomen": massa_aangenomen,
        "zekerheid": zekerheid,
        "norm": norm,
        "m": m,
        "aantal_punten": len(tabel),
        "band_links": band_links,
        "band_rechts": band_rechts,
        "zeker_min": regel_k_nul,
        "zeker_max": regel_k_n,
        "pmin": pmin,
        "pmax": pmax,
        "phigh": phigh,
        "kans_boven_norm": kans_boven_norm,
        "band_kans": band_kans,
    }


def _procent(x: float, cijfers: int = 4) -> str:
    return nl_getal_variabel(_signifdig(x * 100, cijfers))


def plot_eval_distribution(
    res: dict,
    titel: str = "",
    titel2: str = "",
    toon_massa: bool = False,
    toon_n: bool = True,
    toon_k: bool = True,
    toon_min: bool = True,
    toon_max: bool = True,
    toon_meest_waarschijnlijke: bool = True,
    toon_norm: bool = True,
    toon_band: bool = False,
    toon_aantal_punten: bool = True,
    toon_verdeling: bool = True,
    geklemd_deel: str = "tussen_pmin_pmax",
    toon_kans: str = "dichtheid",
    clip_bij: float = 0.01,
    figsize: tuple[float, float] = (8.27, 11.69),
) -> plt.Figure:
    """Teken de kanskromme van ``eval_distribution`` (zoals het SAS-rapport).

    Parameters
    ----------
    res:
        Uitvoer van ``eval_distribution``.
    geklemd_deel:
        Donkerblauw gekleurd deel onder de kromme (de rest is lichtblauw; standaard tussen minimale en maximale fout): een van ``"geen"``,
        ``"onder_pmax"``, ``"boven_pmin"``, ``"tussen_pmin_pmax"``, ``"band"``,
        ``"boven_norm"``.
    toon_kans:
        ``"dichtheid"`` (genormeerd, kolom ``c``) of ``"origineel"``
        (onbewerkte kans, kolom ``c_raw``).
    clip_bij:
        Alleen het deel van de kromme met kans >= ``clip_bij`` maal de hoogste
        kans wordt getekend.
    figsize:
        Standaard A4 staand (inches).
    """
    if geklemd_deel not in _GEKLEURD_DEEL:
        raise ValueError(f"geklemd_deel moet een van {_GEKLEURD_DEEL} zijn.")
    if toon_kans not in ("dichtheid", "origineel"):
        raise ValueError("toon_kans moet 'dichtheid' of 'origineel' zijn.")
    if not 0 <= clip_bij <= 1:
        raise ValueError("clip_bij moet in [0, 1] liggen.")

    tabel = res["tabel"]
    p = tabel["p"].to_numpy()
    y = tabel["c" if toon_kans == "dichtheid" else "c_raw"].to_numpy()
    ppct = p * 100
    pmin, pmax, phigh = res["pmin"], res["pmax"], res["phigh"]
    norm = res["norm"]

    maskers = {
        "onder_pmax": p <= pmax,
        "boven_pmin": p >= pmin,
        "tussen_pmin_pmax": (pmin <= p) & (p <= pmax),
        "band": (res["band_links"] <= p) & (p <= res["band_rechts"]),
        "boven_norm": p > norm,
    }

    zichtbaar = y >= clip_bij * y.max()

    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes((0.12, 0.30, 0.82, 0.55))

    # Het hele gebied onder de kromme is lichtblauw; het gekozen deel
    # (standaard tussen de minimale en de maximale fout) is donkerblauw.
    if len(p) <= _MAX_PUNTEN_VOOR_VLAK:
        # Weinig punten: naalden, zodat zichtbaar blijft hoeveel punten
        # berekend zijn (zoals ``interpol=needle`` in SAS).
        ax.vlines(ppct[zichtbaar], 0, y[zichtbaar], color=_KLEUR_BUITEN, linewidth=1)
        if geklemd_deel != "geen":
            gekozen = maskers[geklemd_deel] & zichtbaar
            ax.vlines(ppct[gekozen], 0, y[gekozen], color=_KLEUR_BINNEN, linewidth=1)
    else:
        ax.fill_between(ppct, 0, y, where=zichtbaar, color=_KLEUR_BUITEN, linewidth=0)
        if geklemd_deel != "geen":
            # Laat het donkere deel precies bij de lijn beginnen en eindigen,
            # ook als de lijn tussen twee roosterpunten ligt.
            grenzen = {
                "onder_pmax": (-np.inf, pmax),
                "boven_pmin": (pmin, np.inf),
                "tussen_pmin_pmax": (pmin, pmax),
                "band": (res["band_links"], res["band_rechts"]),
                "boven_norm": (norm, np.inf),
            }[geklemd_deel]
            rand = np.array([g * 100 for g in grenzen if np.isfinite(g)])
            rand = rand[(rand > ppct.min()) & (rand < ppct.max())]
            x_vlak = np.union1d(ppct, rand)
            y_vlak = np.interp(x_vlak, ppct, y)
            gekozen_vlak = (
                (x_vlak >= grenzen[0] * 100 - 1e-9)
                & (x_vlak <= grenzen[1] * 100 + 1e-9)
                & (y_vlak >= clip_bij * y.max())
            )
            ax.fill_between(
                x_vlak,
                0,
                y_vlak,
                where=gekozen_vlak,
                color=_KLEUR_BINNEN,
                linewidth=0,
            )
    ax.plot(ppct[zichtbaar], y[zichtbaar], color=_KLEUR_BUITEN, linewidth=2)

    # Verticale lijnen, elk in een eigen kleur, van links naar rechts gesorteerd.
    lijnen: list[tuple[float, str, str]] = []
    k, n = res["k"], res["n"]
    zeker = nl_getal_variabel(res["zekerheid"] * 100)
    if toon_min:
        tekst = f"minimale fout = {_procent(pmin)}%"
        if toon_massa:
            tekst += f"; dit is {nl_getal(res['massa'] * pmin, 0)} posten"
        tekst += (
            "; bij een zekerheid van 100%, want k = 0."
            if res["zeker_min"]
            else f"; bij een 1-zijdige zekerheid van {zeker}%, bij k > 0."
        )
        lijnen.append((pmin, tekst, _KLEUR_MIN))
    if toon_max:
        tekst = f"maximale fout = {_procent(pmax)}%"
        if toon_massa:
            tekst += f"; dit is {nl_getal(res['massa'] * pmax, 0)} posten"
        tekst += (
            "; bij een zekerheid van 100%, want k = n."
            if res["zeker_max"]
            else f"; bij een 1-zijdige zekerheid van {zeker}%, bij k < n."
        )
        lijnen.append((pmax, tekst, _KLEUR_MAX))
    if toon_meest_waarschijnlijke:
        tekst = f"meest waarschijnlijke fout = {_procent(phigh, 12)}%"
        if res["zeker_min"]:
            tekst += ", want k = 0"
        elif res["zeker_max"]:
            tekst += ", want k = n"
        if toon_massa:
            tekst += f"; dit is {nl_getal(res['massa'] * phigh, 0)} posten"
        lijnen.append((phigh, tekst + ".", _KLEUR_MEEST_WAARSCHIJNLIJK))
    if toon_norm and 0 < norm < 1:
        tekst = f"norm is fout > {_procent(norm, 12)}%"
        if toon_massa:
            tekst += f"; dit is {nl_getal(norm * res['massa'], 0)} posten"
        tekst += f"; kans = {_procent(res['kans_boven_norm'])}%."
        lijnen.append((norm, tekst, _KLEUR_NORM))
    lijnen.sort(key=lambda t: t[0])
    for waarde, _, kleur in lijnen:
        ax.axvline(waarde * 100, color=kleur, linewidth=1.5)

    ax.set_xlabel("fout%")
    ax.set_ylabel("kansdichtheid" if toon_kans == "dichtheid" else "kans")
    ax.spines[["top", "right"]].set_visible(False)

    # Titelregels.
    titelregels: list[tuple[str, dict]] = []
    if titel:
        titelregels.append((titel, {"color": "blue", "fontsize": 16}))
    if titel2:
        titelregels.append((titel2, {"color": "blue", "fontsize": 16}))
    if toon_massa:
        titelregels.append((
            f"N = aantal posten in de massa; N = {nl_getal(res['massa'], 0)}",
            {},
        ))
    if toon_n:
        titelregels.append((f"n = aantal getrokken posten; n = {n}", {}))
    if toon_k:
        titelregels.append((f"k = aantal getrokken foute posten; k = {k}", {}))
    y_pos = 0.97
    for tekst, opmaak in titelregels:
        fontsize = opmaak.get("fontsize", 10)
        fig.text(
            0.12,
            y_pos,
            tekst,
            ha="left",
            va="top",
            color=opmaak.get("color", "black"),
            fontsize=fontsize,
        )
        y_pos -= 0.012 + fontsize * 0.0016

    # Voetregels.
    voet: list[tuple[str, str]] = []
    if lijnen:
        voet.append((
            "Verticale lijn:"
            if len(lijnen) == 1
            else "Verticale lijnen van links naar rechts respectievelijk:",
            "black",
        ))
        voet.extend((f"- {tekst}", kleur) for _, tekst, kleur in lijnen)
    if toon_band:
        voet.append((
            f"Zekerheid dat fout% tussen {_procent(res['band_links'], 12)}% en "
            f"{_procent(res['band_rechts'], 12)}% ligt (in blauwe gebied) is "
            f"{_procent(res['band_kans'])}%.",
            "black",
        ))
    if toon_aantal_punten:
        voet.append((
            f"Aantal punten berekend: {nl_getal(res['aantal_punten'], 0)}.",
            "black",
        ))
    if toon_verdeling:
        naam = {
            "binomiaal": "binomiale",
            "hypergeometrisch": "hypergeometrische",
            "poisson": "Poisson",
            "normaal": "normale",
        }[res["verdeling"]]
        voet.append((f"Berekening is gebaseerd op de {naam} verdeling.", "black"))
    for i, (tekst, kleur) in enumerate(voet):
        fig.text(
            0.12, 0.20 - i * 0.022, tekst, ha="left", va="top", fontsize=9, color=kleur
        )

    return fig
