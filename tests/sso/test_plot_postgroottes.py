import math

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from auditstat.sso.plot_postgroottes import (  # noqa: E402
    aandeel_grootste_gamma,
    gini_gamma,
    lorenz_empirisch,
    lorenz_gamma,
    plot_lorenz_postgroottes,
)


def test_cv_nul_is_de_diagonaal():
    p = np.linspace(0, 1, 11)
    assert np.allclose(lorenz_gamma(0, p), p)
    assert gini_gamma(0) == 0.0


def test_cv_een_is_exponentieel():
    # Exponentieel (cv = 1): L(p) = p + (1-p) ln(1-p), Gini = 1/2.
    p = np.array([0.1, 0.5, 0.9])
    assert np.allclose(lorenz_gamma(1, p), p + (1 - p) * np.log(1 - p), atol=1e-9)
    assert gini_gamma(1) == pytest.approx(0.5)


@pytest.mark.parametrize("cv", [0.3, 1.0, 2.5])
def test_gamma_tegen_steekproef(cv):
    rng = np.random.default_rng(4821)
    a = 1 / cv**2
    w = rng.gamma(a, 1 / a, size=400_000)
    _, _, gini, top10 = lorenz_empirisch(w)
    assert gini == pytest.approx(gini_gamma(cv), abs=0.01)
    assert top10 == pytest.approx(aandeel_grootste_gamma(cv, 0.1), abs=0.01)


def test_lorenz_stijgt_met_cv_naar_beneden():
    p = np.linspace(0.05, 0.95, 10)
    assert np.all(lorenz_gamma(2, p) < lorenz_gamma(1, p))
    assert np.all(lorenz_gamma(1, p) < lorenz_gamma(0.5, p))


def test_lorenz_empirisch_gelijke_posten():
    _, L, gini, top10 = lorenz_empirisch([5.0] * 100)
    assert gini == pytest.approx(0.0, abs=1e-12)
    assert top10 == pytest.approx(0.1)


def test_ongeldige_invoer():
    with pytest.raises(ValueError):
        lorenz_gamma(-1, [0.5])
    with pytest.raises(ValueError):
        lorenz_empirisch([])
    with pytest.raises(ValueError):
        plot_lorenz_postgroottes()


def test_plot_wordt_getekend():
    fig = plot_lorenz_postgroottes(cv=1.5, postwaarden=[1.0, 2.0, 10.0, 50.0])
    assert fig.axes
    plt.close(fig)


def test_kenmerken_gamma_cv_1_is_exponentieel():
    from auditstat.sso.plot_postgroottes import kenmerken_gamma

    k = kenmerken_gamma(1.0, gemiddelde=500.0)
    assert k["gini"] == pytest.approx(0.5)
    assert k["mediaan"] == pytest.approx(500.0 * math.log(2))
    assert k["drempel_top10"] == pytest.approx(500.0 * math.log(10))


def test_kenmerken_empirisch_en_compacte_figuur():
    from auditstat.sso.plot_postgroottes import (
        kenmerken_empirisch,
        plot_lorenz_postgroottes,
    )

    w = np.array([1.0, 2.0, 3.0, 4.0])
    k = kenmerken_empirisch(w)
    assert k["aantal"] == 4 and k["gemiddelde"] == pytest.approx(2.5)
    fig = plot_lorenz_postgroottes(cv=1.0, compact=True)
    assert fig.get_size_inches()[0] < 6


def test_lorenz_per_type_post_tekent_een_lijn_per_type():
    from auditstat.sso.plot_postgroottes import plot_lorenz_per_type_post

    fig = plot_lorenz_per_type_post({"A": 0.0, "B": 1.0, "C": 2.5})
    assert len(fig.axes[0].lines) == 4  # diagonaal + 3 typen
    with pytest.raises(ValueError):
        plot_lorenz_per_type_post({})


