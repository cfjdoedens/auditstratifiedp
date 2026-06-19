import pandas as pd
import numpy as np

# Importeer de benodigde wiskundige rekenmotoren uit de andere pakket-bestanden.
from auditstratified.eval_stratified import eval_stratified
from auditstratified.utils import haro_nog_nodige_zekerheid, drawsneeded

def plan_stratified_basis(steekproeven: pd.DataFrame, model: str = "binomiaal") -> pd.DataFrame:
    """
    Plan de initiële basissteekproefomvang (Stap 1).
    
    Deze functie berekent de minimale uitgangssituatie per stratum om
    afzonderlijk onder de eigen stratum-materialiteit te blijven.
    """
    # Valideer het gekozen model en converteer naar de juiste Engelse distributieterm.
    if model not in ["binomiaal", "poisson"]:
        raise ValueError("Model moet 'binomiaal' of 'poisson' zijn.")
    dist_eng = "binomial" if model == "binomiaal" else "Poisson"

    # Maak een kopie om waarschuwingen (SettingWithCopyWarning) van Pandas te voorkomen.
    strata = steekproeven.copy()

    # Bereken per stratum de HARo-zekerheid en de daaruit voortvloeiende minimale n_basis.
    strata['cert'] = strata.apply(
        lambda row: haro_nog_nodige_zekerheid(row['ihr'], row['ibr'], row['car']), axis=1
    )
    strata['n_basis'] = np.ceil(strata.apply(
        lambda row: drawsneeded(
            posited_defect_rate=row['verwachte_foutfractie'],
            allowed_defect_rate=row['materialiteit'],
            cert=row['cert'],
            distribution=dist_eng
        ), axis=1
    )).astype(int)

    # Initialiseer de startwaarden voor het klimalgoritme op basis van de basisomvang.
    strata['n_laag'] = strata['n_basis']
    strata['k_laag'] = strata['n_laag'] * strata['verwachte_foutfractie']
    strata['waarde_hoog'] = strata['fout_hoog'] + strata['goed_hoog']
    strata['waarde_populatie'] = strata['waarde_laag'] + strata['waarde_hoog']

    # Schoon de tijdelijke zekerheidskolom op alvorens de tabel te retourneren.
    strata = strata.drop(columns=['cert'])
    
    return strata

def vind_beste_strata_groep(huidige_strata: pd.DataFrame, model: str, klim_granulariteit: int = 1000000, totale_zekerheid: float = 0.95) -> list:
    """
    Evalueer en selecteer de optimale strata voor de volgende parallelle klimstap.
    
    Deze functie berekent via exacte convolutie welke strata bij een ophoging van
    exact 1 post de grootste foutreductie opleveren. Omdat max_fout continu is,
    geeft de kleinste ophoogstap direct het optimale sturingssignaal.
    """
    # Definieer de interne functie voor de gelijktijdige FFT convolutie-evaluatie.
    def calc_max_fout_klim(s_data):
        res = eval_stratified(
            steekproeven=s_data,
            model=model,
            zekerheid=totale_zekerheid,
            methode="FFT samen",
            granulariteit=klim_granulariteit,
            vergelijk=False
        )
        return res['max_fout_convolutie']

    # Initialiseer de nulmeting van de kanskromme en bepaal het aantal strata.
    huidige_fout_klim = calc_max_fout_klim(huidige_strata)
    n_strata = len(huidige_strata)

    # Bereken voor een ophoog van exact 1 de verbetering van de maximale fout per stratum.
    verbetering = np.zeros(n_strata)
    for i in range(n_strata):
        test_strata = huidige_strata.copy()
        
        # In Pandas gebruiken we .at voor veilige aanpassing van individuele cellen.
        test_strata.at[i, 'n_laag'] += 1
        test_strata.at[i, 'k_laag'] = test_strata.at[i, 'n_laag'] * test_strata.at[i, 'verwachte_foutfractie']
        
        nieuwe_fout = calc_max_fout_klim(test_strata)
        foutreductie = huidige_fout_klim - nieuwe_fout
        
        # Vang numerieke artefacten af die ontstaan door zwevendekommagetallen of interpolatie op grove grids.
        if foutreductie < 0:
            foutreductie = 0
            
        verbetering[i] = foutreductie

    # Bepaal wiskundig welke strata het maximale rendement opleveren voor deze ene stap.
    max_verbetering = np.max(verbetering)
    if max_verbetering > 0:
        # We gebruiken een minieme tolerantie om afrondingsverschillen bij exact gelijk presterende strata op te vangen.
        beste_strata = np.where(verbetering >= max_verbetering - 1e-12)[0].tolist()
    else:
        # Vang het fenomeen af waarbij een extreem grof grid blind is voor kleine verbeteringen.
        # Val terug op een analytische proxy: het stratum dat relatief de meeste onzekerheid toevoegt.
        veilige_n = np.maximum(huidige_strata['n_laag'], 1)
        proxy_onzekerheid = huidige_strata['waarde_laag'] / np.sqrt(veilige_n)
        
        # Selecteer het stratum met de hoogste proxy-waarde.
        max_proxy = np.max(proxy_onzekerheid)
        beste_strata = np.where(proxy_onzekerheid >= max_proxy - 1e-6)[0].tolist()

    return beste_strata

