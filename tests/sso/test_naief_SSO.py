import pytest

from auditstat.sso.naief_SSO import naief_match_SSO


def test_grens_grote_N_klant_nadert_n():
    n_eff, k_eff = naief_match_SSO(n=100, k=5, N_klant=1_000_000)
    assert n_eff == pytest.approx(100, rel=1e-3)
    assert k_eff == pytest.approx(5, rel=1e-3)


def test_grens_kleine_N_klant_nadert_N_klant():
    n_eff, k_eff = naief_match_SSO(n=1_000_000, k=50_000, N_klant=10)
    assert n_eff == pytest.approx(10, rel=1e-3)
    # foutfractie k/n = 0.05 blijft behouden
    assert k_eff == pytest.approx(0.5, rel=1e-3)


def test_foutfractie_blijft_behouden():
    n, k, N_klant = 120, 6, 300
    n_eff, k_eff = naief_match_SSO(n, k, N_klant)
    assert k_eff / n_eff == pytest.approx(k / n)


def test_parallelformule():
    n, k, N_klant = 80, 2, 50
    n_eff, k_eff = naief_match_SSO(n, k, N_klant)
    assert n_eff == pytest.approx(n * N_klant / (n + N_klant))


@pytest.mark.parametrize(
    "n,k,N_klant",
    [
        (0, 0, 10),
        (-5, 0, 10),
        (10, 0, 0),
        (10, 0, -5),
        (10, -1, 5),
        (10, 11, 5),
    ],
)
def test_ongeldige_invoer_geeft_value_error(n, k, N_klant):
    with pytest.raises(ValueError):
        naief_match_SSO(n, k, N_klant)
