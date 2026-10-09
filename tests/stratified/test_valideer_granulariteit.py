"""Tests voor valideer_granulariteit."""

import math
import warnings

import pandas as pd
import pytest

from auditstat.stratified.valideer_granulariteit import (  # pyrefly: ignore[missing-import]
    _delta_i,
    valideer_granulariteit,
)


def _basis_strata():
    return pd.DataFrame({
        "naam": ["StratumA", "StratumB"],
        "waarde_laag": [700_000.0, 300_000.0],
        "fout_hoog": [0.0, 0.0],
        "waarde_hoog": [0.0, 0.0],
    })


def test_rapport_zonder_n_kolom():
    """Zonder n_kolom bevat het rapport naam, gewicht, d_i en n_max."""
    rapport = valideer_granulariteit(_basis_strata(), granulariteit=10_000)
    assert list(rapport.columns) == ["naam", "gewicht", "d_i", "n_max"]
    assert len(rapport) == 2


def test_gewichten_sommeren_naar_een():
    """De gewichten van alle strata moeten optellen tot 1."""
    rapport = valideer_granulariteit(_basis_strata(), granulariteit=10_000)
    totaal_gewicht = rapport["gewicht"].sum()
    assert totaal_gewicht == pytest.approx(1.0, abs=1e-9), (
        f"De som van alle stratum gewichten wijkt af van 1.0. "
        f"Berekende som: {totaal_gewicht:.12f}"
    )


def test_n_max_grensvoorwaarde():
    """n_max voldoet aan de grensvoorwaarde: Δᵢ(n_max) ≥ 1/g en Δᵢ(n_max+1) < 1/g."""
    g = 10_000
    zekerheid = 0.95
    rapport = valideer_granulariteit(
        _basis_strata(), granulariteit=g, zekerheid=zekerheid
    )

    for _, rij in rapport.iterrows():
        n_max = rij["n_max"]
        w = rij["gewicht"]
        d = rij["d_i"]
        target = 1.0 / g

        assert _delta_i(n_max, d, w, zekerheid) >= target, (
            f"{rij['naam']}: Δᵢ(n_max={n_max}) is te klein (< 1/g={target})"
        )
        assert _delta_i(n_max + 1, d, w, zekerheid) < target, (
            f"{rij['naam']}: Δᵢ(n_max+1={n_max + 1}) is te groot (≥ 1/g={target})"
        )


def test_geen_waarschuwing_bij_kleine_n():
    """Geen warnings wanneer n_huidig ruim onder n_max ligt."""
    strata = _basis_strata().copy()
    strata["n_laag"] = [10, 10]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rapport = valideer_granulariteit(strata, granulariteit=10_000, n_kolom="n_laag")
    assert (rapport["status"] == "OK").all()


def test_waarschuwing_bij_te_hoge_n():
    """Een warning én status=WAARSCHUWING voor een stratum boven n_max."""
    strata = _basis_strata().copy()
    strata["n_laag"] = [5000, 10]  # StratumA ver boven n_max
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        rapport = valideer_granulariteit(strata, granulariteit=10_000, n_kolom="n_laag")

    assert (
        rapport.loc[rapport["naam"] == "StratumA", "status"].values[0] == "WAARSCHUWING"
    )
    assert rapport.loc[rapport["naam"] == "StratumB", "status"].values[0] == "OK"
    assert any("StratumA" in str(w_.message) for w_ in w)


def test_g_min_klopt():
    """g_min moet groot genoeg zijn zodat n_max ≥ n_huidig na verhoging."""
    g = 10_000
    zekerheid = 0.95
    c = -math.log(1 - zekerheid)
    strata = _basis_strata().copy()
    strata["n_laag"] = [5000, 5000]

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        rapport = valideer_granulariteit(
            strata, granulariteit=g, zekerheid=zekerheid, n_kolom="n_laag"
        )

    for _, rij in rapport.iterrows():
        g_min = rij["g_min"]
        n_huidig = rij["n_huidig"]
        gewicht = rij["gewicht"]
        n_max_na_verhoging = int(math.sqrt(gewicht * c * g_min))
        assert n_max_na_verhoging >= n_huidig, (
            f"g_min={g_min} is niet genoeg voor {rij['naam']}: "
            f"n_max={n_max_na_verhoging} < n_huidig={n_huidig}"
        )


def test_fout_bij_ontbrekende_n_kolom():
    """ValueError als n_kolom niet bestaat in het DataFrame."""
    with pytest.raises(ValueError, match="bestaat_niet"):
        valideer_granulariteit(
            _basis_strata(), granulariteit=10_000, n_kolom="bestaat_niet"
        )
