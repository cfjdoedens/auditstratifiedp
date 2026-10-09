"""Tests voor de klimheuristiek en de discrete exchange-convexiteit."""

import pandas as pd
import pytest

from auditstat.stratified.analyseer_klimheuristiek import (  # pyrefly: ignore[missing-import]
    analyseer_exchange_convexiteit,
    analyseer_klimheuristiek,
)
from auditstat.stratified.plan_stratified import (  # pyrefly: ignore[missing-import]
    plan_stratified_basis,
    vind_beste_strata_groep,
)


def _demo_data() -> pd.DataFrame:
    """Geef een compacte, realistische dataset met drie strata terug."""
    return pd.DataFrame({
        "naam": ["Stratum A", "Stratum B", "Stratum C"],
        "waarde_laag": [500_000.0, 300_000.0, 200_000.0],
        "verwachte_foutfractie": [0.01, 0.015, 0.005],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "kosten": [1.0, 1.0, 1.0],
        "fout_hoog": [0.0, 0.0, 0.0],
        "waarde_hoog": [0.0, 0.0, 0.0],
        "materialiteit": [0.05, 0.05, 0.05],
    })


def _identieke_data() -> pd.DataFrame:
    """Geef twee identieke strata terug voor symmetrie- en exchange-tests."""
    return pd.DataFrame({
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


def test_klimheuristiek_demo_inclusief_exchange():
    """Controleer tegelijk het brute-force optimum en het exchange-rapport."""
    uitkomst = analyseer_klimheuristiek(
        _demo_data(),
        model="binomiaal",
        N_add=4,
        granulariteit=10_000,
        per_stap=True,
        controleer_exchange=True,
    )

    assert uitkomst["is_volledig_optimaal"] is True, (
        "De greedy heuristiek week af van het brute-force optimum."
    )

    # Door per_stap=True moet voor ieder bereikt budget een vergelijking bestaan.
    assert len(uitkomst["stap_rapportage"]) >= 1
    assert all(stap["is_optimaal"] for stap in uitkomst["stap_rapportage"])

    exchange = uitkomst["exchange_convexiteit"]
    assert exchange is not None
    assert exchange["is_exchange_convex"] is True, (
        f"Exchange-convexiteit geschonden: {exchange['overtredingen'][:3]}"
    )
    assert exchange["aantal_exchange_toetsen"] > 0
    assert exchange["aantal_overtredingen"] == 0
    assert exchange["overtredingen"] == []

    # Voor N_add=4 wordt N=2,3,4 onderzocht.
    assert [rij["steken_toegevoegd"] for rij in exchange["per_N"]] == [2, 3, 4]
    assert all(rij["is_exchange_convex"] for rij in exchange["per_N"])


def test_klimheuristiek_lage_zekerheid_zonder_exchange():
    """Behoud de zware lange-padtest, maar voorkom combinatorische exchange-kosten."""
    demo_data = _demo_data().copy()
    demo_data["verwachte_foutfractie"] = [0.01, 0.015, 0.009]

    uitkomst = analyseer_klimheuristiek(
        demo_data,
        model="binomiaal",
        N_add=32,
        granulariteit=10_000,
        zekerheid=0.01,
        controleer_exchange=False,
    )

    assert uitkomst["is_volledig_optimaal"] is True, (
        "De greedy heuristiek week af van het absolute optimum."
    )
    assert uitkomst["exchange_convexiteit"] is None


def test_exchange_convexiteit_direct_symmetrisch():
    """Test de nieuwe analysefunctie rechtstreeks op twee identieke strata."""
    basis = plan_stratified_basis(_identieke_data(), model="binomiaal")

    rapport = analyseer_exchange_convexiteit(
        strata_basis=basis,
        model="binomiaal",
        N_add=8,
        zekerheid=0.95,
        granulariteit=10_000,
        tolerantie=1e-10,
    )

    assert rapport["is_exchange_convex"] is True
    assert rapport["aantal_overtredingen"] == 0
    assert rapport["overtredingen_opgeslagen"] == 0
    assert rapport["aantal_allocaties_geëvalueerd"] > 0
    assert rapport["aantal_exchange_toetsen"] > 0
    assert rapport["kleinste_tweede_verschil"] is not None

    # Bij twee strata en vast N zijn er N+1 allocaties.
    # De rapportage moet dus per N exact N+1 allocaties bevatten.
    for rij in rapport["per_N"]:
        N = rij["steken_toegevoegd"]
        assert rij["aantal_allocaties"] == N + 1
        assert rij["aantal_exchange_toetsen"] == N - 1
        assert rij["aantal_overtredingen"] == 0
        assert rij["kleinste_tweede_verschil"] is not None


def test_exchange_rapport_consistentie_drie_strata():
    """Controleer dat totalen in het exchange-rapport optellen uit de per-N regels."""
    basis = plan_stratified_basis(_demo_data(), model="binomiaal")
    rapport = analyseer_exchange_convexiteit(
        strata_basis=basis,
        N_add=5,
        granulariteit=5_000,
        tolerantie=1e-9,
    )

    assert rapport["aantal_allocaties_geëvalueerd"] == sum(
        rij["aantal_allocaties"] for rij in rapport["per_N"]
    )
    assert rapport["aantal_exchange_toetsen"] == sum(
        rij["aantal_exchange_toetsen"] for rij in rapport["per_N"]
    )
    assert rapport["aantal_overtredingen"] == sum(
        rij["aantal_overtredingen"] for rij in rapport["per_N"]
    )
    assert rapport["is_exchange_convex"] == (rapport["aantal_overtredingen"] == 0)


def test_exchange_N_add_kleiner_dan_twee_geeft_leeg_rapport():
    """Voor N=0 of N=1 bestaan nog geen centrale 1-op-1 exchange-toetsen."""
    basis = plan_stratified_basis(_identieke_data(), model="binomiaal")

    for N_add in [0, 1]:
        rapport = analyseer_exchange_convexiteit(
            strata_basis=basis,
            N_add=N_add,
            granulariteit=2_000,
        )
        assert rapport["is_exchange_convex"] is True
        assert rapport["kleinste_tweede_verschil"] is None
        assert rapport["aantal_allocaties_geëvalueerd"] == 0
        assert rapport["aantal_exchange_toetsen"] == 0
        assert rapport["aantal_overtredingen"] == 0
        assert rapport["per_N"] == []


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"N_add": -1}, "N_add"),
        ({"tolerantie": -1e-12}, "tolerantie"),
        ({"max_overtredingen": -1}, "max_overtredingen"),
    ],
)
def test_exchange_valideert_argumenten(kwargs, match):
    """Negatieve grensparameters moeten expliciet worden geweigerd."""
    basis = plan_stratified_basis(_identieke_data(), model="binomiaal")

    with pytest.raises(ValueError, match=match):
        analyseer_exchange_convexiteit(strata_basis=basis, **kwargs)


