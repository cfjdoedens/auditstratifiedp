"""
Evaluatiefuncties van auditstratified.
Hoofdfunctie is eval_stratified().
"""

__all__ = ["eval_stratified"]

import math

import numpy as np
import pandas as pd
from scipy.fft import fft, ifft, next_fast_len
from scipy.signal import fftconvolve
from scipy.stats import beta, gamma, gaussian_kde

# Zorg ervoor dat de helperfunctie beschikbaar is.
from .utils import foutloze_posten_equivalent


def eval_stratified(
    steekproeven: pd.DataFrame,
    model: str = "binomiaal",
    zekerheid: float = 0.95,
    methode: str = "FFT samen",
    granulariteit: int = None,
    start: int = 1,
    vergelijk: bool = True,
) -> dict:
    """
    Evalueer samen de resultaten van 1 of meer steekproeven op uitgaand geld.

    Het samennemen van de resultaten gebeurt door convolutie van
    de foutkanskrommes van de afzonderlijke steekproeven tot 1 foutkanskromme.

    Parameters
    ----------
    steekproeven : pd.DataFrame
        Invoertabel met één rij per stratum.
        Verplichte kolommen: ``naam``, ``waarde_laag``, ``n_laag``, ``k_laag``.
        Optionele kolommen (standaardwaarden worden ingevuld als ze ontbreken):

        - ``ihr`` (str, standaard ``'H'``)
        - ``ibr`` (str, standaard ``'H'``)
        - ``car`` (str, standaard ``'H'``)
        - ``waarde_hoog`` (float, standaard ``0.0``)
        - ``fout_hoog`` (float, standaard ``0.0``)
        - ``materialiteit`` (float, standaard ``0.01``)

    model : {"binomiaal", "poisson"}
        Kansmodel voor de convolutieberekening.
        binomiaal bij verstek.

    zekerheid : float
        Gewenste statistische zekerheid.
        Tussen 0 en 1.
        0.95 bij verstek.

    methode : {"FFT paarsgewijs", "FFT samen", "direct", "Monte Carlo"}
        De methode voor de benadering van de convolutie.
        "FFT paarsgewijs" voor een paarsgewijze FFT-benadering.
        "FFT samen" voor een FFT-benadering in 1 keer over alle strata.
        "direct" voor een paarsgewijze, "naieve" berekening.
        "Monte Carlo" voor een Monte Carlo-simulatie.
        "FFT samen" bij verstek.

    granulariteit : int
        Aantal stappen in de FFT-benadering,
        of aantal kanstrekking voor de Monte Carlo benadering.
        100.000 bij verstek voor FFT.
        10.000.000 bij verstek voor Monte Carlo.

    start : int
        Startwaarde voor de toevalsgenerator.
        Wordt gebruikt bij de Monte-Carlo-methode.
        1 bij verstek.

    vergelijk : bool
        Als True, evalueer dan ter vergelijking:

        - **als1** waarbij je alle getrokken posten bij elkaar
          telt van alle strata, en alle gevonden fouten van alle strata
        - **los** waarbij je ieder stratum apart evalueert,
          en de resultaten gewogen optelt.

        True bij verstek.

    Returns
    -------
    dict
        Dictionary met onder andere de sleutels `kanskromme`,
        `max_fout_convolutie`, `populatie_totaal` en `steekproeven`.

    Raises
    ------
    TypeError
        Als `steekproeven` geen pandas DataFrame is.
        Als `zekerheid`, `granulariteit` of `start` niet van het vereiste type is,
        of als `vergelijk` geen boolean is.
    ValueError
        Als `steekproeven`
        - leeg is,
        - vereiste kolommen mist,
        - dubbele stratumnamen bevat,
        - NaN-waarden heeft
        - ongeldige kolominhoud heeft
          . negatieve waarden
          . `k_laag` > `n_laag`
          . `fout_hoog` > `waarde_hoog`
          . `materialiteit` buiten (0, 1),
          . `ihr`/`ibr`/`car` niet in {'H', 'M', 'L'}
          . fout_hoog >= materialiteit × waarde_populatie
        Als `model` niet `'binomiaal'` of `'poisson'` is.
        Als `zekerheid` buiten [0, 1] ligt.
        Als `methode` geen geldige methode is.
        Als `granulariteit` kleiner is dan 1, of te laag voor het kleinste laagstratum
        (alleen FFT-methoden).
    """
    # Voeg standaardwaarden toe voor optionele kolommen als ze ontbreken.
    # Dit gebeurt vóór de validatie zodat die altijd op volledige data werkt.
    if isinstance(steekproeven, pd.DataFrame):
        steekproeven = steekproeven.copy()
        optionele_standaarden = {
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "waarde_hoog": 0.0,
            "fout_hoog": 0.0,
            "materialiteit": 0.01,
        }
        for kolom, standaard in optionele_standaarden.items():
            if kolom not in steekproeven.columns:
                steekproeven[kolom] = standaard

    INVOER_CONTROLE = True  # Niet op False zetten, tenzij je de controles,
    # met name de controle op dubbele stratumnamen,
    # hieronder, buiten de functieaanroep overdoet!

    # Controleer de waarden van de parameters van de functie.
    if INVOER_CONTROLE:
        # Valideer steekproeven.
        if not isinstance(steekproeven, pd.DataFrame):
            raise TypeError("steekproeven moet een pandas DataFrame zijn.")
        if len(steekproeven) == 0:
            raise ValueError("steekproeven is leeg: moet tenminste 1 stratum bevatten.")

        # Controle op vereiste kolommen in steekproeven.
        # ihr, ibr, car, waarde_hoog, fout_hoog en materialiteit zijn optioneel:
        # ze zijn al aangevuld met standaardwaarden als ze ontbraken.
        vereiste_kolommen = {
            "naam",
            "waarde_laag",
            "n_laag",
            "k_laag",
        }
        ontbrekend = vereiste_kolommen - set(steekproeven.columns)
        if ontbrekend:
            raise ValueError(f"Ontbrekende kolommen: {', '.join(sorted(ontbrekend))}")

        # Controle op dubbele stratumnamen.
        if steekproeven["naam"].duplicated().any():
            dubbele = steekproeven[steekproeven["naam"].duplicated()]["naam"].unique()
            raise ValueError(
                f"Evaluatiefout: De volgende stratumnamen komen vaker dan één keer voor: {', '.join(dubbele)}"
            )

        # Controleer op NaN-waarden in alle aanwezige kolommen
        # (verplicht én optioneel; optionele zijn al aangevuld met standaardwaarden).
        alle_te_valideren_kolommen = vereiste_kolommen | {
            "ihr",
            "ibr",
            "car",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        }
        kolommen_met_nan = [
            k
            for k in sorted(alle_te_valideren_kolommen)
            if steekproeven[k].isna().any()
        ]
        if kolommen_met_nan:
            raise ValueError(
                f"De volgende kolommen bevatten lege waarden (NaN): {', '.join(kolommen_met_nan)}"
            )

        # Controleer kolom 'naam' op lege strings.
        if (steekproeven["naam"].str.strip() == "").any():
            raise ValueError("Kolom 'naam' mag geen lege strings bevatten.")

        # Controleer de numerieke kolommen op geldig dtype.
        numerieke_kolommen = [
            "waarde_laag",
            "n_laag",
            "k_laag",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        ]
        niet_numeriek = [
            k
            for k in numerieke_kolommen
            if not pd.api.types.is_numeric_dtype(steekproeven[k])
        ]
        if niet_numeriek:
            raise ValueError(
                f"De volgende kolommen moeten numerieke waarden bevatten: {', '.join(niet_numeriek)}"
            )

        # Controleer waarde_laag: >= 0.
        if (steekproeven["waarde_laag"] < 0).any():
            raise ValueError("Kolom 'waarde_laag' mag geen negatieve waarden bevatten.")

        # Controleer n_laag: >= 0 en geen gebroken waarden.
        if (steekproeven["n_laag"] < 0).any():
            raise ValueError("Kolom 'n_laag' mag geen negatieve waarden bevatten.")
        if not (steekproeven["n_laag"] == steekproeven["n_laag"].round()).all():
            raise ValueError("Kolom 'n_laag' mag alleen gehele getallen bevatten.")

        # Controleer k_laag: >= 0 en niet groter dan n_laag.
        if (steekproeven["k_laag"] < 0).any():
            raise ValueError("Kolom 'k_laag' mag geen negatieve waarden bevatten.")
        if (steekproeven["k_laag"] > steekproeven["n_laag"]).any():
            raise ValueError(
                "Kolom 'k_laag' mag de bijbehorende 'n_laag' niet overschrijden."
            )

        # Controleer waarde_hoog: >= 0.
        if (steekproeven["waarde_hoog"] < 0).any():
            raise ValueError("Kolom 'waarde_hoog' mag geen negatieve waarden bevatten.")

        # Controleer fout_hoog: >= 0 én niet groter dan de bijbehorende waarde_hoog.
        if (steekproeven["fout_hoog"] < 0).any():
            raise ValueError("Kolom 'fout_hoog' mag geen negatieve waarden bevatten.")
        if (steekproeven["fout_hoog"] > steekproeven["waarde_hoog"]).any():
            raise ValueError(
                "Kolom 'fout_hoog' mag de bijbehorende 'waarde_hoog' niet overschrijden."
            )

        # Controleer materialiteit (kolom): in het open interval (0, 1).
        if (steekproeven["materialiteit"] <= 0).any() or (
            steekproeven["materialiteit"] >= 1
        ).any():
            raise ValueError(
                "Kolom 'materialiteit' moet waarden bevatten in het open interval (0, 1)."
            )

        # Controleer ihr, ibr, car: uitsluitend 'H', 'M' of 'L'.
        geldige_risicos = {"H", "M", "L"}
        for kolom in ["ihr", "ibr", "car"]:
            ongeldig = ~steekproeven[kolom].isin(geldige_risicos)
            if ongeldig.any():
                ongeldige_waarden = steekproeven.loc[ongeldig, kolom].unique().tolist()
                raise ValueError(
                    f"Kolom '{kolom}' bevat ongeldige waarden: {ongeldige_waarden}. "
                    "Toegestaan zijn uitsluitend 'H', 'M' en 'L'."
                )

        # Controleer cross-constraint: materialiteit * (waarde_laag + waarde_hoog) > fout_hoog.
        waarde_populatie_check = (
            steekproeven["waarde_laag"] + steekproeven["waarde_hoog"]
        )
        afgekeurde_strata_check = steekproeven.loc[
            steekproeven["materialiteit"] * waarde_populatie_check
            <= steekproeven["fout_hoog"],
            "naam",
        ].tolist()
        if afgekeurde_strata_check:
            raise ValueError(
                f"De reeds gevonden fout in het hoogstratum overschrijdt (of evenaart) de toegestane "
                f"totale materialiteit. Er is geen foutmarge meer over voor het laagstratum. "
                f"Fout bij: {', '.join(afgekeurde_strata_check)}."
            )

        # Valideer het model.
        if model not in ["binomiaal", "poisson"]:
            raise ValueError("Model moet 'binomiaal' of 'poisson' zijn.")

        # Valideer de zekerheid.
        if isinstance(zekerheid, bool) or not isinstance(zekerheid, (int, float)):
            raise TypeError(
                "zekerheid mag geen boolean zijn, maar moet een getal van 0 tot 1 zijn."
            )
        if not (0 <= zekerheid <= 1):
            raise ValueError("zekerheid moet op het segment [0, 1] liggen.")

        # Valideer de methode.
        if methode not in ["FFT paarsgewijs", "FFT samen", "direct", "Monte Carlo"]:
            raise ValueError(f"Ongeldige methode: {methode!r}")

        # Bepaal dynamische verstekwaarde voor granulariteit.
        if granulariteit is None:
            granulariteit = int(1e7) if methode == "Monte Carlo" else int(1e5)

        # Valideer de granulariteit.
        if isinstance(granulariteit, bool) or not isinstance(granulariteit, int):
            raise TypeError("granulariteit moet een geheel getal zijn (geen boolean).")
        if granulariteit < 1:
            raise ValueError("granulariteit moet een geheel getal >= 1 zijn.")

        # Voorkom deling door nul bij extreme gewichtsverschillen tussen strata (FFT-methoden).
        if methode != "Monte Carlo":
            laag_strata = steekproeven[steekproeven["waarde_laag"] > 0]
            if not laag_strata.empty:
                min_waarde_laag = laag_strata["waarde_laag"].min()
                totaal_waarde_laag = laag_strata["waarde_laag"].sum()
                dx = totaal_waarde_laag / granulariteit
                if dx >= min_waarde_laag:
                    min_benodigde_gran = math.ceil(
                        (totaal_waarde_laag / min_waarde_laag) * 10
                    )
                    raise ValueError(
                        f"De granulariteit ({granulariteit}) is te laag ten opzichte van het kleinste "
                        f"stratum (waarde: {min_waarde_laag}). De berekening zou hierdoor crashen. "
                        f"Verhoog de granulariteit naar minimaal {min_benodigde_gran}."
                    )

        # Valideer start.
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise TypeError("start moet een int of een float zijn (geen boolean).")

        # Valideer vergelijk.
        if not isinstance(vergelijk, bool):
            raise TypeError("vergelijk moet een boolean zijn.")

    # Bepaal totaal geldswaarde, inclusief het 100%-getoetste deel.
    totaalgeld_laag = steekproeven["waarde_laag"].sum()
    totaalgeld_fout_hoog = steekproeven["fout_hoog"].sum()
    totaalgeld_goed_hoog = (
        steekproeven["waarde_hoog"] - steekproeven["fout_hoog"]
    ).sum()
    totaalgeld_algeheel = totaalgeld_laag + totaalgeld_fout_hoog + totaalgeld_goed_hoog

    # Creëer uitvoer DataFrame met regels per steekproef en vul afgeleide kolommen.
    t_uit = steekproeven.copy()
    t_uit["goed_hoog"] = t_uit["waarde_hoog"] - t_uit["fout_hoog"]
    t_uit["waarde_populatie"] = t_uit["waarde_laag"] + t_uit["waarde_hoog"]

    # Wiskundig zuiver: haal de bekende fout_hoog van het totale materialiteitsbudget af.
    t_uit["materialiteit_in_geld"] = (
        t_uit["materialiteit"] * t_uit["waarde_populatie"]
    ) - t_uit["fout_hoog"]

    # Zet eerst de standaardwaarden voor alle rijen.
    t_uit["materialiteit_laag"] = None
    t_uit["extra_foutloze_posten"] = 0

    # Maak een masker voor uitsluitend de rijen waar het laagstratum groter is dan 0.
    masker = t_uit["waarde_laag"] > 0

    # Voer de berekeningen alléén uit voor de rijen in het masker.
    if masker.any():
        t_uit.loc[masker, "materialiteit_laag"] = (
            t_uit.loc[masker, "materialiteit_in_geld"]
            / t_uit.loc[masker, "waarde_laag"]
        )

        # Controleer dat materialiteit_laag strikt kleiner is dan 1.
        # Dit is een gebruikersfout (te hoge materialiteit t.o.v. de waarde_laag/waarde_hoog-verhouding),
        # dus ValueError en geen AssertionError.
        foute_strata = t_uit.loc[
            masker & (t_uit["materialiteit_laag"] >= 1), "naam"
        ].tolist()
        if foute_strata:
            raise ValueError(
                f"Materialiteit voor het laagstratum mag niet >= 1 zijn. Fout bij: {', '.join(foute_strata)}."
            )

        # Apply de helperfunctie uitsluitend op de juiste rijen.
        t_uit.loc[masker, "extra_foutloze_posten"] = t_uit.loc[masker].apply(
            lambda row: foutloze_posten_equivalent(
                row["ihr"],
                row["ibr"],
                row["car"],
                row["materialiteit_laag"],
            ),
            axis=1,
        )

    t_uit["toch_fouten"] = ~(
        (t_uit["ihr"] == "H") & (t_uit["ibr"] == "H") & (t_uit["car"] == "H")
    ) & (t_uit["k_laag"] > 0)

    # Convolutie: FFT, FFT samen, direct, of MonteCarlo.
    if methode == "FFT paarsgewijs":
        conv = convolutie_fft(
            t_uit,
            model,
            zekerheid,
            granulariteit,
            totaalgeld_laag,
            totaalgeld_fout_hoog,
            totaalgeld_algeheel,
        )
    elif methode == "FFT samen":
        conv = convolutie_fft_gelijktijdig(
            t_uit,
            model,
            zekerheid,
            granulariteit,
            totaalgeld_laag,
            totaalgeld_fout_hoog,
            totaalgeld_algeheel,
        )
    elif methode == "direct":
        conv = convolutie_direct(
            t_uit,
            model,
            zekerheid,
            granulariteit,
            totaalgeld_laag,
            totaalgeld_fout_hoog,
            totaalgeld_algeheel,
        )
    else:
        conv = convolutie_montecarlo(
            t_uit,
            model,
            zekerheid,
            granulariteit,
            start,
            totaalgeld_laag,
            totaalgeld_fout_hoog,
            totaalgeld_algeheel,
        )

    # Ter vergelijking: los en als1.
    vergelijk_met = {}
    if vergelijk:
        verg = vergelijk_los_en_als1(
            t_uit,
            model,
            zekerheid,
            totaalgeld_laag,
            totaalgeld_fout_hoog,
            totaalgeld_algeheel,
        )
        t_uit = verg["t_uit"]
        vergelijk_met = {
            "mw_fout_los": verg["mw_fout_los"],
            "mw_fout_los_geld": verg["mw_fout_los"] * totaalgeld_algeheel,
            "min_fout_los": verg["min_fout_los"],
            "min_fout_los_geld": verg["min_fout_los"] * totaalgeld_algeheel,
            "max_fout_los": verg["max_fout_los"],
            "max_fout_los_geld": verg["max_fout_los"] * totaalgeld_algeheel,
            "mw_fout_als1": verg["mw_fout_als1"],
            "mw_fout_als1_geld": verg["mw_fout_als1"] * totaalgeld_algeheel,
            "min_fout_als1": verg["min_fout_als1"],
            "min_fout_als1_geld": verg["min_fout_als1"] * totaalgeld_algeheel,
            "max_fout_als1": verg["max_fout_als1"],
            "max_fout_als1_geld": verg["max_fout_als1"] * totaalgeld_algeheel,
        }

    # Resultaat opstellen en retourneren als dictionary.
    return {
        "kanskromme": conv["d"],
        "populatie_totaal": totaalgeld_algeheel,
        "modus_fout_convolutie": conv["modus_fout"],
        "modus_fout_convolutie_geld": conv["modus_fout"] * totaalgeld_algeheel,
        "mediaan_fout_convolutie": conv["mediaan_fout"],
        "mediaan_fout_convolutie_geld": conv["mediaan_fout"] * totaalgeld_algeheel,
        "gemiddelde_fout_convolutie": conv["gemiddelde_fout"],
        "gemiddelde_fout_convolutie_geld": conv["gemiddelde_fout"]
        * totaalgeld_algeheel,
        "mw_fout_convolutie": conv["modus_fout"],
        "mw_fout_convolutie_geld": conv["modus_fout"] * totaalgeld_algeheel,
        "min_fout_convolutie": conv["min_fout"],
        "min_fout_convolutie_geld": conv["min_fout"] * totaalgeld_algeheel,
        "max_fout_convolutie": conv["max_fout"],
        "max_fout_convolutie_geld": conv["max_fout"] * totaalgeld_algeheel,
        "vergelijk_met": vergelijk_met,
        "steekproeven": t_uit,
        "invoer": {
            "model": model,
            "zekerheid": zekerheid,
            "methode": methode,
            "granulariteit": granulariteit,
            "start": start,
            "vergelijk": vergelijk,
        },
    }


