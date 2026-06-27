import pandas as pd
from auditstratified.analyseer_klimheuristiek import analyseer_klimheuristiek

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
        "materialiteit": [0.05, 0.05, 0.05],
        "fout_hoog": [0.0, 0.0, 0.0],
        "goed_hoog": [0.0, 0.0, 0.0]
    })

    N_add = 4

    # Voer de analytische vergelijking uit voor N_add extra stappen.
    uitkomst = analyseer_klimheuristiek(demo_data, model="binomiaal", N_add=N_add, granulariteit=10000)
    
    # Eis dat de greedy heuristiek gedurende de HELE reis op het perfecte pad bleef.
    assert uitkomst["is_volledig_optimaal"] is True, "De greedy heuristiek week af van het absolute optimum!"

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
        "materialiteit": [0.05, 0.05, 0.05],
        "fout_hoog": [0.0, 0.0, 0.0],
        "goed_hoog": [0.0, 0.0, 0.0]
    })

    N_add = 32

    # Voer de analytische vergelijking uit voor N_add extra stappen.
    uitkomst = analyseer_klimheuristiek(demo_data, model="binomiaal", N_add=N_add, granulariteit=10000, zekerheid=0.01)
    
    # Eis dat de greedy heuristiek gedurende de HELE reis op het perfecte pad bleef.
    assert uitkomst["is_volledig_optimaal"] is True, "De greedy heuristiek week af van het absolute optimum!"


# Toon de werking van de validatiefunctie aan de hand van een handmatige demonstratie.
if __name__ == "__main__":
    demo_data = pd.DataFrame({
        "naam": ["Stratum A", "Stratum B", "Stratum C"],
        "waarde_laag": [500000.0, 300000.0, 200000.0],
        "verwachte_foutfractie": [0.01, 0.015, 0.009],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "materialiteit": [0.05, 0.05, 0.05],
        "fout_hoog": [0.0, 0.0, 0.0],
        "goed_hoog": [0.0, 0.0, 0.0]
    })

    print("--- Start Heuristiek Validatietest ---")
    N_add = 100
    print(f"Systeem simuleert de route van {N_add} steken over 3 strata...\n")
    
    # Voer de rekenintensieve analyse uit voor N_add steken.
    uitkomst = analyseer_klimheuristiek(demo_data, model="binomiaal", N_add=N_add, granulariteit=10000, per_stap = False)
    
    # Rapporteer de bevindingen overzichtelijk aan de gebruiker.
    print(f"Is de heuristiek op ELKE afzonderlijke stap optimaal?: {uitkomst['is_volledig_optimaal']}")
    print(f"Totaal aantal brute-force combinaties geëvalueerd: {uitkomst['totaal_geëvalueerd']}")
    print(f"Eindverdeling gekozen door algoritme: {uitkomst['greedy_verdeling']}\n")
    
    print("--- Rapportage per stap ---")
    for stap in uitkomst['stap_rapportage']:
        print(f"Steken toegevoegd: {stap['steken_toegevoegd']:<2} | "
              f"Greedy fout: {stap['greedy_fout']:.6f} | "
              f"Absoluut Optimum: {stap['globale_optimum_fout']:.6f} | "
              f"Optimaal? {stap['is_optimaal']}")