def test_symmetrische_tie_verdeling():
    """Bij identieke strata moet de parallelle ophoogstap symmetrisch blijven."""
    identiek = _identieke_data()

    for N_add in [2, 6, 10, 20]:
        uitkomst = analyseer_klimheuristiek(
            identiek,
            model="binomiaal",
            N_add=N_add,
            granulariteit=10_000,
            controleer_exchange=False,
        )
        verdeling = uitkomst["greedy_verdeling"]
        assert verdeling[0] == verdeling[1], (
            f"Verwachtte gelijke verdeling bij identieke strata voor N_add={N_add}, "
            f"maar kreeg {verdeling}."
        )


def test_fallback_proxy_symmetrisch():
    """Bij een grove FFT moet de fallback-proxy identieke strata gelijk behandelen."""
    identiek = _identieke_data().copy()
    identiek["n_laag"] = [1000, 1000]
    identiek["k_laag"] = [0.0, 0.0]

    with pytest.warns(RuntimeWarning, match="analytische proxy"):
        beste = vind_beste_strata_groep(
            identiek,
            model="binomiaal",
            klim_granulariteit=500,
            totale_zekerheid=0.95,
        )

    assert set(beste) == {0, 1}, (
        f"Fallback-proxy moet beide identieke strata selecteren, maar koos: {beste}."
    )
