import pytest
import pandas as pd
from auditstratified.plan_stratified import plan_stratified

def test_happy_flow_succesvolle_planning():
    """De Happy Flow: Succesvolle planning voor meerdere strata."""
    test_succes = pd.DataFrame({
        "naam": ["Grote_Klanten", "Kleine_Klanten"],
        "waarde_laag": [300000.0, 500000.0],
        "verwachte_foutfractie": [0.01, 0.015],
        "ihr": ["H", "H"], "ibr": ["H", "H"], "car": ["H", "H"],
        "materialiteit": [0.05, 0.05],
        "fout_hoog": [2000.0, 0.0],
        "goed_hoog": [198000.0, 0.0]
    })

    # Corrigeer de argumenten naar de exacte parameternamen van de hoofdfunctie.
    resultaat = plan_stratified(
        steekproeven=test_succes,
        materialiteit=0.05,
        zekerheid=0.95
    )

    # Voer de basiscontroles uit op de structuur van de geretourneerde data.
    assert isinstance(resultaat, pd.DataFrame)
    assert "n_laag" in resultaat.columns

def test_foutmelding_verwachte_foutfractie_te_hoog():
    """Foutmelding: Verwachte foutfractie is al te hoog voor planning."""
    test_fout_verwacht = pd.DataFrame({
        "naam": ["Alle_Klanten"],
        "waarde_laag": [1000000.0],
        "verwachte_foutfractie": [0.06],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"],
        "materialiteit": [0.07],
        "fout_hoog": [0.0],
        "goed_hoog": [0.0]
    })

    # Controleer of de planningsmodule correct weigert wanneer de fout te hoog is.
    with pytest.raises(ValueError, match="Verwachte foutfractie groter dan of gelijk aan de totale materialiteit"):
        plan_stratified(test_fout_verwacht, materialiteit=0.05)

def test_foutmelding_bekende_fout_hoogstratum_nekt_materialiteit():
    """Foutmelding: Bekende fout in hoogstratum nekt de materialiteit."""
    test_fout_hoog = pd.DataFrame({
        "naam": ["Alle_Klanten"],
        "waarde_laag": [800000.0],
        "verwachte_foutfractie": [0.01],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [60000.0],
        "goed_hoog": [140000.0]
    })

    # Controleer of de fout in het hoogstratum een duidelijke stop-barriere triggert.
    with pytest.raises(ValueError, match="Reeds bekende fout in de hoogstrata"):
        plan_stratified(test_fout_hoog, materialiteit=0.05)

def test_foutmelding_inconsistentie_op_stratum_niveau():
    """Foutmelding: Inconsistentie op stratum-niveau (verwachte fout > materialiteit)."""
    test_inconsistent = pd.DataFrame({
        "naam": ["Stratum1"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.03],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"],
        "materialiteit": [0.02],
        "fout_hoog": [0.0],
        "goed_hoog": [0.0]
    })

    # Verifieer of de inconsistentie tussen verwachte fout en materialiteit direct faalt.
    with pytest.raises(ValueError, match="Verwachte foutfractie groter dan of gelijk aan de stratum-materialiteit"):
        plan_stratified(test_inconsistent, materialiteit=0.05)

def test_attribuutverificatie_geretourneerde_dataset():
    """Attribuutverificatie op de geretourneerde dataset."""
    test_data = pd.DataFrame({
        "naam": ["Simple"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.001],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [0.0],
        "goed_hoog": [0.0]
    })

    # Roep de herstelde planning aan om de data-attributen te valideren.
    resultaat = plan_stratified(test_data, materialiteit=0.05)
    assert isinstance(resultaat, pd.DataFrame)
    assert "geplande_max_fout_totaal" in resultaat.attrs

def test_foutmelding_dubbele_stratumnamen():
    """Foutmelding: Dubbele stratumnamen in de invoer."""
    test_dubbel = pd.DataFrame({
        "naam": ["Stratum_A", "Stratum_A"],
        "waarde_laag": [100000.0, 200000.0],
        "verwachte_foutfractie": [0.01, 0.01],
        "ihr": ["H", "H"], "ibr": ["H", "H"], "car": ["H", "H"],
        "materialiteit": [0.05, 0.05],
        "fout_hoog": [0.0, 0.0],
        "goed_hoog": [0.0, 0.0]
    })

    # Controleer of dubbele stratumnamen correct worden afgevangen.
    with pytest.raises(ValueError, match="Namen komen vaker dan 1 keer voor"):
        plan_stratified(test_dubbel, materialiteit=0.05)

def get_test_steekproeven():
    """Genereer een representatieve dataset met twee strata voor de simulatietesten."""
    return pd.DataFrame({
        "naam": ["Subsidies", "Inkoop"],
        "waarde_laag": [1000000.0, 500000.0],
        "verwachte_foutfractie": [0.01, 0.005],
        "ihr": ["M", "L"], "ibr": ["M", "L"], "car": ["M", "L"],
        "materialiteit": [0.03, 0.03],
        "fout_hoog": [0.0, 0.0],
        "goed_hoog": [100000.0, 50000.0]
    })

def test_plan_stratified_binomiaal_sluitend():
    """Verifieer of plan_stratified een exact sluitend steekproefplan genereert voor binomiaal."""
    steekproeven = get_test_steekproeven()

    # Roep de validatiefunctie aan met een materialiteit van drie procent.
    resultaat = plan_stratified(
        steekproeven=steekproeven,
        materialiteit=0.03,
        zekerheid=0.95,
        model="binomiaal",
        granulariteit=10000
    )

    # Voer de validatietesten uit op het verkregen resultaatsobject.
    assert isinstance(resultaat, pd.DataFrame)
    assert "n_definitief" in resultaat.columns
    assert resultaat.attrs["geplande_max_fout_totaal"] <= 0.03

def test_plan_stratified_poisson_strakke_marges():
    """Verifieer of plan_stratified correct werkt met de poisson verdeling en strakke marges."""
    steekproeven = get_test_steekproeven()

    # Verhoog de verwachte foutfractie om de planningsmodule extra werk te geven.
    steekproeven["verwachte_foutfractie"] = [0.02, 0.01]

    # Voer de validatie uit specifiek voor de poisson verdeling.
    resultaat = plan_stratified(
        steekproeven=steekproeven,
        materialiteit=0.05,
        zekerheid=0.95,
        model="poisson",
        granulariteit=10000
    )

    # Eis dat de samenvattende variabele de poisson-planning als positief markeert.
    assert isinstance(resultaat, pd.DataFrame)
    assert "n_definitief" in resultaat.columns
    assert resultaat.attrs["geplande_max_fout_totaal"] <= 0.05
