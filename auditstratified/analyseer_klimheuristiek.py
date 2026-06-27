import math
import pandas as pd
from auditstratified.plan_stratified import plan_stratified_basis, vind_beste_strata_groep
from auditstratified.eval_stratified import eval_stratified

def genereer_verdelingen(n_steken, n_strata):
    """
    Genereer alle mogelijke verdelingen van een aantal steken over de strata.
    
    Dit is een recursieve generator die alle non-negatieve integercomposities
    teruggeeft van n_steken verdeeld over n_strata groepen.
    """
    if n_strata == 1:
        yield (n_steken,)
    else:
        # We proberen elk aantal steken van 0 tot n_steken voor het huidige stratum.
        for i in range(n_steken + 1):
            for sub_verdeling in genereer_verdelingen(n_steken - i, n_strata - 1):
                yield (i,) + sub_verdeling


def analyseer_klimheuristiek(steekproeven: pd.DataFrame, model: str = "binomiaal", 
                             N_add: int = 4, zekerheid: float = 0.95, 
                             granulariteit: int = 10000, per_stap: bool = False) -> dict:
    """
    Controleer of de greedy klimheuristiek tot de optimale verdeling leidt.
    
    De functie doorloopt het klimalgoritme. Als 'per_stap' op True staat, wordt er 
    bij elke toegevoegde steek een brute-force zoektocht uitgevoerd. Staat deze op 
    False (standaard), dan wordt de vergelijking pas aan het eind van de rit gemaakt.
    """
    # We maken een kopie van de invoergegevens om ongewenste neveneffecten te voorkomen.
    data = steekproeven.copy()

    # Bepaal eerst de minimale basissteekproefomvang per stratum (Stap 1).
    strata_basis = plan_stratified_basis(data, model=model)
    n_strata = len(strata_basis)

    # Initialiseer de trackingvariabelen voor de analyse.
    strata_greedy = strata_basis.copy()
    toegevoegd = 0
    stap_rapportage = []
    is_volledig_optimaal = True
    totaal_geëvalueerd = 0

    # Simuleer de greedy klimheuristiek totdat het budget (N_add) is bereikt.
    while toegevoegd < N_add:
        # Bepaal via de heuristiek de beste strata voor deze iteratie.
        beste_strata = vind_beste_strata_groep(
            strata_greedy,
            model=model,
            klim_granulariteit=granulariteit,
            totale_zekerheid=zekerheid,
        )

        # Begrens het aantal parallelle ophoogingen tot het resterende budget.
        resterend = N_add - toegevoegd
        te_verhogen = beste_strata[:resterend]

        # Voer de greedy ophoogstap daadwerkelijk door op de geselecteerde strata.
        for idx in te_verhogen:
            strata_greedy.at[idx, "n_laag"] += 1
            strata_greedy.at[idx, "k_laag"] = (
                strata_greedy.at[idx, "n_laag"] * strata_greedy.at[idx, "verwachte_foutfractie"]
            )

        # Houd exact bij hoeveel steken we inmiddels hebben toegevoegd.
        toegevoegd += len(te_verhogen)

        # Voer de rekenintensieve brute-force check alleen uit als per_stap True is,
        # of als we aan het einde van onze rit (N_add) zijn beland.
        if per_stap or toegevoegd == N_add:
            # Evalueer de actuele fout van het greedy pad tot nu toe.
            res_greedy = eval_stratified(
                strata_greedy,
                model=model,
                zekerheid=zekerheid,
                methode="FFT samen",
                granulariteit=granulariteit,
                vergelijk=False
            )
            greedy_fout = res_greedy["max_fout_convolutie"]

            # Start de brute-force zoektocht voor exact dit huidige aantal toegevoegde steken.
            laagste_fout_globaal = float("inf")
            
            # Evalueer alle combinaties voor dit specifieke stappen-moment.
            for verdeling in genereer_verdelingen(toegevoegd, n_strata):
                totaal_geëvalueerd += 1
                test_strata = strata_basis.copy()
                
                # Loop over alle strata op basis van hun positie.
                for i in range(n_strata):
                    # Haal het werkelijke label van de rij op, zodat at-indexing niet crasht.
                    rij_label = test_strata.index[i]
                    # Voeg de steken van deze brute-force combinatie toe.
                    test_strata.at[rij_label, "n_laag"] += int(verdeling[i])
                    # Bereken het nieuwe aantal verwachte fouten op basis van de extra steken.
                    test_strata.at[rij_label, "k_laag"] = test_strata.at[rij_label, "n_laag"] * test_strata.at[rij_label, "verwachte_foutfractie"]                    
                
                # Evalueer de resulterende fout voor deze specifieke verdeling.
                fout_test = eval_stratified(
                    test_strata,
                    model=model,
                    zekerheid=zekerheid,
                    methode="FFT samen",
                    granulariteit=granulariteit,
                    vergelijk=False
                )["max_fout_convolutie"]
                
                # Sla de laagst gevonden fout op als het nieuwe globale wiskundige optimum.
                if fout_test < laagste_fout_globaal:
                    laagste_fout_globaal = fout_test

            # Controleer of de greedy heuristiek op dit exacte punt is afgeweken van de waarheid.
            stap_is_optimaal = math.isclose(greedy_fout, laagste_fout_globaal, abs_tol=1e-4)
            if not stap_is_optimaal:
                is_volledig_optimaal = False

            # Sla de vergelijkende resultaten op in de rapportage.
            stap_rapportage.append({
                "steken_toegevoegd": toegevoegd,
                "greedy_fout": greedy_fout,
                "globale_optimum_fout": laagste_fout_globaal,
                "is_optimaal": stap_is_optimaal
            })

    return {
        "is_volledig_optimaal": is_volledig_optimaal,
        "greedy_verdeling": strata_greedy["n_laag"].tolist(),
        "totaal_geëvalueerd": totaal_geëvalueerd,
        "stap_rapportage": stap_rapportage
    }