def convolutie_montecarlo(
    t_uit,
    model,
    zekerheid,
    granulariteit,
    start,
    totaalgeld_laag,
    totaalgeld_fout_hoog,
    totaalgeld_algeheel,
):
    """Convolutie via Monte Carlo simulatie."""
    # Zorg voor reproduceerbaarheid via de seed.
    if start != 0:
        np.random.seed(start)

    # Simuleer foutfracties per stratum via kansverdelingen.
    n_steekproeven = len(t_uit)
    krommen = np.zeros((int(granulariteit), n_steekproeven))

    for i in range(n_steekproeven):
        n_calc = t_uit["n_laag"].iloc[i] + t_uit["extra_foutloze_posten"].iloc[i]
        k_calc = t_uit["k_laag"].iloc[i]

        if model == "binomiaal":
            krommen[:, i] = beta.rvs(
                a=k_calc + 1, b=n_calc - k_calc + 1, size=int(granulariteit)
            )
        else:
            krommen[:, i] = gamma.rvs(
                a=k_calc + 1, scale=1.0 / n_calc, size=int(granulariteit)
            )

    # Convolutie via matrixvermenigvuldiging (dot product) van fracties en geldwaarden.
    convolutie = (
        np.dot(krommen, t_uit["waarde_laag"].values) + totaalgeld_fout_hoog
    ) / totaalgeld_algeheel

    # Kernel density estimation over de simulatie-uitkomst.
    bovengrens = 1.0 if model == "binomiaal" else (np.max(convolutie) + 0.1)
    kde = gaussian_kde(convolutie)
    kde.set_bandwidth(bw_method=kde.factor * 1.5)

    x_grid = np.linspace(0, bovengrens, 512)
    y_vals = kde.evaluate(x_grid)

    # Normaliseer de kernel density.
    dx = x_grid[1] - x_grid[0]
    oppervlakte = np.sum(y_vals) * dx
    y_vals = y_vals / oppervlakte

    return {
        "d": {"x": x_grid, "y": y_vals},
        "min_fout": np.percentile(convolutie, (1 - zekerheid) * 100),
        "max_fout": np.percentile(convolutie, zekerheid * 100),
        "mediaan_fout": np.percentile(convolutie, 50),
        "modus_fout": x_grid[np.argmax(y_vals)],
        "gemiddelde_fout": np.mean(convolutie),
    }


