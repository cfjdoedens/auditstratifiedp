import unittest

from scipy.stats import beta, betabinom, gamma, nbinom

from auditstat.sso.moment_match_SSO import moment_match_SSO


def _max_fout_95(n_eff, k_eff):
    return beta.ppf(0.95, k_eff + 1, n_eff - k_eff + 1)


def _max_fout_exact_binomiaal(n, k, N_klant, zekerheid=0.95):
    return betabinom.ppf(zekerheid, N_klant, k + 1, n - k + 1) / N_klant


def _max_fout_exact_poisson(n, k, N_klant, zekerheid=0.95):
    return nbinom.ppf(zekerheid, k + 1, n / (n + N_klant)) / N_klant


class TestMomentMatchSSO(unittest.TestCase):
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

    def test_geklemd_binomiaal_matcht_exacte_grens(self):
        # Bij klemming (k_eff < 0) wordt k_eff op 0 gezet en n_eff zo
        # gekozen dat de 95%-kwantiel van de resulterende Beta-verdeling
        # exact gelijk is aan de werkelijke Beta-Binomiale grens.
        n, k, N_klant = 120, 1, 100
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertEqual(k_eff, 0.0)
        self.assertAlmostEqual(_max_fout_95(n_eff, k_eff), exact, places=6)

    def test_geklemd_binomiaal_matcht_exacte_grens_bij_zeer_kleine_N_klant(self):
        n, k, N_klant = 120, 1, 5
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertEqual(k_eff, 0.0)
        self.assertAlmostEqual(_max_fout_95(n_eff, k_eff), exact, places=6)

    def test_geklemd_poisson_matcht_exacte_grens(self):
        n, k, N_klant = 120, 1, 5
        exact = _max_fout_exact_poisson(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "poisson")
        self.assertEqual(k_eff, 0.0)
        mf = gamma.ppf(0.95, a=k_eff + 1, scale=1.0 / n_eff)
        self.assertAlmostEqual(mf, exact, places=6)
        self.assertGreater(n_eff, 0.0)

    def test_geklemd_binomiaal_is_minstens_zo_conservatief_als_exact(self):
        # Ook in het extreme randgeval (exacte grens zelf dicht bij of
        # boven de haalbare Beta-kwantiel) mag het resultaat de werkelijke
        # grens niet onderschatten.
        n, k, N_klant = 120, 5, 2
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        self.assertGreaterEqual(_max_fout_95(n_eff, k_eff) + 1e-9, min(exact, 0.95))


if __name__ == "__main__":
    unittest.main()