def test_pareto_ecdf_strip_figuren():
    from auditstat.sso.plot_postgroottes import (
        plot_ecdf_postgroottes,
        plot_pareto_postgroottes,
        plot_strip_postgroottes,
        simuleer_gamma_posten,
    )

    w = simuleer_gamma_posten(1.0, 500.0, 3000)
    assert w.mean() == pytest.approx(500.0, rel=0.1)
    assert w.std() / w.mean() == pytest.approx(1.0, rel=0.1)
    fig = plot_pareto_postgroottes(w, compact=True)
    lijn = fig.axes[0].lines[0]
    assert lijn.get_ydata()[-1] == pytest.approx(1.0)
    plot_ecdf_postgroottes({"a": w, "b": w * 2})
    plot_strip_postgroottes({"a": w}, compact=True)
    plot_pareto_postgroottes([1.0, 2.0, 3.0])
    assert np.all(simuleer_gamma_posten(0.0, 7.0, 10) == 7.0)
    with pytest.raises(ValueError):
        plot_ecdf_postgroottes({"a": [0.0, 1.0]})
    with pytest.raises(ValueError):
        plot_strip_postgroottes({})


def test_ecdf_en_strip_met_meerdere_typen_posten():
    from auditstat.sso.plot_postgroottes import (
        plot_ecdf_postgroottes,
        plot_strip_postgroottes,
        simuleer_gamma_posten,
    )

    g = {
        "A": simuleer_gamma_posten(0.5, 500.0, 500),
        "B": simuleer_gamma_posten(2.0, 400.0, 500, seed=1),
    }
    fig = plot_strip_postgroottes(g, compact=True)
    assert [t.get_text() for t in fig.axes[0].get_yticklabels()] == ["A", "B"]
    assert len(plot_ecdf_postgroottes(g).axes[0].lines) == 2


def test_omgekeerde_lorenz_histogram_overschrijding():
    from auditstat.sso.plot_postgroottes import (
        plot_histogram_postgroottes,
        plot_omgekeerde_lorenz_postgroottes,
        plot_overschrijdingscurve_postgroottes,
        simuleer_gamma_posten,
    )

    w = simuleer_gamma_posten(1.0, 500.0, 2000)
    g = {"A": w, "B": w * 3}
    lijn = plot_omgekeerde_lorenz_postgroottes(w).axes[0].lines[1]
    assert lijn.get_ydata()[-1] == pytest.approx(1.0)
    assert lijn.get_ydata()[10] >= lijn.get_xdata()[10]  # boven de diagonaal
    plot_histogram_postgroottes(w, compact=True)
    plot_histogram_postgroottes(g)
    fig = plot_overschrijdingscurve_postgroottes(g)
    assert fig.axes[0].get_yscale() == "log"
    assert fig.axes[0].lines[0].get_ydata()[0] == pytest.approx(1.0)
    for f in (
        plot_omgekeerde_lorenz_postgroottes,
        plot_histogram_postgroottes,
        plot_overschrijdingscurve_postgroottes,
    ):
        with pytest.raises(ValueError):
            f({})


def test_simuleer_gamma_posten_blijft_positief_bij_zeer_grote_cv():
    from auditstat.sso.plot_postgroottes import (
        plot_pareto_postgroottes,
        simuleer_gamma_posten,
    )

    w = simuleer_gamma_posten(10.0, 500.0, 5000)
    assert np.all(w > 0)
    plot_pareto_postgroottes(w, compact=True)


def test_gesimuleerde_posten_zijn_hele_centen():
    from auditstat.sso.plot_postgroottes import simuleer_gamma_posten

    for cv in (0.0, 0.5, 3.0, 10.0):
        w = simuleer_gamma_posten(cv, 500.0, 5000)
        assert np.all(w >= 0.01)
        assert np.allclose(w * 100, np.round(w * 100))
    assert simuleer_gamma_posten(0.0, 12.34, 3).tolist() == [12.34] * 3
    assert simuleer_gamma_posten(10.0, 500.0, 5000).size == 5000
    assert simuleer_gamma_posten(0.0, 0.001, 5).tolist() == [0.01] * 5