def convolutie_fft_gelijktijdig(
    t_uit,
    model,
    zekerheid,
    granulariteit,
    totaalgeld_laag,
    totaalgeld_fout_hoog,
    totaalgeld_algeheel,
):
    """
    Convolutie via gelijktijdige Fast Fourier Transform.
    Transformeert alle strata tegelijk naar het frequentiedomein.
    """
    # Randgeval: geen statistische controle, alles integraal.
    if totaalgeld_laag < 0.01:
        frac = totaalgeld_fout_hoog / totaalgeld_algeheel
        return {
            "d": {"x": np.array([frac]), "y": np.array([1.0])},
            "min_fout": frac,
            "max_fout": frac,
            "mediaan_fout": frac,
            "modus_fout": frac,
            "gemiddelde_fout": frac,
        }

    # Bouw kansmassavectoren per stratum.
    dx = totaalgeld_laag / granulariteit
    p_strata = []

    for i in range(len(t_uit)):
        w_laag = t_uit["waarde_laag"].iloc[i]
        n_calc = t_uit["n_laag"].iloc[i] + t_uit["extra_foutloze_posten"].iloc[i]
        k_calc = t_uit["k_laag"].iloc[i]

        if w_laag > 0:
            max_frac = (
                1.0
                if model == "binomiaal"
                else gamma.ppf(0.9999, a=k_calc + 1, scale=1.0 / n_calc)
            )
            x_grens = max(w_laag, max_frac * w_laag)
            x_as = np.arange(0, x_grens + dx, dx)

            if model == "binomiaal":
                p = beta.pdf(x_as / w_laag, k_calc + 1, n_calc - k_calc + 1)
            else:
                p = gamma.pdf(x_as / w_laag, a=k_calc + 1, scale=1.0 / n_calc)

            p = np.nan_to_num(p, posinf=0.0, neginf=0.0)
            p = p / np.sum(p)
            p_strata.append(p)

    # Gelijktijdige convolutie via zero-padding en fft.
    if len(p_strata) == 1:
        p_totaal = p_strata[0]
    else:
        totale_lengte = sum(len(p) for p in p_strata) - len(p_strata) + 1
        pad_lengte = next_fast_len(totale_lengte)

        fft_product = np.ones(pad_lengte, dtype=complex)
        for p in p_strata:
            p_padded = np.pad(p, (0, pad_lengte - len(p)))
            fft_product *= fft(p_padded)

        p_totaal = np.real(ifft(fft_product))
        p_totaal = p_totaal[:totale_lengte]

        p_totaal[(p_totaal < 0) & (np.abs(p_totaal) < 1e-12)] = 0
        p_totaal = p_totaal / np.sum(p_totaal)

    # Bereken de totale assen en parameters.
    x_totaal_laag = np.arange(len(p_totaal)) * dx
    x_totaal_geld = x_totaal_laag + totaalgeld_fout_hoog
    x_totaal_fractie = x_totaal_geld / totaalgeld_algeheel

    dx_fractie = dx / totaalgeld_algeheel
    d = {"x": x_totaal_fractie, "y": p_totaal / dx_fractie}

    cum_p = np.cumsum(p_totaal)

    min_fout = interpolate_quantile(cum_p, x_totaal_fractie, 1 - zekerheid)
    max_fout = interpolate_quantile(cum_p, x_totaal_fractie, zekerheid)
    mediaan_fout = interpolate_quantile(cum_p, x_totaal_fractie, 0.5)

    return {
        "d": d,
        "min_fout": min_fout,
        "max_fout": max_fout,
        "mediaan_fout": mediaan_fout,
        "modus_fout": x_totaal_fractie[np.argmax(p_totaal)],
        "gemiddelde_fout": np.sum(x_totaal_fractie * p_totaal),
    }


