"""
Planningsfuncties van auditstratified.
Hoofdfunctie is plan_stratified().
"""

__all__ = ["plan_stratified", "plan_stratified_basis", "vind_beste_strata_groep"]

import numpy as np
import pandas as pd

# Importeer de benodigde wiskundige rekenmotoren uit de andere pakket-bestanden.
from auditstratified.eval_stratified import eval_stratified
from auditstratified.utils import drawsneeded, haro_nog_nodige_zekerheid


def plan_stratified(
    steekproeven: pd.DataFrame,
    model: str = "binomiaal",
    materialiteit: float = None,
    zekerheid: float = 0.95,
    granulariteit: int = 10000,
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
        Het invoer-DataFrame aangevuld met kolommen ``n_laag``, ``k_laag``,
        ``n_basis``, ``kosten`` en ``waarde_populatie``.
        Het attribuut ``geplande_max_fout_totaal`` bevat de bereikte convolutiefout.

    Raises
    ------
    ValueError

        Als er dubbele stratumnamen worden opgegeven.
        Als er strata zijn waar de verwachte foutfractie >= de materialiteit van dat stratum.
        Als de totale bekende fout in de hoogstrata de algehele materialiteit overschrijdt.
        Als de totale verwachte fout in de laagstrata de algehele materialiteit overschrijdt.
        Als de totale bekende fout in de hoogstrata plus de verwachte fout
        in de laagstrata samen de algehele materialiteit overschrijdt.


    """
    INVOER_CONTROLE = True  # Niet op False zetten, tenzij je de controles,
    # met name, die ValueErrors kunnen geven,
    # buiten de functieaanroep overdoet!

    # Controleer de waarden van de parameters van de functie.
    if INVOER_CONTROLE:
        # Valideer steekproeven.
        assert isinstance(steekproeven, pd.DataFrame), (
            "steekproeven moet een pandas DataFrame zijn."
        )
        if len(steekproeven) == 0:
            raise ValueError("steekproeven is leeg: moet tenminste 1 stratum bevatten.")

        # Controle op vereiste kolommen in steekproeven.
        vereiste_kolommen = {
            "naam",
            "waarde_laag",
            "verwachte_foutfractie",
            "ibr",
            "car",
            "kosten",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        }
        ontbrekend = vereiste_kolommen - set(steekproeven.columns)
        assert not ontbrekend, f"Ontbrekende kolommen: {', '.join(sorted(ontbrekend))}"

        # Controle op dubbele stratumnamen.
        if steekproeven["naam"].duplicated().any():
            dubbele = steekproeven[steekproeven["naam"].duplicated()]["naam"].unique()
            raise ValueError(
                f"Evaluatiefout: De volgende stratumnamen komen vaker dan één keer voor: {', '.join(dubbele)}"
            )

        # Valideer het model.
        assert model in ["binomiaal", "poisson"], (
            "Model moet 'binomiaal' of 'poisson' zijn."
        )

        # Valideer de materialiteit.
        assert not isinstance(materialiteit, bool), (
            "Materialiteit mag geen boolean zijn, maar moet een getal van 0 tot 1 zijn."
        )
        assert isinstance(materialiteit, (int, float)), (
            "Materialiteit moet een getal zijn. (Namelijk, een element van het segment [0, 1].)"
        )
        assert materialiteit >= 0, (
            "Materialiteit moet >= 0 zijn. (En liggen op het segment [0, 1].)"
        )
        assert materialiteit <= 1, (
            "Materialiteit moet <= 1 zijn. (En liggen op het segment [0, 1].)"
        )

        # Valideer de zekerheid.
        assert not isinstance(zekerheid, bool), (
            "Zekerheid mag geen boolean zijn, maar moet een getal van 0 tot 1 zijn."
        )
        assert isinstance(zekerheid, (int, float)), (
            "Zekerheid moet een getal zijn. (Namelijk, een element van het segment [0, 1].)"
        )
        assert zekerheid >= 0, (
            "Zekerheid moet >= 0 zijn. (En liggen op het segment [0, 1].)"
        )
        assert zekerheid <= 1, (
            "Zekerheid moet <= 1 zijn. (En liggen op het segment [0, 1].)"
        )

        # Valideer de granulariteit.
        assert not isinstance(granulariteit, bool), (
            "Granulariteit mag geen boolean zijn, maar moet een geheel, positief getal zijn."
        )
        assert isinstance(granulariteit, int), (
            "Granulariteit moet een geheel getal zijn. En positief bovendien."
        )
        assert granulariteit >= 0, "Granulariteit moet >= 0 zijn. En geheel bovendien."

        # Controleer op dubbele stratumnamen in de invoertabel.
        if steekproeven["naam"].duplicated().any():
            dubbele_naam = steekproeven[steekproeven["naam"].duplicated()]["naam"].iloc[
                0
            ]
            raise ValueError(f"Namen komen vaker dan 1 keer voor: {dubbele_naam}")

        # Controleer op stratuminconsistentie waarbij de verwachte foutfractie
        # in een laagstratum >= de stratummaterialiteit.
        probleem_strata = steekproeven.loc[
            steekproeven["verwachte_foutfractie"] >= steekproeven["materialiteit"],
            "naam",
        ].tolist()
        if probleem_strata:
            raise ValueError(
                f"Verwachte foutfractie >= de stratummaterialiteit in: {', '.join(probleem_strata)}"
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

    # Controleer of uitvoeringskosten zijn meegegeven; zo niet, hanteer een neutrale waarde van 1.0.
    if "kosten" not in strata.columns:
        strata["kosten"] = 1.0

    # Bereken n_basis en neem de berekening van 'cert' inline op.
    strata["n_basis"] = np.ceil(
        strata.apply(
            lambda row: drawsneeded(
                posited_defect_rate=row["verwachte_foutfractie"],
                allowed_defect_rate=row["materialiteit"],
                cert=haro_nog_nodige_zekerheid(row["ihr"], row["ibr"], row["car"]),
                distribution=dist_eng,
            ),
            axis=1,
        )
    ).astype(int)

    # Initialiseer de startwaarden voor het klimalgoritme uit de basisomvang.
    strata["n_laag"] = strata["n_basis"]
    strata["k_laag"] = strata["n_laag"] * strata["verwachte_foutfractie"]
    strata["waarde_populatie"] = strata["waarde_laag"] + strata["waarde_hoog"]

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
        print("We vallen terug op de analytische proxy.")
        veilige_n = np.maximum(huidige_strata["n_laag"], 1)
        proxy_onzekerheid = (
            huidige_strata["waarde_laag"] / np.sqrt(veilige_n)
        ) / huidige_strata["kosten"]
        max_proxy = np.max(proxy_onzekerheid)
        beste_strata = np.where(proxy_onzekerheid >= max_proxy - 1e-6)[0].tolist()

    return beste_strata
