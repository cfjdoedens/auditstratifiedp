import unittest

from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO


class TestMaxFoutBenaderd(unittest.TestCase):
    def test_benaderd_binomiaal(self):
        fout = max_fout_benaderd_SSO(
            n=100, k=0, N_klant=100, zekerheid=0.95, verdeling="binomiaal"
        )
        self.assertTrue(0.04 < fout < 0.07)  # Verwacht rond de 5-6%

    def test_benaderd_poisson(self):
        fout = max_fout_benaderd_SSO(
            n=100, k=0, N_klant=100, zekerheid=0.95, verdeling="poisson"
        )
        self.assertTrue(0.04 < fout < 0.07)


if __name__ == "__main__":
    unittest.main()
