import pandas as pd
import pytest

from auditstratified.analyseer_klimheuristiek import (  # pyrefly: ignore[missing-import]
    analyseer_klimheuristiek,
)
from auditstratified.plan_stratified import (  # pyrefly: ignore[missing-import]
    vind_beste_strata_groep,
)


def test_klimheuristiek_demo():
    """
    Test de heuristiek via pytest met een realistische demo-dataset.

    Dit stelt pytest in staat om deze test automatisch te ontdekken en
    uit te voeren binnen de tests/ directory in Positron.
    """
    demo_data = pd.DataFrame({
        "naam": ["Stratum A", "Stratum B", "Stratum C"],
        "waarde_laag": [500000.0, 300000.0, 200000.0],
        "verwachte_foutfractie": [0.01, 0.015, 0.005],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "kosten": [1.0, 1.0, 1.0],
        "fout_hoog": [0.0, 0.0, 0.0],
        "waarde_hoog": [0.0, 0.0, 0.0],
        "materialiteit": [0.05, 0.05, 0.05],
    })

    N_add = 4

    # Voer de analytische vergelijking uit voor N_add extra stappen.
    uitkomst = analyseer_klimheuristiek(
        demo_data, model="binomiaal", N_add=N_add, granulariteit=10000
    )

    # Eis dat de greedy heuristiek gedurende de HELE reis op het perfecte pad bleef.
    assert uitkomst["is_volledig_optimaal"] is True, (
        "De greedy heuristiek week af van het absolute optimum!"
    )


def test_klimheuristiek_lage_zekerheid():
    """
    Test de heuristiek via pytest met een realistische demo-dataset.

    Dit stelt pytest in staat om deze test automatisch te ontdekken en
    uit te voeren binnen de tests/ directory in Positron.
    """
    demo_data = pd.DataFrame({
        "naam": ["Stratum A", "Stratum B", "Stratum C"],
        "waarde_laag": [500000.0, 300000.0, 200000.0],
        "verwachte_foutfractie": [0.01, 0.015, 0.009],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "kosten": [1.0, 1.0, 1.0],
        "fout_hoog": [0.0, 0.0, 0.0],
        "waarde_hoog": [0.0, 0.0, 0.0],
        "materialiteit": [0.05, 0.05, 0.05],
    })

    N_add = 32

    # Voer de analytische vergelijking uit voor N_add extra stappen.
    uitkomst = analyseer_klimheuristiek(
        demo_data, model="binomiaal", N_add=N_add, granulariteit=10000, zekerheid=0.01
    )

    # Eis dat de greedy heuristiek gedurende de HELE reis op het perfecte pad bleef.
    assert uitkomst["is_volledig_optimaal"] is True, (
        "De greedy heuristiek week af van het absolute optimum!"
    )


def test_symmetrische_tie_verdeling():
    """
    Bij identieke strata moet de parallelle ophoogstap altijd een gelijke verdeling
    opleveren: greedy_verdeling[0] == greedy_verdeling[1] voor elk N_add.

    Dit test direct of de tie-detectie in vind_beste_strata_groep (tolerantie 1e-12)
    correct werkt: beide strata worden elke stap tegelijk opgehoogd.
    """
    identiek = pd.DataFrame({
        "naam": ["StratumA", "StratumB"],
        "waarde_laag": [500_000.0, 500_000.0],
        "verwachte_foutfractie": [0.005, 0.005],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "kosten": [1.0, 1.0],
        "fout_hoog": [0.0, 0.0],
        "waarde_hoog": [0.0, 0.0],
        "materialiteit": [0.03, 0.03],
    })

    for N_add in [2, 6, 10, 20]:
        uitkomst = analyseer_klimheuristiek(
            identiek, model="binomiaal", N_add=N_add, granulariteit=10_000
        )
        verdeling = uitkomst["greedy_verdeling"]
        assert verdeling[0] == verdeling[1], (
            f"Verwachtte gelijke verdeling bij identieke strata voor N_add={N_add}, "
            f"maar kreeg {verdeling}."
        )


def test_fallback_proxy_symmetrisch():
    """
    Bij een te grove granulariteit (max_verbetering=0) valt vind_beste_strata_groep
    terug op de analytische proxy. Voor identieke strata moet de proxy beide strata
    als gelijkwaardig selecteren: beste_strata == [0, 1].

    Gebruikt g=500 met n=1000, waarvoor geldt c/n² ≈ 3e-6 << 1/g = 0.002,
    zodat de FFT geen reductie kan meten en de fallback-tak wordt bereikt.
    """
    identiek = pd.DataFrame({
        "naam": ["StratumA", "StratumB"],
        "waarde_laag": [500_000.0, 500_000.0],
        "n_laag": [1000, 1000],
        "k_laag": [0.0, 0.0],
        "verwachte_foutfractie": [0.005, 0.005],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "kosten": [1.0, 1.0],
        "fout_hoog": [0.0, 0.0],
        "waarde_hoog": [0.0, 0.0],
        "materialiteit": [0.03, 0.03],
    })

    with pytest.warns(RuntimeWarning, match="analytische proxy"):
        beste = vind_beste_strata_groep(
            identiek, model="binomiaal", klim_granulariteit=500, totale_zekerheid=0.95
        )
    assert set(beste) == {0, 1}, (
        f"Fallback-proxy moet beide identieke strata selecteren, maar koos: {beste}. "
        f"Dit wijst op een asymmetrie in de analytische proxy bij identieke strata."
    )


# Toon de werking van de validatiefunctie aan de hand van een handmatige demonstratie.
if __name__ == "__main__":
    demo_data = pd.DataFrame({
        "naam": ["Stratum A", "Stratum B", "Stratum C"],
        "waarde_laag": [500000.0, 300000.0, 200000.0],
        "verwachte_foutfractie": [0.01, 0.015, 0.009],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "kosten": [1.0, 1.0, 1.0],
        "fout_hoog": [0.0, 0.0, 0.0],
        "waarde_hoog": [0.0, 0.0, 0.0],
        "materialiteit": [0.05, 0.05, 0.05],
    })

    print("--- Start Heuristiek Validatietest ---")
    N_add = 100
    print(f"Systeem simuleert de route van {N_add} steken over 3 strata...\n")

    # Voer de rekenintensieve analyse uit voor N_add steken.
    uitkomst = analyseer_klimheuristiek(
        demo_data, model="binomiaal", N_add=N_add, granulariteit=10000, per_stap=False
    )

    # Rapporteer de bevindingen overzichtelijk aan de gebruiker.
    print(
        f"Is de heuristiek op ELKE afzonderlijke stap optimaal?: {uitkomst['is_volledig_optimaal']}"
    )
    print(
        f"Totaal aantal brute-force combinaties geëvalueerd: {uitkomst['totaal_geëvalueerd']}"
    )
    print(f"Eindverdeling gekozen door algoritme: {uitkomst['greedy_verdeling']}\n")

    print("--- Rapportage per stap ---")
    for stap in uitkomst["stap_rapportage"]:
        print(
            f"Steken toegevoegd: {stap['steken_toegevoegd']:<2} | "
            f"Greedy fout: {stap['greedy_fout']:.6f} | "
            f"Absoluut Optimum: {stap['globale_optimum_fout']:.6f} | "
            f"Optimaal? {stap['is_optimaal']}"
        )
