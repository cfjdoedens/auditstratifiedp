import numpy as np
import pytest

from auditstat.sso.compound_postwaarden import (
    aantal_fouten_venster,
    kansmassa_compound,
)
from auditstat.sso.evalueer_SSO_klant_exact import evalueer_SSO_klant_exact
from auditstat.sso.moment_match_SSO import moment_match_SSO
from auditstat.sso.naief_SSO import naief_match_SSO
from auditstat.sso.strata_SSO_klant import bouw_strata_SSO_klant


def _kwantiel(massa, dx, waarde, q):
    return np.searchsorted(np.cumsum(massa), q) * dx / waarde


def _mc_gamma(n, k, N, w, cv, R=300_000, seed=4821):
    rng = np.random.default_rng(seed)
    p = rng.beta(k + 1, n - k + 1, R)
    aantal = rng.binomial(N, p)
    alfa, theta = 1 / cv**2, (w / N) * cv**2
    return np.where(aantal > 0, rng.gamma(np.maximum(aantal, 1) * alfa, theta), 0.0)


def test_venster_is_genormaliseerd_en_bevat_het_gemiddelde():
    k0, pmf = aantal_fouten_venster("binomiaal", 100, 2, 1000)
    assert pmf.sum() == pytest.approx(1.0)
    gemiddelde = k0 + (np.arange(len(pmf)) * pmf).sum()
    # E[K] = N * (k+1)/(n+2)
    assert gemiddelde == pytest.approx(1000 * 3 / 102, rel=1e-4)


@pytest.mark.parametrize(
    "n,k,N,w,cv",
    [(100, 2, 2000, 1e6, 1.0), (60, 0, 200, 1e5, 2.0), (40, 1, 30, 1e4, 3.0)],
)
def test_gamma_komt_overeen_met_monte_carlo(n, k, N, w, cv):
    dx = w / 20_000
    massa = kansmassa_compound("binomiaal", n, k, N, w, ("gamma", cv), dx)
    assert massa.sum() == pytest.approx(1.0)
    e = _mc_gamma(n, k, N, w, cv)
    exact = _kwantiel(massa, dx, w, 0.95)
    mc = np.quantile(e, 0.95) / w
    # Het rooster rondt naar boven af: nooit duidelijk te laag.
    assert exact >= mc - 0.004
    assert exact == pytest.approx(mc, abs=0.006 + 0.02 * mc)


def test_empirisch_komt_overeen_met_monte_carlo():
    rng = np.random.default_rng(6112)
    y = rng.lognormal(0, 1, 1000)
    n, k, N, w = 100, 2, 1000, 5e5
    dx = w / 20_000
    massa = kansmassa_compound("binomiaal", n, k, N, w, y, dx)
    r = np.random.default_rng(77)
    p = r.beta(k + 1, n - k + 1, 20_000)
    aantal = r.binomial(N, p)
    z = y * (w / N / y.mean())
    e = np.array([z[r.integers(0, N, a)].sum() for a in aantal])
    assert _kwantiel(massa, dx, w, 0.95) == pytest.approx(
        np.quantile(e, 0.95) / w, abs=0.004
    )


def test_poisson_massa_is_genormaliseerd():
    massa = kansmassa_compound("poisson", 100, 2, 2000, 1e6, ("gamma", 1.0), 50.0)
    assert massa.sum() == pytest.approx(1.0)
    assert (massa >= 0).all()


def test_kleine_cv_benadert_gelijke_posten():
    post = {"naam": "a", "n": 100, "k": 2, "N_klant": 2000, "waarde_laag": 1e6}
    basis = evalueer_SSO_klant_exact([post])["max_fout_convolutie"]
    klein = evalueer_SSO_klant_exact([{**post, "cv": 0.01}])["max_fout_convolutie"]
    assert klein == pytest.approx(basis, abs=0.002)


def test_grotere_cv_geeft_ruimere_grens():
    post = {"naam": "a", "n": 100, "k": 2, "N_klant": 2000, "waarde_laag": 1e6}
    grenzen = [
        evalueer_SSO_klant_exact([{**post, "cv": cv}])["max_fout_convolutie"]
        for cv in (0.0, 1.0, 3.0)
    ]
    assert grenzen[0] < grenzen[1] < grenzen[2]


def test_postwaarden_geven_cv_in_steekproeventabel():
    y = np.random.default_rng(3).lognormal(0, 0.5, 500)
    post = {
        "naam": "a",
        "n": 100,
        "k": 2,
        "N_klant": 500,
        "waarde_laag": 1e5,
        "postwaarden": y,
    }
    res = evalueer_SSO_klant_exact([post])
    assert res["steekproeven"]["cv"].iloc[0] == pytest.approx(y.std() / y.mean())


@pytest.mark.parametrize(
    "extra,melding",
    [
        ({"cv": -1.0}, "cv moet"),
        ({"cv": float("nan")}, "cv moet"),
        ({"postwaarden": []}, "niet-lege"),
        ({"postwaarden": [1.0, -2.0]}, "positief"),
    ],
)
def test_ongeldige_invoer_wordt_geweigerd(extra, melding):
    post = {"naam": "a", "n": 100, "k": 2, "N_klant": 500, "waarde_laag": 1e5, **extra}
    with pytest.raises(ValueError, match=melding):
        evalueer_SSO_klant_exact([post])


