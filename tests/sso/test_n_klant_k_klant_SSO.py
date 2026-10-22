import unittest

from auditstat.sso.n_klant_k_klant_SSO import n_klant_k_klant_SSO


class TestNKlantKKlantSSO(unittest.TestCase):
    def test_formule(self):
        n, k, N_klant = 100, 4, 100
        n_klant, k_klant = n_klant_k_klant_SSO(n, k, N_klant)
        self.assertAlmostEqual(n_klant, (n * N_klant) / (n + N_klant))
        self.assertAlmostEqual(k_klant, (n_klant / n) * k)

    def test_n_klant_kleiner_dan_n_en_N_klant(self):
        n_klant, _ = n_klant_k_klant_SSO(n=200, k=0, N_klant=1500)
        self.assertLess(n_klant, 200)
        self.assertLess(n_klant, 1500)

    def test_n_niet_positief(self):
        with self.assertRaises(ValueError):
            n_klant_k_klant_SSO(n=0, k=0, N_klant=100)

    def test_N_klant_niet_positief(self):
        with self.assertRaises(ValueError):
            n_klant_k_klant_SSO(n=100, k=0, N_klant=0)

    def test_k_negatief(self):
        with self.assertRaises(ValueError):
            n_klant_k_klant_SSO(n=100, k=-1, N_klant=100)

    def test_k_groter_dan_n(self):
        with self.assertRaises(ValueError):
            n_klant_k_klant_SSO(n=100, k=101, N_klant=100)


if __name__ == "__main__":
    unittest.main()