def convolutie_fft(
    t_uit,
    model,
    zekerheid,
    granulariteit,
    totaalgeld_laag,
    totaalgeld_fout_hoog,
    totaalgeld_algeheel,
):
    """Convolutie via paarsgewijze Fast Fourier Transformatie."""
    # Noot: de rekenstappen voor de assen zijn identiek aan de gelijktijdige methode.
    if totaalgeld_laag < 0.01:
        frac = totaalgeld_fout_hoog / totaalgeld_algeheel
        return {
            "d": {"x": np.array([frac]), "y": np.array([1.0])},
            "min_fout": frac,
            "max_fout": frac,
            "mediaan_fout": frac,
            "modus_fout": frac,
            "gemiddelde_fout": frac,
        }

    dx = totaalgeld_laag / granulariteit
    p_strata = []

    for i in range(len(t_uit)):
        w_laag = t_uit["waarde_laag"].iloc[i]
        n_calc = t_uit["n_laag"].iloc[i] + t_uit["extra_foutloze_posten"].iloc[i]
        k_calc = t_uit["k_laag"].iloc[i]

        if w_laag > 0:
            max_frac = (
                1.0
                if model == "binomiaal"
                else gamma.ppf(0.9999, a=k_calc + 1, scale=1.0 / n_calc)
            )
            x_grens = max(w_laag, max_frac * w_laag)
            x_as = np.arange(0, x_grens + dx, dx)

            if model == "binomiaal":
                p = beta.pdf(x_as / w_laag, k_calc + 1, n_calc - k_calc + 1)
            else:
                p = gamma.pdf(x_as / w_laag, a=k_calc + 1, scale=1.0 / n_calc)

            p = np.nan_to_num(p, posinf=0.0, neginf=0.0)
            p = p / np.sum(p)
            p_strata.append(p)

    # Paarsgewijze convolutie in een klassieke lus.
    if len(p_strata) > 0:
        p_totaal = p_strata[0]
        for p_next in p_strata[1:]:
            p_totaal = fftconvolve(p_totaal, p_next, mode="full")
            p_totaal[(p_totaal < 0) & (np.abs(p_totaal) < 1e-12)] = 0
            p_totaal = p_totaal / np.sum(p_totaal)

    x_totaal_laag = np.arange(len(p_totaal)) * dx
    x_totaal_geld = x_totaal_laag + totaalgeld_fout_hoog
    x_totaal_fractie = x_totaal_geld / totaalgeld_algeheel

    dx_fractie = dx / totaalgeld_algeheel
    d = {"x": x_totaal_fractie, "y": p_totaal / dx_fractie}

    cum_p = np.cumsum(p_totaal)

    min_fout = interpolate_quantile(cum_p, x_totaal_fractie, 1 - zekerheid)
    max_fout = interpolate_quantile(cum_p, x_totaal_fractie, zekerheid)
    mediaan_fout = interpolate_quantile(cum_p, x_totaal_fractie, 0.5)

    return {
        "d": d,
        "min_fout": min_fout,
        "max_fout": max_fout,
        "mediaan_fout": mediaan_fout,
        "modus_fout": x_totaal_fractie[np.argmax(p_totaal)],
        "gemiddelde_fout": np.sum(x_totaal_fractie * p_totaal),
    }


