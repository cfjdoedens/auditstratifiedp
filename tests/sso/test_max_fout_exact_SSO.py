import unittest

from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO


class TestMaxFoutExact(unittest.TestCase):
    def test_exact_binomiaal(self):
        fout = max_fout_exact_SSO(
            n=100, k=0, N_klant=100, zekerheid=0.95, verdeling="binomiaal"
        )
        self.assertTrue(
            0.02 < fout < 0.05
        )  # De exacte methode (ca 3.8%) is scherper dan de benadering

    def test_exact_poisson(self):
        fout = max_fout_exact_SSO(
            n=100, k=0, N_klant=100, zekerheid=0.95, verdeling="poisson"
        )
        self.assertTrue(0.02 < fout < 0.05)


if __name__ == "__main__":
    unittest.main()
