import unittest

from scipy.stats import beta

from auditstat.sso.moment_match_SSO import _naieve_pooling, moment_match_SSO


def _max_fout_95(n_eff, k_eff):
    return beta.ppf(0.95, k_eff + 1, n_eff - k_eff + 1)


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

    def test_geklemd_resultaat_is_minstens_zo_conservatief_als_naief(self):
        # Bij klemming wordt vergeleken met de naïeve-poolingmethode en de
        # conservatiefste (hoogste maximale foutfractie bij 95% zekerheid)
        # van de twee aangehouden: het resultaat mag dus nooit minder
        # conservatief zijn dan de naïeve pooling zelf.
        n, k, N_klant = 120, 1, 100
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        n_naief, k_naief = _naieve_pooling(n, k, N_klant)
        self.assertGreaterEqual(
            _max_fout_95(n_eff, k_eff), _max_fout_95(n_naief, k_naief)
        )

    def test_geklemd_kiest_naieve_pooling_bij_matig_kleine_N_klant(self):
        # Bij een matig kleine N_klant (klem treedt op, maar niet extreem)
        # is naïeve pooling de conservatievere van de twee kandidaten.
        n, k, N_klant = 120, 1, 100
        n_naief, k_naief = _naieve_pooling(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertAlmostEqual(n_eff, n_naief, places=6)
        self.assertAlmostEqual(k_eff, k_naief, places=6)

    def test_geklemd_behoudt_momentmatching_bij_zeer_kleine_N_klant(self):
        # Bij een zeer kleine N_klant (extreme klem) is de geklemde
        # momentmatching zelf juist conservatiever dan naïeve pooling, en
        # moet die dus behouden blijven in plaats van overschreven te worden.
        n, k, N_klant = 120, 1, 5
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        n_naief, k_naief = _naieve_pooling(n, k, N_klant)
        self.assertGreater(_max_fout_95(n_eff, k_eff), _max_fout_95(n_naief, k_naief))

    def test_geklemde_fallback_ook_voor_poisson(self):
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(120, 1, 5, "poisson")
        self.assertGreaterEqual(k_eff, 0.0)
        self.assertGreaterEqual(n_eff, k_eff)
        self.assertGreater(n_eff, 0.0)


if __name__ == "__main__":
    unittest.main()