def convolutie_direct(
    t_uit,
    model,
    zekerheid,
    granulariteit,
    totaalgeld_laag,
    totaalgeld_fout_hoog,
    totaalgeld_algeheel,
):
    """
    Convolutie via directe, "naïeve" berekening, stap-voor-stap volgens
    de formele wiskundige definitie: P(Z=z) = Som(P(X=x) * P(Y=z-x)).
    Hierbij wordt geen gebruik gemaakt van FFT of geoptimaliseerde convolutiefuncties
    zoals numpy.convolve.
    """
    # Randgeval: geen statistische controle, alles integraal.
    if totaalgeld_laag < 0.01:
        frac = totaalgeld_fout_hoog / totaalgeld_algeheel
        return {
            "d": {"x": np.array([frac]), "y": np.array([1.0])},
            "min_fout": frac,
            "max_fout": frac,
            "mediaan_fout": frac,
            "modus_fout": frac,
            "gemiddelde_fout": frac,
        }

    # Bepaal stapgrootte.
    dx = totaalgeld_laag / granulariteit
    p_strata = []

    # Bepaal per stratum de discrete kansvector P(X)
    for i in range(len(t_uit)):
        w_laag = t_uit["waarde_laag"].iloc[i]
        n_calc = t_uit["n_laag"].iloc[i] + t_uit["extra_foutloze_posten"].iloc[i]
        k_calc = t_uit["k_laag"].iloc[i]

        if w_laag > 0:
            max_frac = (
                1.0
                if model == "binomiaal"
                else gamma.ppf(0.9999, a=k_calc + 1, scale=1.0 / n_calc)
            )
            x_grens = max(w_laag, max_frac * w_laag)
            x_as = np.arange(0, x_grens + dx, dx)

            if model == "binomiaal":
                p = beta.pdf(x_as / w_laag, k_calc + 1, n_calc - k_calc + 1)
            else:
                p = gamma.pdf(x_as / w_laag, a=k_calc + 1, scale=1.0 / n_calc)

            p = np.nan_to_num(p, posinf=0.0, neginf=0.0)
            p = p / np.sum(p)
            p_strata.append(p)

    # De naïeve directe convolutie.
    if len(p_strata) > 0:
        p_totaal = p_strata[0]

        # Voor elk volgend stratum Y, voeg dit samen met de huidige P_totaal(X)
        for p_next in p_strata[1:]:
            lengte_huidig = len(p_totaal)
            lengte_volgend = len(p_next)
            lengte_nieuw = lengte_huidig + lengte_volgend - 1

            p_nieuw = np.zeros(lengte_nieuw)

            # De brute force dubbele lus (O(N^2)) om P(Z=z) = P(X=x)*P(Y=z-x) te berekenen
            for i in range(lengte_huidig):
                if p_totaal[i] > 0:  # Kleine optimalisatie: sla kansen van nul over
                    for j in range(lengte_volgend):
                        p_nieuw[i + j] += p_totaal[i] * p_next[j]

            p_totaal = p_nieuw
            p_totaal[(p_totaal < 0) & (np.abs(p_totaal) < 1e-12)] = 0
            p_totaal = p_totaal / np.sum(p_totaal)

    # Assen en kwantielen bepalen.
    x_totaal_laag = np.arange(len(p_totaal)) * dx
    x_totaal_geld = x_totaal_laag + totaalgeld_fout_hoog
    x_totaal_fractie = x_totaal_geld / totaalgeld_algeheel

    dx_fractie = dx / totaalgeld_algeheel
    d = {"x": x_totaal_fractie, "y": p_totaal / dx_fractie}

    cum_p = np.cumsum(p_totaal)

    min_fout = interpolate_quantile(cum_p, x_totaal_fractie, 1 - zekerheid)
    max_fout = interpolate_quantile(cum_p, x_totaal_fractie, zekerheid)
    mediaan_fout = interpolate_quantile(cum_p, x_totaal_fractie, 0.5)

    return {
        "d": d,
        "min_fout": min_fout,
        "max_fout": max_fout,
        "mediaan_fout": mediaan_fout,
        "modus_fout": x_totaal_fractie[np.argmax(p_totaal)],
        "gemiddelde_fout": np.sum(x_totaal_fractie * p_totaal),
    }