def test_naief_cv_nul_is_ongewijzigd_en_cv_verkleint_n_eff():
    assert naief_match_SSO(100, 2, 1000, cv=0.0) == naief_match_SSO(100, 2, 1000)
    n_eff, k_eff = naief_match_SSO(100, 2, 1000, cv=1.0)
    assert n_eff == pytest.approx(100 * 1000 / (1000 + 100 * 2))
    assert k_eff == pytest.approx(2 * n_eff / 100)
    # Gelijkwaardig aan N_klant / (1 + cv^2) in de parallelformule.
    assert n_eff == pytest.approx(naief_match_SSO(100, 2, 500)[0])
    with pytest.raises(ValueError, match="cv"):
        naief_match_SSO(100, 2, 1000, cv=-0.1)


@pytest.mark.parametrize("verdeling", ["binomiaal", "poisson"])
def test_momentmatching_cv_matcht_de_variantie(verdeling):
    n, k, N, cv = 200, 4, 5000, 1.5
    n_eff, k_eff = moment_match_SSO(n, k, N, verdeling=verdeling, cv=cv)
    n0, k0 = moment_match_SSO(n, k, N, verdeling=verdeling)
    assert n_eff < n0  # meer variantie -> minder effectieve steekproef
    if verdeling == "binomiaal":
        a, b = k + 1, n - k + 1
        s = a + b
        doel = a * b * (s + N) / (s**2 * (s + 1) * N) + cv**2 * (a / s) / N
        a_eff, b_eff = k_eff + 1, n_eff - k_eff + 1
        s_eff = a_eff + b_eff
        assert a_eff * b_eff / (s_eff**2 * (s_eff + 1)) == pytest.approx(doel)
    assert moment_match_SSO(n, k, N, verdeling=verdeling, cv=0.0) == (n0, k0)


def test_momentmatching_cv_bij_klemming_gebruikt_numerieke_grens():
    with pytest.warns(RuntimeWarning, match="gekalibreerd"):
        n_eff, k_eff = moment_match_SSO(120, 1, 20, cv=1.0)
    assert k_eff == 0.0 and n_eff >= 0


def test_strata_geeft_cv_door():
    basis = {"naam": "a", "n": 100, "k": 2, "N_klant": 2000, "waarde_laag": 1e6}
    zonder = bouw_strata_SSO_klant([basis], kalibratiemethode="naief")
    met = bouw_strata_SSO_klant([{**basis, "cv": 2.0}], kalibratiemethode="naief")
    assert met["n_laag"].iloc[0] < zonder["n_laag"].iloc[0]
    with pytest.raises(ValueError, match="cv"):
        bouw_strata_SSO_klant([{**basis, "cv": -1}])


def test_voortgang_loopt_van_0_naar_bijna_1_en_verandert_uitkomst_niet():
    import numpy as np

    from auditstat.sso.compound_postwaarden import kansmassa_compound

    w = np.linspace(100, 900, 500)
    meldingen = []
    met = kansmassa_compound(
        "binomiaal", 100, 1, 2000, 1_000_000.0, w, 50.0, voortgang=meldingen.append
    )
    zonder = kansmassa_compound("binomiaal", 100, 1, 2000, 1_000_000.0, w, 50.0)
    assert np.array_equal(met, zonder)
    assert meldingen and meldingen[0] == 0.0
    assert all(0.0 <= m < 1.0 for m in meldingen)
    assert meldingen == sorted(meldingen)


def test_schatting_rekentijd_groeit_met_n_klant_en_geeft_none_bij_fout():
    import numpy as np

    from auditstat.sso.evalueer_SSO_klant_exact import schat_rekentijd_exact

    w = np.linspace(100, 900, 500)

    def post(N, **extra):
        return {
            "naam": "t",
            "n": 100,
            "k": 1,
            "N_klant": N,
            "waarde_laag": N * 500.0,
            **extra,
        }

    klein = schat_rekentijd_exact([post(2000, postwaarden=w)])
    groot = schat_rekentijd_exact([post(40000, postwaarden=w)])
    assert 0 <= klein < groot
    assert schat_rekentijd_exact([post(2000)]) == 0.0
    assert schat_rekentijd_exact([post(5_000_000, postwaarden=w)]) is None


def test_venster_aantal_fouten_loopt_niet_door_tot_n():
    import numpy as np

    from auditstat.sso.compound_postwaarden import aantal_fouten_venster

    # Regressie: door afrondingsfouten in de pmf haalde de cumulatieve som nooit
    # 1 - 1e-12 en liep het venster door tot K = N (100.001 i.p.v. ~15.700).
    laag, venster = aantal_fouten_venster("binomiaal", 200, 2, 100_000)
    assert len(venster) < 20_000
    assert abs(venster.sum() - 1.0) < 1e-12
    assert laag + len(venster) - 1 >= 15_000
    assert np.all(venster >= 0)


def test_te_groot_venster_geeft_value_error_met_limiet():
    import numpy as np

    from auditstat.sso.compound_postwaarden import (
        MAX_K_VENSTER,
        schat_rekentijd_compound,
    )

    assert MAX_K_VENSTER == 1_000_000
    z = np.linspace(100, 900, 500)
    # n=100, k=5: venster ca. 0,34 x N_klant, dus 10 mln posten is te groot.
    N = 10_000_000
    with pytest.raises(ValueError, match=r"maximaal 1\.000\.000"):
        schat_rekentijd_compound("binomiaal", 100, 5, N, N * 500.0, z, N * 25.0)
    # N_klant 1 mln (venster ca. 0,34 mln) valt binnen de limiet.
    N = 1_000_000
    assert schat_rekentijd_compound("binomiaal", 100, 5, N, N * 500.0, z, N * 25.0) > 0
