"""
Planningsfuncties van auditstratified.
Hoofdfunctie is plan_stratified().
"""

__all__ = ["plan_stratified", "plan_stratified_basis", "vind_beste_strata_groep"]

import math
import warnings

import numpy as np
import pandas as pd

# Importeer de benodigde wiskundige rekenmotoren uit de andere pakketbestanden.
from .eval_stratified import eval_stratified
from .utils import drawsneeded, haro_nog_nodige_zekerheid


def plan_stratified(
    steekproeven: pd.DataFrame,
    model: str = "binomiaal",
    zekerheid: float = 0.95,
    granulariteit: int = 10000,
    materialiteit: float = None,
) -> pd.DataFrame:
    """
    Plan de optimale steekproefverdeling.

    Deze functie voert de planning stapsgewijs uit totdat de gecombineerde
    convolutiefout onder de algehele materialiteit zakt, waarbij strata met de
    hoogste foutreductie per kosteneenheid voorrang krijgen.
    De convolutie wordt berekend met "FFT samen": gelijktijdige convolutie
    van alle strata. Want dat is de snelste FFT-methode. En bovendien
    symmetrisch: alle strata worden exact gelijk behandeld.
    Bij de paarsgewijze FFT maakt het ietsje uit wat de volgorde van
    de strata is.

    Parameters
    ----------
    steekproeven : pd.DataFrame
        Invoertabel met één rij per stratum.
        Verplichte kolommen: ``naam``, ``waarde_laag``.
        Optionele kolommen (standaardwaarden worden ingevuld als ze ontbreken):

        - ``verwachte_foutfractie`` (float, standaard ``0.001``)
        - ``ihr`` (str, standaard ``'H'``)
        - ``ibr`` (str, standaard ``'H'``)
        - ``car`` (str, standaard ``'H'``)
        - ``waarde_hoog`` (float, standaard ``0.0``)
        - ``fout_hoog`` (float, standaard ``0.0``)
        - ``materialiteit`` (float, standaard ``0.01``)
        - ``kosten`` (float, standaard ``1.0``)
    model : {"binomiaal", "poisson"}
        Kansmodel voor de convolutieberekening.
        binomiaal bij verstek.
    materialiteit : float
        Maximale grenswaarde van de foutfractie van de totale
        hoeveelheid geld.
        Tussen 0 en 1.
    zekerheid : float
        Gewenste statistische zekerheid.
        Tussen 0 en 1.
        0.95 bij verstek.
    granulariteit : int
        Aantal stappen in de FFT-benadering.
        10.000 bij verstek.

    Returns
    -------
    pd.DataFrame
        Het invoer-DataFrame aangevuld met kolommen `n_laag`, `k_laag`,
        `n_basis`, `kosten` en `waarde_populatie`.
        Het attribuut `geplande_max_fout_totaal` bevat de bereikte convolutiefout.

    Raises
    ------
    TypeError
        Als `steekproeven` geen pandas DataFrame is.
        Als `materialiteit`, `zekerheid` of `granulariteit` niet van het vereiste type is.
    ValueError
        Als `steekproeven`
        - leeg is,
        - vereiste kolommen mist,
        - dubbele stratumnamen bevat,
        - NaN-waarden heeft
        - ongeldige kolominhoud heeft:
          . negatieve waarden
          . `verwachte_foutfractie` buiten [0, 1)
          . `kosten` ≤ 0
          . `fout_hoog` > `waarde_hoog`
          . `materialiteit` buiten (0, 1)
          . `ihr`/`ibr`/`car` niet in {'H', 'M', 'L'}
        Als `model` niet `'binomiaal'` of `'poisson'` is.
        Als `materialiteit` of `zekerheid` buiten [0, 1] ligt, of `granulariteit` ≤ 0.
        Als `granulariteit` te laag is voor het kleinste laagstratum (FFT-crash-preventie).
        Als de bekende fout in een hoogstratum de stratum-materialiteit overschrijdt.
        Als de verwachte foutfractie ≥ de omgerekende materialiteit van het laagstratum.
        Als de totale bekende of verwachte fout de algehele materialiteit overschrijdt.
    """
    # Voeg standaardwaarden toe voor optionele kolommen als ze ontbreken.
    # Dit gebeurt vóór de validatie zodat die altijd op volledige data werkt.
    if isinstance(steekproeven, pd.DataFrame):
        steekproeven = steekproeven.copy()
        optionele_standaarden = {
            "verwachte_foutfractie": 0.001,
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "waarde_hoog": 0.0,
            "fout_hoog": 0.0,
            "materialiteit": 0.01,
            "kosten": 1.0,
        }
        for kolom, standaard in optionele_standaarden.items():
            if kolom not in steekproeven.columns:
                steekproeven[kolom] = standaard

    INVOER_CONTROLE = True  # Niet op False zetten, tenzij je de controles,
    # met name, die ValueErrors kunnen geven,
    # buiten de functieaanroep overdoet!

    # Controleer de waarden van de parameters van de functie.
    if INVOER_CONTROLE:
        # Valideer steekproeven.
        if not isinstance(steekproeven, pd.DataFrame):
            raise TypeError("steekproeven moet een pandas DataFrame zijn.")
        if len(steekproeven) == 0:
            raise ValueError("steekproeven is leeg: moet tenminste 1 stratum bevatten.")

        # Controle op vereiste kolommen in steekproeven.
        # verwachte_foutfractie, ihr, ibr, car, waarde_hoog, fout_hoog, materialiteit
        # en kosten zijn optioneel: ze zijn al aangevuld met standaardwaarden als ze ontbraken.
        vereiste_kolommen = {
            "naam",
            "waarde_laag",
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

        # Controleer op NaN/None-waarden in alle aanwezige kolommen
        # (verplicht én optioneel; optionele zijn al aangevuld met standaardwaarden).
        alle_te_valideren_kolommen = vereiste_kolommen | {
            "verwachte_foutfractie",
            "ihr",
            "ibr",
            "car",
            "kosten",
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
            "verwachte_foutfractie",
            "kosten",
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

        # Controleer verwachte_foutfractie: in [0, 1).
        if (steekproeven["verwachte_foutfractie"] < 0).any() or (
            steekproeven["verwachte_foutfractie"] >= 1
        ).any():
            raise ValueError(
                "Kolom 'verwachte_foutfractie' moet waarden bevatten in het interval [0, 1)."
            )

        # Controleer kosten: strikt positief (> 0).
        if (steekproeven["kosten"] <= 0).any():
            raise ValueError(
                "Kolom 'kosten' moet strikt positieve waarden bevatten (groter dan 0)."
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

        # Valideer het model.
        if model not in ["binomiaal", "poisson"]:
            raise ValueError("Model moet 'binomiaal' of 'poisson' zijn.")

        # Valideer de materialiteit.
        if isinstance(materialiteit, bool) or not isinstance(
            materialiteit, (int, float)
        ):
            raise TypeError(
                "Materialiteit mag geen boolean zijn, maar moet een getal van 0 tot 1 zijn."
            )
        if materialiteit < 0:
            raise ValueError(
                "Materialiteit moet >= 0 zijn. (En liggen op het segment [0, 1].)"
            )
        if materialiteit > 1:
            raise ValueError(
                "Materialiteit moet <= 1 zijn. (En liggen op het segment [0, 1].)"
            )

        # Valideer de zekerheid.
        if isinstance(zekerheid, bool) or not isinstance(zekerheid, (int, float)):
            raise TypeError(
                "Zekerheid mag geen boolean zijn, maar moet een getal van 0 tot 1 zijn."
            )
        if zekerheid < 0:
            raise ValueError(
                "Zekerheid moet >= 0 zijn. (En liggen op het segment [0, 1].)"
            )
        if zekerheid > 1:
            raise ValueError(
                "Zekerheid moet <= 1 zijn. (En liggen op het segment [0, 1].)"
            )

        # Valideer de granulariteit.
        if isinstance(granulariteit, bool) or not isinstance(granulariteit, int):
            raise TypeError(
                "Granulariteit mag geen boolean zijn, maar moet een geheel getal zijn."
            )
        if granulariteit <= 0:
            raise ValueError("Granulariteit moet > 0 zijn. En geheel bovendien.")

        # Controleer cross-constraint: materialiteit * (waarde_laag + waarde_hoog) > fout_hoog.
        # Er moet na aftrek van de reeds bekende fout_hoog een positief budget overblijven voor het laagstratum.
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
                f"stratum-materialiteit. Er is geen foutmarge meer over voor het laagstratum. "
                f"Fout bij: {', '.join(afgekeurde_strata_check)}."
            )

        # Controleer op stratuminconsistentie waarbij de verwachte foutfractie
        # in het laagstratum >= de omgerekende materialiteit van het laagstratum.
        mask_laag = steekproeven["waarde_laag"] > 0
        if mask_laag.any():
            materialiteit_laag_check = (
                (
                    steekproeven.loc[mask_laag, "materialiteit"]
                    * waarde_populatie_check.loc[mask_laag]
                )
                - steekproeven.loc[mask_laag, "fout_hoog"]
            ) / steekproeven.loc[mask_laag, "waarde_laag"]

            probleem_strata = steekproeven.loc[
                mask_laag
                & (
                    steekproeven.loc[mask_laag, "verwachte_foutfractie"]
                    >= materialiteit_laag_check
                ),
                "naam",
            ].tolist()

            if probleem_strata:
                raise ValueError(
                    f"Verwachte foutfractie >= de omgerekende materialiteit van het laagstratum in: {', '.join(probleem_strata)}. "
                    f"Verlaag de verwachte fout of verhoog de materialiteit."
                )

        # Bereken de totale geldswaarde van de populatie en
        # de bekende fout in geld in de hoogstrata en de
        # totale verwachte fout in de laagstrata.
        totale_pop_waarde = (
            steekproeven["waarde_laag"] + steekproeven["waarde_hoog"]
        ).sum()
        totale_fout_hoog = steekproeven["fout_hoog"].sum()
        totale_verwachte_fout_laag = (
            steekproeven["verwachte_foutfractie"] * steekproeven["waarde_laag"]
        ).sum()

        # Werp een fout op als de bekende fout in geld in
        # de hoogstrata de algehele materialiteitsgrens in geld overschrijdt.
        if totale_fout_hoog > materialiteit * totale_pop_waarde:
            raise ValueError(
                "Bekende fout in de hoogstrata overschrijdt alleen al de algehele materialiteit."
            )

        # Werp een fout op als de totale verwachte fout in geld in de laagstrata
        # de algehele materialiteit in geld overschrijdt.
        if totale_verwachte_fout_laag > materialiteit * totale_pop_waarde:
            raise ValueError(
                "Totale verwachte fout in de laagstrata alleen al overschrijdt de algehele materialiteit."
            )

        # Werp een fout op als:
        # - de totale verwachte fout in geld in de laagstrata, plus
        # - de totale bekende fout in geld in de hoogstrata
        # de algehele materialiteit in geld overschrijdt.
        if (
            totale_verwachte_fout_laag + totale_fout_hoog
            > materialiteit * totale_pop_waarde
        ):
            raise ValueError(
                "Totale verwachte fout in de laagstrata plus fout in de hoogstrata "
                "overschrijdt de algehele materialiteit."
            )

        # Voorkom deling door nul bij extreme gewichtsverschillen tussen strata.
        # Voer de granulariteitscontrole uit als er ten minste één geldig laagstratum is.
        laag_strata = steekproeven[steekproeven["waarde_laag"] > 0]
        if not laag_strata.empty:
            min_waarde_laag = laag_strata["waarde_laag"].min()
            totaal_waarde_laag = laag_strata["waarde_laag"].sum()

            # Bereken de theoretische rasterstap van de FFT.
            dx = totaal_waarde_laag / granulariteit

            # Werp een fout op als de rasterstap groter is dan of gelijk is aan het kleinste stratum.
            if dx >= min_waarde_laag:
                # Bereken de minimaal benodigde granulariteit door naar boven af te ronden.
                min_benodigde_gran = math.ceil(
                    (totaal_waarde_laag / min_waarde_laag) * 10
                )

                raise ValueError(
                    f"De granulariteit ({granulariteit}) is te laag ten opzichte van het kleinste "
                    f"stratum (waarde: {min_waarde_laag}). De berekening zou hierdoor crashen. "
                    f"Verhoog de granulariteit naar minimaal {min_benodigde_gran}."
                )

    # Bereken de initiële basissteekproefomvang op basis van de invoerdata.
    strata = plan_stratified_basis(steekproeven, model=model)

    # Bereken de initiële algehele convolutiefout van de startpositie.
    huidige_fout = eval_stratified(
        strata,
        model=model,
        zekerheid=zekerheid,
        methode="FFT samen",
        granulariteit=granulariteit,
        vergelijk=False,
    )["max_fout_convolutie"]

    # Start de stapsgewijze klimlus totdat de fout onder de gestelde materialiteit zakt.
    iteratie = 0
    while huidige_fout > materialiteit and iteratie < 10000:
        iteratie += 1
        beste_strata_indices = vind_beste_strata_groep(
            strata,
            model=model,
            klim_granulariteit=granulariteit,
            totale_zekerheid=zekerheid,
        )

        # Hoog de geselecteerde strata parallel op met één post.
        for beste_stratum in beste_strata_indices:
            # Vertaal positie-index naar het daadwerkelijke DataFrame-label
            rij_label = strata.index[beste_stratum]

            # Hoog 1 op.
            strata.at[rij_label, "n_laag"] += 1
            strata.at[rij_label, "k_laag"] = (
                strata.at[rij_label, "n_laag"]
                * strata.at[rij_label, "verwachte_foutfractie"]
            )

        # Evalueer de nieuwe algehele fout na de parallelle ophoogstap.
        huidige_fout = eval_stratified(
            strata,
            model=model,
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=granulariteit,
            vergelijk=False,
        )["max_fout_convolutie"]

    strata.attrs["geplande_max_fout_totaal"] = huidige_fout

    return strata


def plan_stratified_basis(
    steekproeven: pd.DataFrame, model: str = "binomiaal"
) -> pd.DataFrame:
    """
    Plan de initiële steekproefomvang.

    Deze functie berekent het minimaal aantal benodigde steken per stratum om
    onder de eigen stratum-materialiteit te blijven.
    Teruggegeven wordt het steekproeven pandas DataFrame aangevuld met de startwaarden,
    dus het aantal steken per individueel stratum, voor het klimalgoritme.
    """
    # Valideer het gekozen model en converteer naar de juiste Engelse distributieterm.
    if model not in ["binomiaal", "poisson"]:
        raise ValueError("Model moet 'binomiaal' of 'poisson' zijn.")
    dist_eng = "binomial" if model == "binomiaal" else "Poisson"

    # Maak een kopie om waarschuwingen (SettingWithCopyWarning) van Pandas te voorkomen.
    strata = steekproeven.copy()

    strata["waarde_populatie"] = strata["waarde_laag"] + strata["waarde_hoog"]

    # Wiskundig zuiver: bereken het daadwerkelijke foutbudget voor het laagstratum.
    strata["materialiteit_in_geld"] = (
        strata["materialiteit"] * strata["waarde_populatie"]
    ) - strata["fout_hoog"]

    strata["materialiteit_laag"] = None
    strata["n_basis"] = 0

    masker = strata["waarde_laag"] > 0

    if masker.any():
        strata.loc[masker, "materialiteit_laag"] = (
            strata.loc[masker, "materialiteit_in_geld"]
            / strata.loc[masker, "waarde_laag"]
        )

        # Bereken n_basis uitsluitend op basis van de omgerekende materialiteit_laag.
        strata.loc[masker, "n_basis"] = np.ceil(
            strata.loc[masker].apply(
                lambda row: drawsneeded(
                    posited_defect_rate=row["verwachte_foutfractie"],
                    allowed_defect_rate=row["materialiteit_laag"],
                    cert=haro_nog_nodige_zekerheid(row["ihr"], row["ibr"], row["car"]),
                    distribution=dist_eng,
                ),
                axis=1,
            )
        )

    # Forceer de datatypes netjes naar integers.
    strata["n_basis"] = strata["n_basis"].astype(int)

    # Initialiseer de startwaarden voor het klimalgoritme uit de basisomvang.
    strata["n_laag"] = strata["n_basis"]
    strata["k_laag"] = strata["n_laag"] * strata["verwachte_foutfractie"]

    return strata


def vind_beste_strata_groep(
    huidige_strata: pd.DataFrame,
    model: str,
    klim_granulariteit: int = 1000000,
    totale_zekerheid: float = 0.95,
) -> list:
    """
    Evalueer en selecteer de optimale strata voor de volgende parallelle klimstap.

    Deze functie berekent via convolutie welke strata bij een ophoging van
    1 post de grootste foutreductie PER KOSTENEENHEID opleveren.
    Teruggegeven wordt een selectie van rijen uit huidige_strata pandas DataFrame.
    """

    # Definieer de interne functie voor de gelijktijdige FFT convolutie-evaluatie.
    def calc_max_fout_klim(s_data):
        res = eval_stratified(
            steekproeven=s_data,
            model=model,
            zekerheid=totale_zekerheid,
            methode="FFT samen",
            granulariteit=klim_granulariteit,
            vergelijk=False,
        )
        return res["max_fout_convolutie"]

    # Initialiseer de nulmeting van de kanskromme en bepaal het aantal strata.
    huidige_fout_klim = calc_max_fout_klim(huidige_strata)
    n_strata = len(huidige_strata)

    # Bereken voor een ophoog van 1 de kostengecorrigeerde verbetering.
    verbetering = np.zeros(n_strata)
    for i in range(n_strata):
        test_strata = huidige_strata.copy()

        # Haal het juiste rijlabel op om veilig te indexeren met .at.
        rij_label = test_strata.index[i]

        test_strata.at[rij_label, "n_laag"] += 1
        test_strata.at[rij_label, "k_laag"] = (
            test_strata.at[rij_label, "n_laag"]
            * test_strata.at[rij_label, "verwachte_foutfractie"]
        )

        nieuwe_fout = calc_max_fout_klim(test_strata)
        foutreductie = huidige_fout_klim - nieuwe_fout

        # Vang numerieke artefacten af die ontstaan door zwevendekommagetallen of interpolatie.
        if foutreductie < 0:
            foutreductie = 0

        # Deel de absolute foutreductie door de uitvoeringskosten van deze steek.
        kosten_steek = test_strata.at[rij_label, "kosten"]
        verbetering[i] = foutreductie / kosten_steek

    # Bepaal welke strata het maximale rendement opleveren.
    max_verbetering = np.max(verbetering)
    if max_verbetering > 0:
        # Gebruik een minieme tolerantie om afrondingsverschillen op te vangen.
        beste_strata = np.where(verbetering >= max_verbetering - 1e-12)[0].tolist()
    else:
        # Dit kan eigenlijk niet voorkomen.
        # Maar veiligheidshalve:
        # val terug op de analytische proxy (ook deze corrigeren we voor kosten).
        warnings.warn(
            "We vallen terug op de analytische proxy.", RuntimeWarning, stacklevel=2
        )
        veilige_n = np.maximum(huidige_strata["n_laag"], 1)
        proxy_onzekerheid = (
            huidige_strata["waarde_laag"] / np.sqrt(veilige_n)
        ) / huidige_strata["kosten"]
        max_proxy = np.max(proxy_onzekerheid)
        beste_strata = np.where(proxy_onzekerheid >= max_proxy - 1e-6)[0].tolist()

    return beste_strata