def vergelijk_los_en_als1(
    t_uit, model, zekerheid, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel
):
    """Vergelijkingsmethoden: **los** (per stratum) en **als1** (alles samengevoegd)."""
    t_uit_werk = t_uit.copy()
    n_steekproeven = len(t_uit_werk)

    # Los: per stratum apart extrapoleren, dan gewogen optellen.
    mw_fout_lijst, min_fout_lijst, max_fout_lijst = [], [], []

    for i in range(n_steekproeven):
        n_calc = (
            t_uit_werk["n_laag"].iloc[i] + t_uit_werk["extra_foutloze_posten"].iloc[i]
        )
        k_calc = t_uit_werk["k_laag"].iloc[i]

        mw_fout_lijst.append(k_calc / n_calc if n_calc > 0 else 0)

        if model == "binomiaal":
            min_fout_lijst.append(
                beta.ppf(1 - zekerheid, k_calc + 1, n_calc - k_calc + 1)
            )
            max_fout_lijst.append(beta.ppf(zekerheid, k_calc + 1, n_calc - k_calc + 1))
        else:
            min_fout_lijst.append(
                gamma.ppf(1 - zekerheid, a=k_calc + 1, scale=1.0 / n_calc)
            )
            max_fout_lijst.append(
                gamma.ppf(zekerheid, a=k_calc + 1, scale=1.0 / n_calc)
            )

    t_uit_werk["mw_fout"] = mw_fout_lijst
    t_uit_werk["min_fout"] = min_fout_lijst
    t_uit_werk["max_fout"] = max_fout_lijst

    mw_fout_los = (
        np.sum(t_uit_werk["mw_fout"] * t_uit_werk["waarde_laag"]) + totaalgeld_fout_hoog
    ) / totaalgeld_algeheel
    min_fout_los = (
        np.sum(t_uit_werk["min_fout"] * t_uit_werk["waarde_laag"])
        + totaalgeld_fout_hoog
    ) / totaalgeld_algeheel
    max_fout_los = (
        np.sum(t_uit_werk["max_fout"] * t_uit_werk["waarde_laag"])
        + totaalgeld_fout_hoog
    ) / totaalgeld_algeheel

    # Als1: alle strata samenvoegen alsof het 1 steekproef is.
    n_calc_als1 = t_uit_werk["n_laag"].sum() + t_uit_werk["extra_foutloze_posten"].sum()
    k_calc_als1 = t_uit_werk["k_laag"].sum()

    mw_fout_als1_laag = k_calc_als1 / n_calc_als1 if n_calc_als1 > 0 else 0
    if model == "binomiaal":
        min_fout_als1_laag = beta.ppf(
            1 - zekerheid, k_calc_als1 + 1, n_calc_als1 - k_calc_als1 + 1
        )
        max_fout_als1_laag = beta.ppf(
            zekerheid, k_calc_als1 + 1, n_calc_als1 - k_calc_als1 + 1
        )
    else:
        min_fout_als1_laag = gamma.ppf(
            1 - zekerheid, a=k_calc_als1 + 1, scale=1.0 / n_calc_als1
        )
        max_fout_als1_laag = gamma.ppf(
            zekerheid, a=k_calc_als1 + 1, scale=1.0 / n_calc_als1
        )

    return {
        "t_uit": t_uit_werk,
        "mw_fout_los": mw_fout_los,
        "min_fout_los": min_fout_los,
        "max_fout_los": max_fout_los,
        "mw_fout_als1": (
            (mw_fout_als1_laag * totaalgeld_laag + totaalgeld_fout_hoog)
            / totaalgeld_algeheel
        ),
        "min_fout_als1": (
            (min_fout_als1_laag * totaalgeld_laag + totaalgeld_fout_hoog)
            / totaalgeld_algeheel
        ),
        "max_fout_als1": (
            (max_fout_als1_laag * totaalgeld_laag + totaalgeld_fout_hoog)
            / totaalgeld_algeheel
        ),
    }


def interpolate_quantile(cum_p, x_vals, target):
    """Bereken de exacte fractiewaarde van een kwantiel via lineaire interpolatie."""
    idx_boven_array = np.where(cum_p >= target)[0]

    if len(idx_boven_array) == 0:
        return x_vals[-1]

    idx_boven = idx_boven_array[0]
    if idx_boven == 0:
        return x_vals[0]

    idx_onder = idx_boven - 1
    p_onder = cum_p[idx_onder]
    p_boven = cum_p[idx_boven]
    x_onder = x_vals[idx_onder]
    x_boven = x_vals[idx_boven]

    if p_boven == p_onder:
        return x_boven

    pct = (target - p_onder) / (p_boven - p_onder)
    return x_onder + pct * (x_boven - x_onder)