def plan_stratified(steekproeven: pd.DataFrame, model: str = "binomiaal", materialiteit: float = None, zekerheid: float = 0.95, granulariteit: int = 10000, **kwargs) -> pd.DataFrame:
    """
    Plan de volledige optimale steekproefverdeling via parallelle convolutie-optimalisatie.
    
    Deze functie voert de volledige planningscyclus uit: het start met de basisomvang
    en verhoogt daarna stapsgewijs de omvang van de meest effectieve strata totdat
    de gecombineerde convolutiefout onder de algehele materialiteit zakt.
    """
    # Vang variaties in argumentnamen op die door testscripts of wrappers gebruikt worden.
    if materialiteit is None and 'totale_materialiteit' in kwargs:
        materialiteit = kwargs['totale_materialiteit']
    if 'totale_zekerheid' in kwargs:
        zekerheid = kwargs['totale_zekerheid']

    # Controleer vooraf op dubbele stratumnamen in de invoertabel.
    if steekproeven['naam'].duplicated().any():
        dubbele_naam = steekproeven[steekproeven['naam'].duplicated()]['naam'].iloc[0]
        raise ValueError(f"Namen komen vaker dan 1 keer voor: {dubbele_naam}")

    # Valideer vooraf of er individuele strata zijn waar de verwachte foutfractie de materialiteit al overschrijdt.
    if (steekproeven['verwachte_foutfractie'] >= materialiteit).any():
        raise ValueError("Verwachte foutfractie groter dan of gelijk aan de totale materialiteit")

    # Controleer op stratum-inconsistentie waarbij de verwachte foutfractie groter of gelijk is aan de stratum-materialiteit.
    if (steekproeven['verwachte_foutfractie'] >= steekproeven['materialiteit']).any():
        raise ValueError("Verwachte foutfractie groter dan of gelijk aan de stratum-materialiteit")

    # Valideer de modelkeuze en bereken de initiële basissteekproefomvang op basis van de invoerdata.
    strata = plan_stratified_basis(steekproeven, model=model)

    # Bereken de totale geldswaarde van de populatie en de absolute bekende fout binnen het hoogstratum.
    totale_pop_waarde = strata['waarde_populatie'].sum()
    totale_fout_hoog = strata['fout_hoog'].sum()

    # Werp een fout op als de bekende fout in het hoogstratum de algehele materialiteitsgrens al overschrijdt.
    if totale_pop_waarde > 0 and (totale_fout_hoog / totale_pop_waarde) >= materialiteit:
        raise ValueError("Reeds bekende fout in de hoogstrata")

    # Bereken de initiële algehele convolutiefout van de startpositie.
    huidige_fout = eval_stratified(
        strata,
        model=model,
        zekerheid=zekerheid,
        methode="FFT samen",
        granulariteit=granulariteit,
        vergelijk=False
    )['max_fout_convolutie']

    # Start de stapsgewijze klimloop totdat de fout onder de gestelde materialiteit zakt (met een ruime veiligheidsmarge tegen oneindige loops).
    iteratie = 0
    while huidige_fout > materialiteit and iteratie < 10000:
        iteratie += 1
        beste_strata_indices = vind_beste_strata_groep(
            strata,
            model=model,
            klim_granulariteit=granulariteit,
            totale_zekerheid=zekerheid
        )

        # Hoog de geselecteerde strata parallel op met één post.
        for beste_stratum in beste_strata_indices:
            strata.at[beste_stratum, 'n_laag'] += 1
            strata.at[beste_stratum, 'k_laag'] = strata.at[beste_stratum, 'n_laag'] * strata.at[beste_stratum, 'verwachte_foutfractie']

        # Evalueer de nieuwe algehele fout na de parallelle ophoogstap.
        huidige_fout = eval_stratified(
            strata,
            model=model,
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=granulariteit,
            vergelijk=False
        )['max_fout_convolutie']

    # Voeg de door het testscript verwachte synoniemkolom n_definitief en het kwaliteitsattribuut toe.
    strata['n_definitief'] = strata['n_laag']
    strata.attrs['geplande_max_fout_totaal'] = huidige_fout

    return strata
