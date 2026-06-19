import pytest
import math
import numpy as np
import pandas as pd
from auditstratified.eval_stratified import eval_stratified

def test_voorbeeld_paul_van_batenburg():
    """Test op basis van het voorbeeld van Paul van Batenburg."""
    vb_paul = pd.DataFrame({
        "naam": ["populatie1", "populatie2"],
        "waarde_laag": [1000000.0, 1000000.0],
        "n_laag": [512, 106],
        "k_laag": [1.0, 2.0],
        "ihr": ["H", "H"], "ibr": ["H", "H"], "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0], "fout_hoog": [0.0, 0.0]
    })
    r = eval_stratified(vb_paul, zekerheid=0.95, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.0310, abs_tol=1e-3)

def test_uitleg_samennemen_beschrijving():
    """Uitleg over samennemen van steekproeven met verschillende risico-inschattingen."""
    example = pd.DataFrame({
        "naam": ["populatie1", "populatie2"],
        "waarde_laag": [100000000.0, 100000000.0],
        "n_laag": [148, 50],
        "k_laag": [1.0, 0.0],
        "ihr": ["H", "L"], "ibr": ["H", "L"], "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0], "fout_hoog": [0.0, 0.0]
    })
    r = eval_stratified(example, zekerheid=0.95, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.0184, abs_tol=1e-3)

def test_voorbeelden_niels_van_leeuwen():
    """Uitgebreide voorbeelden voor Niels van Leeuwen met diverse zekerheidsniveaus."""
    sniels = pd.DataFrame({
        "naam": ["x", "y"],
        "waarde_laag": [100.0, 200.0],
        "n_laag": [300, 160],
        "k_laag": [0.0, 0.0],
        "ihr": ["H", "H"], "ibr": ["H", "H"], "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0], "fout_hoog": [0.0, 0.0]
    })

    # Test 95%
    r = eval_stratified(sniels, zekerheid=0.95, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.0136, abs_tol=1e-3)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.0156, abs_tol=1e-3)

    # Test 90%
    r = eval_stratified(sniels, zekerheid=0.90, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.0108, abs_tol=1e-3)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.0120, abs_tol=1e-3)

    # Test 55%
    r = eval_stratified(sniels, zekerheid=0.55, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.004510, abs_tol=1e-4)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.00418, abs_tol=1e-4)

    # Test 10% (Hier is convolutie voor het eerst groter dan los)
    r = eval_stratified(sniels, zekerheid=0.10, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.00118, abs_tol=1e-4)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.000553, abs_tol=1e-5)

def test_drie_dezelfde_steekproeven():
    """Evaluatie van drie exact gelijke steekproeven."""
    dezelfde_drie = pd.DataFrame({
        "naam": ["s1", "s2", "s3"],
        "waarde_laag": [10.0] * 3,
        "n_laag": [10] * 3,
        "k_laag": [0.0] * 3,
        "ihr": ["H"] * 3, "ibr": ["H"] * 3, "car": ["H"] * 3,
        "materialiteit": [0.01] * 3,
        "waarde_hoog": [0.0] * 3, "fout_hoog": [0.0] * 3
    })
    r = eval_stratified(dezelfde_drie, zekerheid=0.60, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.088, abs_tol=1e-3)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.0799, abs_tol=1e-3)

def test_tweeendertig_dezelfde_steekproeven():
    """Stress-test: evaluatie van 32 exact gelijke steekproeven (vectorized opbouw)."""
    dezelfde_32 = pd.DataFrame({
        "naam": [f"s{i}" for i in range(1, 33)],
        "waarde_laag": [10.0] * 32,
        "n_laag": [10] * 32,
        "k_laag": [0.0] * 32,
        "ihr": ["H"] * 32, "ibr": ["H"] * 32, "car": ["H"] * 32,
        "materialiteit": [0.01] * 32,
        "waarde_hoog": [0.0] * 32, "fout_hoog": [0.0] * 32
    })
    
    # 51% Zekerheid
    r = eval_stratified(dezelfde_32, zekerheid=0.51, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.0830, abs_tol=1e-3)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.0628, abs_tol=1e-3)
    
    # 95% Zekerheid
    r = eval_stratified(dezelfde_32, zekerheid=0.95, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.106, abs_tol=1e-3)
    assert math.isclose(r["vergelijk_met"]["max_fout_los"], 0.238, abs_tol=1e-3)

