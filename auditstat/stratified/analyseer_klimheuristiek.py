__all__ = ["analyseer_klimheuristiek", "analyseer_exchange_convexiteit"]

import math

import pandas as pd

from .eval_stratified import eval_stratified
from .plan_stratified import (
    plan_stratified_basis,
    vind_beste_strata_groep,
)


def analyseer_klimheuristiek(
    steekproeven: pd.DataFrame,
    model: str = "binomiaal",
    N_add: int = 4,
    zekerheid: float = 0.95,
    granulariteit: int = 10000,
    per_stap: bool = False,
    controleer_exchange: bool = True,
    exchange_tolerantie: float = 1e-10,
    max_overtredingen: int = 100,
) -> dict:
    """
    Controleer of de steileklimheuristiek tot de optimale verdeling leidt.

    De functie doorloopt het klimalgoritme. Als 'per_stap' op True staat, wordt er
    bij elke toegevoegde steek een brute-force zoektocht uitgevoerd. Staat deze op
    False (standaard), dan wordt de vergelijking pas aan het eind van de rit gemaakt.

    Als ``controleer_exchange`` True is, wordt daarnaast voor elk totaal aantal
    extra waarnemingen van 2 t/m ``N_add`` de discrete exchange-convexiteit
    gecontroleerd. Voor iedere haalbare allocatie x en ieder stratumpaar (i, j)
    waarvoor beide reallocaties haalbaar zijn, wordt getoetst of::

        F(x - e_i + e_j) - 2 F(x) + F(x + e_i - e_j) >= 0.

    Een negatieve waarde kleiner dan ``-exchange_tolerantie`` geldt als een
    overtreding. De toets gebruikt dezelfde FFT-evaluatie als het planningsalgoritme.
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
                strata_greedy.at[idx, "n_laag"]
                * strata_greedy.at[idx, "verwachte_foutfractie"]
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
                vergelijk=False,
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
                    test_strata.at[rij_label, "k_laag"] = (
                        test_strata.at[rij_label, "n_laag"]
                        * test_strata.at[rij_label, "verwachte_foutfractie"]
                    )

                # Evalueer de resulterende fout voor deze specifieke verdeling.
                fout_test = eval_stratified(
                    test_strata,
                    model=model,
                    zekerheid=zekerheid,
                    methode="FFT samen",
                    granulariteit=granulariteit,
                    vergelijk=False,
                )["max_fout_convolutie"]

                # Sla de laagst gevonden fout op als het nieuwe globale wiskundige optimum.
                if fout_test < laagste_fout_globaal:
                    laagste_fout_globaal = fout_test

            # Controleer of de greedy heuristiek op dit exacte punt is afgeweken van de waarheid.
            stap_is_optimaal = math.isclose(
                greedy_fout, laagste_fout_globaal, abs_tol=1e-4
            )
            if not stap_is_optimaal:
                is_volledig_optimaal = False

            # Sla de vergelijkende resultaten op in de rapportage.
            stap_rapportage.append({
                "steken_toegevoegd": toegevoegd,
                "greedy_fout": greedy_fout,
                "globale_optimum_fout": laagste_fout_globaal,
                "is_optimaal": stap_is_optimaal,
            })

    exchange_rapport = None
    if controleer_exchange:
        exchange_rapport = analyseer_exchange_convexiteit(
            strata_basis=strata_basis,
            model=model,
            N_add=N_add,
            zekerheid=zekerheid,
            granulariteit=granulariteit,
            tolerantie=exchange_tolerantie,
            max_overtredingen=max_overtredingen,
        )

    return {
        "is_volledig_optimaal": is_volledig_optimaal,
        "greedy_verdeling": strata_greedy["n_laag"].tolist(),
        "totaal_geëvalueerd": totaal_geëvalueerd,
        "stap_rapportage": stap_rapportage,
        "exchange_convexiteit": exchange_rapport,
    }


def analyseer_exchange_convexiteit(
    strata_basis: pd.DataFrame,
    model: str = "binomiaal",
    N_add: int = 4,
    zekerheid: float = 0.95,
    granulariteit: int = 10000,
    tolerantie: float = 1e-10,
    max_overtredingen: int = 100,
) -> dict:
    """Toets discrete exchange-convexiteit vanaf de basisallocatie.

    Voor elk vast totaal ``N`` aan extra waarnemingen worden alle haalbare
    integerallocaties over de strata geëvalueerd. Vervolgens wordt voor iedere
    allocatie ``x`` en ieder paar strata ``(i, j)`` waarvoor ``x_i >= 1`` en
    ``x_j >= 1`` geldt, de tweede exchange-differentie berekend::

        D2 = F(x - e_i + e_j) - 2 F(x) + F(x + e_i - e_j).

    ``D2 >= 0`` is de lokale discrete convexiteitsvoorwaarde langs de
    reallocatierichting ``e_i - e_j`` bij vast totaal aantal waarnemingen.
    Omdat alle drie allocaties hetzelfde totaal hebben, kunnen hun reeds
    berekende foutwaarden uit een cache worden gebruikt.
    """
    if N_add < 0:
        raise ValueError("N_add moet niet-negatief zijn.")
    if tolerantie < 0:
        raise ValueError("tolerantie moet niet-negatief zijn.")
    if max_overtredingen < 0:
        raise ValueError("max_overtredingen moet niet-negatief zijn.")

    n_strata = len(strata_basis)
    per_N = []
    overtredingen = []
    totaal_allocaties = 0
    totaal_toetsen = 0
    kleinste_d2 = float("inf")

    # Voor N=0 en N=1 bestaat geen centraal punt met aan beide zijden
    # een haalbare 1-op-1-reallocatie, dus starten we bij N=2.
    for N in range(2, N_add + 1):
        fout_per_verdeling = {}

        # Evalueer iedere allocatie voor dit vaste totaal precies één keer.
        for verdeling in genereer_verdelingen(N, n_strata):
            test_strata = strata_basis.copy()
            for i in range(n_strata):
                rij_label = test_strata.index[i]
                test_strata.at[rij_label, "n_laag"] += int(verdeling[i])
                test_strata.at[rij_label, "k_laag"] = (
                    test_strata.at[rij_label, "n_laag"]
                    * test_strata.at[rij_label, "verwachte_foutfractie"]
                )

            fout_per_verdeling[verdeling] = eval_stratified(
                test_strata,
                model=model,
                zekerheid=zekerheid,
                methode="FFT samen",
                granulariteit=granulariteit,
                vergelijk=False,
            )["max_fout_convolutie"]

        totaal_allocaties += len(fout_per_verdeling)
        aantal_toetsen_N = 0
        aantal_overtredingen_N = 0
        kleinste_d2_N = float("inf")

        # Toets lokale discrete convexiteit langs iedere exchange-richting.
        for verdeling, fout_centraal in fout_per_verdeling.items():
            for i in range(n_strata):
                if verdeling[i] == 0:
                    continue
                for j in range(i + 1, n_strata):
                    if verdeling[j] == 0:
                        continue

                    links = list(verdeling)
                    links[i] -= 1
                    links[j] += 1
                    links = tuple(links)

                    rechts = list(verdeling)
                    rechts[i] += 1
                    rechts[j] -= 1
                    rechts = tuple(rechts)

                    d2 = (
                        fout_per_verdeling[links]
                        - 2.0 * fout_centraal
                        + fout_per_verdeling[rechts]
                    )

                    aantal_toetsen_N += 1
                    totaal_toetsen += 1
                    kleinste_d2_N = min(kleinste_d2_N, d2)
                    kleinste_d2 = min(kleinste_d2, d2)

                    if d2 < -tolerantie:
                        aantal_overtredingen_N += 1
                        if len(overtredingen) < max_overtredingen:
                            overtredingen.append({
                                "steken_toegevoegd": N,
                                "verdeling_centraal": verdeling,
                                "stratum_i": strata_basis.index[i],
                                "stratum_j": strata_basis.index[j],
                                "verdeling_links": links,
                                "verdeling_rechts": rechts,
                                "fout_links": fout_per_verdeling[links],
                                "fout_centraal": fout_centraal,
                                "fout_rechts": fout_per_verdeling[rechts],
                                "tweede_verschil": d2,
                            })

        per_N.append({
            "steken_toegevoegd": N,
            "aantal_allocaties": len(fout_per_verdeling),
            "aantal_exchange_toetsen": aantal_toetsen_N,
            "kleinste_tweede_verschil": (
                None if aantal_toetsen_N == 0 else kleinste_d2_N
            ),
            "aantal_overtredingen": aantal_overtredingen_N,
            "is_exchange_convex": aantal_overtredingen_N == 0,
        })

    aantal_overtredingen = sum(r["aantal_overtredingen"] for r in per_N)

    return {
        "is_exchange_convex": aantal_overtredingen == 0,
        "tolerantie": tolerantie,
        "kleinste_tweede_verschil": (
            None if totaal_toetsen == 0 else kleinste_d2
        ),
        "aantal_allocaties_geëvalueerd": totaal_allocaties,
        "aantal_exchange_toetsen": totaal_toetsen,
        "aantal_overtredingen": aantal_overtredingen,
        "overtredingen_opgeslagen": len(overtredingen),
        "overtredingen": overtredingen,
        "per_N": per_N,
    }


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
