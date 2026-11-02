import matplotlib
import numpy as np
import pytest
from scipy.stats import beta, betabinom

from auditstat.sso.evalueer_SSO_klant_exact import (
    STANDAARD_GRANULARITEIT,
    _cdf_aantal_fouten,
    evalueer_SSO_klant_exact,
)
from auditstat.sso.moment_match_SSO import _max_fout_exact
from auditstat.stratified.plot_kanskromme import plot_kanskromme

matplotlib.use("Agg")

# Eén roostercel is 1/granulariteit van de totale waarde breed; de grens is
# naar boven afgerond, dus (bij één stratum) 0 <= verschil < 1/granulariteit.
CEL = 1 / STANDAARD_GRANULARITEIT


def _post(naam, n, k, N, w):
    return {"naam": naam, "n": n, "k": k, "N_klant": N, "waarde_laag": w}


def _monte_carlo(post_typen, model, zekerheid, R=400_000, seed=6194):
    rng = np.random.default_rng(seed)
    totaal = sum(p["waarde_laag"] for p in post_typen)
    fout = np.zeros(R)
    for p in post_typen:
        if model == "binomiaal":
            kans = rng.beta(p["k"] + 1, p["n"] - p["k"] + 1, R)
            x = rng.binomial(p["N_klant"], kans)
        else:
            kans = rng.gamma(p["k"] + 1, 1 / p["n"], R)
            x = rng.poisson(p["N_klant"] * kans)
        fout += p["waarde_laag"] * np.minimum(x / p["N_klant"], 1.0)
    return np.quantile(fout, zekerheid) / totaal


@pytest.mark.parametrize("model", ["binomiaal", "poisson"])
@pytest.mark.parametrize(
    "n, k, N",
    [(120, 1, 100), (120, 1, 20), (100, 0, 1000), (80, 3, 1200), (108, 2, 100_000)],
)
@pytest.mark.parametrize("zekerheid", [0.9, 0.95, 0.99])
def test_een_stratum_komt_overeen_met_max_fout_exact(model, n, k, N, zekerheid):
    res = evalueer_SSO_klant_exact(
        [_post("a", n, k, N, 500_000.0)], model=model, zekerheid=zekerheid
    )
    verwacht = min(_max_fout_exact(n, k, N, model, zekerheid), 1.0)
    verschil = res["max_fout_convolutie"] - verwacht
    assert -1e-9 <= verschil < CEL + 1e-9


@pytest.mark.parametrize("model", ["binomiaal", "poisson"])
@pytest.mark.parametrize(
    "post_typen",
    [
        [
            _post("Emol", 120, 1, 1800, 900_000.0),
            _post("Inkoop", 80, 3, 1200, 600_000.0),
        ],
        [_post("x", 120, 1, 100, 500_000.0), _post("y", 80, 3, 50, 500_000.0)],
        [
            _post(f"t{i}", 60 + 10 * i, i % 3, 400 + 200 * i, 200_000.0)
            for i in range(5)
        ],
        [
            _post("groot", 150, 2, 5000, 9_990_000.0),
            _post("klein", 100, 1, 300, 10_000.0),
        ],
    ],
)
def test_meerdere_strata_komt_overeen_met_monte_carlo(model, post_typen):
    res = evalueer_SSO_klant_exact(post_typen, model=model)
    mc = _monte_carlo(post_typen, model, 0.95)
    # MC-ruis (sd <= ~0,00016 bij 4e5 trekkingen) plus roosterfout (<~0,0002).
    assert abs(res["max_fout_convolutie"] - mc) < 0.001


def test_groot_aantal_posten_nadert_beta_grens():
    n, k, N = 108, 2, 2_000_000
    res = evalueer_SSO_klant_exact([_post("a", n, k, N, 1_000_000.0)])
    beta_grens = beta.ppf(0.95, k + 1, n - k + 1)
    assert -1e-6 <= res["max_fout_convolutie"] - beta_grens < CEL + 1e-6


@pytest.mark.parametrize("N", [5, 50, 3000])
def test_snelle_cdf_gelijk_aan_scipy(N):
    n, k = 120, 3
    cdf = _cdf_aantal_fouten("binomiaal", n, k, N)
    j = np.arange(0, N + 1)
    assert np.allclose(cdf(j), betabinom.cdf(j, N, k + 1, n - k + 1), atol=1e-10)


def test_volgorde_van_strata_maakt_niet_uit():
    a = _post("a", 120, 1, 1800, 900_000.0)
    b = _post("b", 80, 3, 1200, 600_000.0)
    r1 = evalueer_SSO_klant_exact([a, b])
    r2 = evalueer_SSO_klant_exact([b, a])
    assert r1["max_fout_convolutie"] == pytest.approx(r2["max_fout_convolutie"])


def test_kanskromme_integreert_tot_een_en_resultaat_is_plotbaar():
    res = evalueer_SSO_klant_exact([
        _post("a", 120, 1, 1800, 900_000.0),
        _post("b", 80, 3, 1200, 600_000.0),
    ])
    x, y = res["kanskromme"]["x"], res["kanskromme"]["y"]
    assert np.sum(y) * (x[1] - x[0]) == pytest.approx(1.0)
    assert res["max_fout_convolutie_geld"] == pytest.approx(
        res["max_fout_convolutie"] * 1_500_000.0
    )
    fig = plot_kanskromme(res)
    assert fig is not None


def test_hogere_zekerheid_geeft_hogere_grens():
    post = [_post("a", 120, 1, 1800, 900_000.0)]
    grenzen = [
        evalueer_SSO_klant_exact(post, zekerheid=z)["max_fout_convolutie"]
        for z in (0.8, 0.9, 0.95, 0.99)
    ]
    assert grenzen == sorted(grenzen)


@pytest.mark.parametrize(
    "post_typen, kwargs, fragment",
    [
        ([], {}, "tenminste 1"),
        ([_post("", 100, 1, 100, 1.0)], {}, "naam"),
        ([_post("a", 100, 1, 100, 1.0), _post("a", 100, 1, 100, 1.0)], {}, "uniek"),
        ([_post("a", 100, 101, 100, 1.0)], {}, "k moet"),
        ([_post("a", 100, 1, 10.5, 1.0)], {}, "N_klant"),
        ([_post("a", 100, 1, 100, 0.0)], {}, "waarde_laag"),
        ([_post("a", 100, 1, 10**9, 1.0)], {}, "maximum"),
        (
            [{**_post("a", 100, 1, 100, 1.0), "waarde_hoog": 5.0}],
            {},
            "niet ondersteund",
        ),
        ([_post("a", 100, 1, 100, 1.0)], {"model": "x"}, "model"),
        ([_post("a", 100, 1, 100, 1.0)], {"zekerheid": 1.0}, "zekerheid"),
        ([_post("a", 100, 1, 100, 1.0)], {"granulariteit": 10}, "granulariteit"),
        ([{"naam": "a", "n": 1}], {}, "mist"),
    ],
)
def test_ongeldige_invoer(post_typen, kwargs, fragment):
    with pytest.raises(ValueError, match=fragment):
        evalueer_SSO_klant_exact(post_typen, **kwargs)