def test_lnv_2023_wim_slot():
    """Praktijkcase LNV 2023 (Wim Slot)."""
    lnv_2023 = pd.DataFrame({
        "naam": ["kd_beleid", "lbv", "inkopen"],
        "waarde_laag": [69600741.0, 223532422.0, 12146914.0],
        "n_laag": [8, 22, 1],
        "k_laag": [0.0, 0.0331905, 0.0],
        "ihr": ["H", "H", "H"], "ibr": ["H", "H", "H"], "car": ["H", "H", "H"],
        "materialiteit": [0.01, 0.01, 0.01],
        "waarde_hoog": [0.0, 0.0, 0.0], "fout_hoog": [0.0, 0.0, 0.0]
    })

    r = eval_stratified(lnv_2023, zekerheid=0.95, methode="FFT samen", granulariteit=100000)
    assert math.isclose(r["max_fout_convolutie"], 0.139, abs_tol=1e-3)
    assert math.isclose(r["max_fout_convolutie_geld"], 42394460, abs_tol=50.0) # Kleine afrondingstolerantie op grote bedragen

def test_evaluatie_met_hoogstratum():
    """Evaluatie met een 100%-getoetst topstratum inclusief redundantie."""
    test_top = pd.DataFrame({
        "naam": ["stratum_met_top"],
        "waarde_laag": [500000.0],
        "n_laag": [100],
        "k_laag": [1.0],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"],
        "materialiteit": [0.01],
        "waarde_hoog": [100000.0],
        "fout_hoog": [10000.0]
    })
    
    r_fft = eval_stratified(test_top, zekerheid=0.95, methode="FFT paarsgewijs")
    assert math.isclose(r_fft["mw_fout_convolutie_geld"], 15000, abs_tol=10.0)

def test_fft_vs_monte_carlo():
    """Controleer of FFT en Monte Carlo nagenoeg dezelfde uitkomsten geven."""
    sniels = pd.DataFrame({
        "naam": ["x", "y"],
        "waarde_laag": [100.0, 200.0],
        "n_laag": [300, 160],
        "k_laag": [0.0, 0.0],
        "ihr": ["H", "H"], "ibr": ["H", "H"], "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0], "fout_hoog": [0.0, 0.0]
    })

    r_mc = eval_stratified(sniels, zekerheid=0.95, methode="Monte Carlo", granulariteit=100000, start=1)
    r_fft = eval_stratified(sniels, zekerheid=0.95, methode="FFT paarsgewijs", granulariteit=10000)

    # De resultaten mogen een klein beetje ruis hebben vanwege de Monte Carlo benadering
    assert math.isclose(r_fft["max_fout_convolutie"], r_mc["max_fout_convolutie"], abs_tol=0.015)

def test_effect_hoogstratum_toevoeging():
    """Controleer effect van toevoegen van posten uit het hoogstratum."""
    a = pd.DataFrame({
        "naam": ["x"], "waarde_laag": [1000.0], "n_laag": [300], "k_laag": [0.0],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"], "materialiteit": [0.01],
        "waarde_hoog": [1000.0], "fout_hoog": [0.0]
    })
    b = a.copy()
    b.loc[0, "fout_hoog"] = 1000.0

    ra = eval_stratified(a, methode="FFT samen", vergelijk=False)
    rb = eval_stratified(b, methode="FFT samen", vergelijk=False)

    assert ra["max_fout_convolutie"] < rb["max_fout_convolutie"]
    
    verwacht_verschil = (1000.0 - 0.0) / (1000.0 + 1000.0)
    werkelijk_verschil = rb["max_fout_convolutie"] - ra["max_fout_convolutie"]
    assert math.isclose(werkelijk_verschil, verwacht_verschil, abs_tol=1e-3)

# --- Invoercontroles ---
def get_geldige_steekproef():
    return pd.DataFrame({
        "naam": ["test"], "waarde_laag": [1000.0], "n_laag": [50], "k_laag": [1.0],
        "ihr": ["H"], "ibr": ["H"], "car": ["H"], "materialiteit": [0.05],
        "waarde_hoog": [0.0], "fout_hoog": [0.0]
    })

def test_invoercontrole_ontbrekende_kolom():
    slecht = get_geldige_steekproef().drop(columns=["k_laag"])
    with pytest.raises(ValueError, match="Ontbrekende kolommen"):
        eval_stratified(slecht)

def test_invoercontrole_dubbele_stratumnamen():
    dubbel = pd.concat([get_geldige_steekproef(), get_geldige_steekproef()])
    with pytest.raises(ValueError, match="stratumnamen"):
        eval_stratified(dubbel)

def test_invoercontrole_lege_dataframe():
    leeg = get_geldige_steekproef().iloc[0:0]
    with pytest.raises(ValueError, match="is leeg"):
        eval_stratified(leeg)