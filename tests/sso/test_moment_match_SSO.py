import unittest

from scipy import stats

from auditstat.sso.max_fout_exact_continu_SSO import max_fout_exact_continu_SSO
from auditstat.sso.moment_match_SSO import moment_match_SSO
from auditstat.sso.n_klant_k_klant_SSO import n_klant_k_klant_SSO


def _kwantiel_beta(n_eff, k_eff, zekerheid):
    return stats.beta.ppf(zekerheid, k_eff + 1, n_eff - k_eff + 1)


def _kwantiel_gamma(n_eff, k_eff, zekerheid):
    return stats.gamma.ppf(zekerheid, a=k_eff + 1, scale=1.0 / n_eff)


class TestMomentMatchSSO(unittest.TestCase):
    def test_gekalibreerde_kwantiel_ligt_dichter_bij_exact_continu_dan_oude_pooling(
        self,
    ):
        n, k, N_klant, zekerheid = 60, 2, 500, 0.95
        exact_continu = max_fout_exact_continu_SSO(
            n, k, N_klant, zekerheid, "binomiaal"
        )

        n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        kwantiel_mm = _kwantiel_beta(n_eff, k_eff, zekerheid)

        n_oud, k_oud = n_klant_k_klant_SSO(n, k, N_klant)
        kwantiel_oud = _kwantiel_beta(n_oud, k_oud, zekerheid)

        self.assertLess(
            abs(kwantiel_mm - exact_continu), abs(kwantiel_oud - exact_continu)
        )

    def test_poisson_kwantiel_ligt_dichter_bij_exact_continu_dan_oude_pooling(self):
        n, k, N_klant, zekerheid = 60, 2, 500, 0.95
        exact_continu = max_fout_exact_continu_SSO(n, k, N_klant, zekerheid, "poisson")

        n_eff, k_eff = moment_match_SSO(n, k, N_klant, "poisson")
        kwantiel_mm = _kwantiel_gamma(n_eff, k_eff, zekerheid)

        n_oud, k_oud = n_klant_k_klant_SSO(n, k, N_klant)
        kwantiel_oud = _kwantiel_gamma(n_oud, k_oud, zekerheid)

        self.assertLess(
            abs(kwantiel_mm - exact_continu), abs(kwantiel_oud - exact_continu)
        )

    def test_gemiddelde_komt_overeen_met_posterior_gemiddelde(self):
        # Het gemiddelde van de samengestelde verdeling is gelijk aan het
        # Beta-posterior-gemiddelde van de SSO-steekproef, onafhankelijk
        # van N_klant; dit moet (bij een ruime N_klant) ook gelden voor
        # het gekalibreerde (n_eff, k_eff)-paar.
        n, k, N_klant = 200, 4, 5000
        n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        gemiddelde_mm = (k_eff + 1) / (n_eff + 2)
        gemiddelde_posterior = (k + 1) / (n + 2)
        self.assertAlmostEqual(gemiddelde_mm, gemiddelde_posterior, places=6)

    def test_kleine_N_klant_wordt_geklemd_met_waarschuwing(self):
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(10, 0, 2, "binomiaal")
        self.assertGreaterEqual(k_eff, 0.0)
        self.assertGreaterEqual(n_eff, k_eff)

    def test_k_gelijk_aan_n_wordt_geklemd_indien_nodig(self):
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(20, 20, 20, "binomiaal")
        self.assertGreaterEqual(n_eff, k_eff)

    def test_ongeldige_verdeling(self):
        with self.assertRaises(ValueError):
            moment_match_SSO(100, 0, 100, "onbekend")

    def test_n_niet_positief(self):
        with self.assertRaises(ValueError):
            moment_match_SSO(0, 0, 100, "binomiaal")

    def test_N_klant_niet_positief(self):
        with self.assertRaises(ValueError):
            moment_match_SSO(100, 0, 0, "binomiaal")

    def test_k_negatief(self):
        with self.assertRaises(ValueError):
            moment_match_SSO(100, -1, 100, "binomiaal")

    def test_k_groter_dan_n(self):
        with self.assertRaises(ValueError):
            moment_match_SSO(100, 101, 100, "binomiaal")


if __name__ == "__main__":
    unittest.main()
