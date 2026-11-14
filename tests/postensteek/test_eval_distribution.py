import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from scipy.stats import beta, gamma  # noqa: E402

from auditstat.postensteek.eval_distribution import (  # noqa: E402
    _signifdig,
    eval_distribution,
    plot_eval_distribution,
)


@pytest.mark.parametrize("n,k", [(100, 3), (300, 0), (50, 10)])
def test_binomiaal_komt_overeen_met_beta(n, k):
    m = 20000
    res = eval_distribution(n=n, k=k, verdeling="binomiaal", m=m)
    exact = beta.ppf(0.95, k + 1, n - k + 1)
    assert res["pmax"] == pytest.approx(exact, abs=2 / m)
    assert res["tabel"]["cc"].iloc[-1] == pytest.approx(1.0)
    assert res["tabel"]["c"].sum() / m == pytest.approx(1.0)


def test_meest_waarschijnlijke_fout_is_k_over_n():
    res = eval_distribution(n=100, k=10, verdeling="binomiaal", m=10000)
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
    bin_ = eval_distribution(n=100, k=2, verdeling="binomiaal", m=20000)
    assert hyp["aantal_punten"] == 20001
    assert hyp["pmax"] == pytest.approx(bin_["pmax"], abs=5e-4)
    assert hyp["tabel"]["c"].sum() / 20001 == pytest.approx(1.0)


def test_hypergeometrisch_zonder_massa_gebruikt_drie_maal_n():
    res = eval_distribution(n=50, k=2, verdeling="h")
    assert res["massa"] == 150
    assert res["massa_aangenomen"] is True
    assert res["aantal_punten"] == 151
    expliciet = eval_distribution(n=50, k=2, verdeling="h", massa=150)
    assert expliciet["massa_aangenomen"] is False
    assert res["pmax"] == expliciet["pmax"]


def test_hypergeometrisch_zonder_massa_en_n_nul_gebruikt_100():
    res = eval_distribution(n=0, k=0, verdeling="h")
    assert res["massa"] == 100
    assert res["massa_aangenomen"] is True


@pytest.mark.parametrize("n,k", [(100, 3), (300, 0), (50, 10), (1000, 2)])
def test_poisson_komt_overeen_met_gamma(n, k):
    m = 20000
    res = eval_distribution(n=n, k=k, verdeling="poisson", m=m)
    exact = gamma.ppf(0.95, k + 1, scale=1 / n)
    assert res["pmax"] == pytest.approx(exact, abs=2 / m + 1e-4)
    if k > 0:
        assert res["pmin"] == pytest.approx(
            gamma.ppf(0.05, k + 1, scale=1 / n), abs=2 / m + 1e-4
        )
        assert res["phigh"] == pytest.approx(k / n, abs=2 / m)
    assert res["tabel"]["c"].sum() / m == pytest.approx(1.0)
    assert res["zeker_max"] is False


@pytest.mark.parametrize(
    "n,k,zekerheid", [(306, 46, 0.975), (306, 31, 0.95), (1000, 300, 0.9)]
)
def test_normaal_komt_overeen_met_waldformule(n, k, zekerheid):
    from scipy.stats import norm

    m = 40000
    res = eval_distribution(n=n, k=k, verdeling="normaal", zekerheid=zekerheid, m=m)
    f = k / n
    half = norm.ppf(zekerheid) * (f * (1 - f) / n) ** 0.5
    assert res["pmin"] == pytest.approx(f - half, abs=2 / m)
    assert res["pmax"] == pytest.approx(f + half, abs=2 / m)
    assert res["phigh"] == pytest.approx(f, abs=2 / m)


def test_normaal_document_voorbeeld():
    res = eval_distribution(n=306, k=46, verdeling="n", zekerheid=0.975, m=40000)
    assert res["pmin"] == pytest.approx(0.110, abs=5e-4)
    assert res["pmax"] == pytest.approx(0.190, abs=5e-4)


@pytest.mark.parametrize("n,k", [(50, 0), (50, 50), (0, 0)])
def test_normaal_vraagt_k_tussen_0_en_n(n, k):
    with pytest.raises(ValueError):
        eval_distribution(n=n, k=k, verdeling="normaal")


def test_poisson_randgevallen():
    r0 = eval_distribution(n=50, k=0, verdeling="p")
    assert r0["pmin"] == 0 and r0["phigh"] == 0 and r0["zeker_min"] is True
    rn = eval_distribution(n=50, k=50, verdeling="poisson")
    assert rn["pmax"] < 1 and rn["zeker_max"] is False
    leeg = eval_distribution(n=0, k=0, verdeling="poisson", m=1000)
    assert leeg["pmin"] == pytest.approx(0.05, abs=2e-3)
    assert leeg["pmax"] == pytest.approx(0.95, abs=2e-3)


def test_band_en_norm():
    res = eval_distribution(
        n=100,
        k=2,
        verdeling="binomiaal",
        m=10000,
        norm=0.05,
        band_links=0,
        band_rechts=0.05,
    )
    assert res["kans_boven_norm"] == pytest.approx(beta.sf(0.05, 3, 99), abs=1e-3)
    assert res["band_kans"] == pytest.approx(beta.cdf(0.05, 3, 99), abs=1e-3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n": -1, "k": 0},
        {"n": 5, "k": 6},
        {"n": 5.5, "k": 1},
        {"n": 5, "k": 1, "zekerheid": 0.4},
        {"n": 5, "k": 1, "norm": 1.5},
        {"n": 5, "k": 1, "verdeling": "binomiaal", "m": 1},
        {"n": 5, "k": 1, "verdeling": "onzin"},
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


def test_plot_normaal():
    res = eval_distribution(n=306, k=46, verdeling="normaal", norm=0.2)
    fig = plot_eval_distribution(res)
    assert "normale" in " ".join(t.get_text() for t in fig.texts)
    plt.close(fig)


def test_plot_poisson():
    res = eval_distribution(n=100, k=3, verdeling="poisson", norm=0.05)
    fig = plot_eval_distribution(res)
    assert "Poisson" in " ".join(t.get_text() for t in fig.texts)
    plt.close(fig)


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
