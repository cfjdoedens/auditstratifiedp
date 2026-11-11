import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from scipy.stats import beta  # noqa: E402

from auditstat.single.eval_distribution import (  # noqa: E402
    _signifdig,
    eval_distribution,
    plot_eval_distribution,
)


@pytest.mark.parametrize("n,k", [(100, 3), (300, 0), (50, 10)])
def test_binomiaal_komt_overeen_met_beta(n, k):
    m = 20000
    res = eval_distribution(n=n, k=k, m=m)
    exact = beta.ppf(0.95, k + 1, n - k + 1)
    assert res["pmax"] == pytest.approx(exact, abs=2 / m)
    assert res["tabel"]["cc"].iloc[-1] == pytest.approx(1.0)
    assert res["tabel"]["c"].sum() / m == pytest.approx(1.0)


def test_meest_waarschijnlijke_fout_is_k_over_n():
    res = eval_distribution(n=100, k=10, m=10000)
    assert res["phigh"] == pytest.approx(0.10, abs=1e-4)


def test_k_nul_en_k_gelijk_n():
    r0 = eval_distribution(n=50, k=0)
    assert r0["pmin"] == 0 and r0["phigh"] == 0
    rn = eval_distribution(n=50, k=50)
    assert rn["pmax"] == 1 and rn["phigh"] == 1


def test_n_nul_geeft_volledig_onzekere_kromme():
    res = eval_distribution(n=0, k=0, m=1000)
    assert res["pmin"] == 0 and res["pmax"] == 1
    assert res["phigh"] == 1  # k = n wint van k = 0, zoals in de SAS-macro


def test_hypergeometrisch_benadert_binomiaal_bij_grote_massa():
    hyp = eval_distribution(n=100, k=2, verdeling="h", massa=20000)
    bin_ = eval_distribution(n=100, k=2, m=20000)
    assert hyp["aantal_punten"] == 20001
    assert hyp["pmax"] == pytest.approx(bin_["pmax"], abs=5e-4)
    assert hyp["tabel"]["c"].sum() / 20001 == pytest.approx(1.0)


def test_band_en_norm():
    res = eval_distribution(
        n=100, k=2, m=10000, norm=0.05, band_links=0, band_rechts=0.05
    )
    assert res["kans_onder_norm"] == pytest.approx(beta.cdf(0.05, 3, 99), abs=1e-3)
    assert res["band_kans"] == pytest.approx(beta.cdf(0.05, 3, 99), abs=1e-3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n": -1, "k": 0},
        {"n": 5, "k": 6},
        {"n": 5.5, "k": 1},
        {"n": 5, "k": 1, "zekerheid": 0.4},
        {"n": 5, "k": 1, "norm": 1.5},
        {"n": 5, "k": 1, "m": 1},
        {"n": 5, "k": 1, "verdeling": "poisson"},
        {"n": 5, "k": 1, "verdeling": "h", "massa": 0},
        {"n": 5, "k": 1, "verdeling": "h", "massa": 3},
        {"n": 5, "k": 1, "band_links": 0.5, "band_rechts": 0.5},
    ],
)
def test_ongeldige_invoer(kwargs):
    with pytest.raises(ValueError):
        eval_distribution(**kwargs)


def test_signifdig_voorbeelden_uit_sas():
    assert _signifdig(0.0567, 2) == 0.057
    assert _signifdig(4.567, 2) == 4.6
    assert _signifdig(234.567, 2) == 235
    assert _signifdig(0, 4) == 0
    assert _signifdig(-0.0567, 2) == -0.057


@pytest.mark.parametrize("deel", ["geen", "onder_pmax", "boven_pmin", "band"])
def test_plot_geeft_figuur(deel):
    res = eval_distribution(n=100, k=3, norm=0.05, massa=1_000_000)
    fig = plot_eval_distribution(res, titel="Test", toon_massa=True, geklemd_deel=deel)
    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_ongeldig_deel():
    res = eval_distribution(n=10, k=1)
    with pytest.raises(ValueError):
        plot_eval_distribution(res, geklemd_deel="onzin")
    assert np.isfinite(res["pmax"])
