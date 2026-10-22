import unittest

import numpy as np
from scipy import stats

from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO
from auditstat.sso.max_fout_exact_continu_SSO import (
    _betabinom_continu_pdf,
    max_fout_exact_continu_SSO,
)
from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO


class TestBetabinomContinuPdf(unittest.TestCase):
    def test_komt_overeen_met_discrete_pmf_op_gehele_waarden(self):
        N_klant, alpha, beta = 500, 3.0, 59.0
        x_int = np.arange(0, N_klant + 1)
        discreet = stats.betabinom.pmf(x_int, N_klant, alpha, beta)
        continu = _betabinom_continu_pdf(x_int.astype(float), N_klant, alpha, beta)
        self.assertTrue(np.allclose(discreet, continu, atol=1e-10))

    def test_niet_negatief_tussen_gehele_waarden(self):
        dichtheid = _betabinom_continu_pdf(
            np.linspace(0, 100, 50), N_klant=100, alpha=3.0, beta=98.0
        )
        self.assertTrue(np.all(dichtheid >= 0))


class TestMaxFoutExactContinuSSO(unittest.TestCase):
    def test_binomiaal_ligt_tussen_discreet_exact_en_benaderd(self):
        n, k, N_klant = 60, 2, 500
        exact = max_fout_exact_SSO(n, k, N_klant, 0.95, "binomiaal")
        exact_continu = max_fout_exact_continu_SSO(n, k, N_klant, 0.95, "binomiaal")
        benaderd = max_fout_benaderd_SSO(n, k, N_klant, 0.95, "binomiaal")
        # Het continue exacte model behoudt beide onzekerheidslagen en
        # moet dus dicht bij de discrete exacte uitkomst liggen, duidelijk
        # onderscheiden van de (eenvoudiger) benaderde kortere weg.
        self.assertAlmostEqual(exact_continu, exact, delta=0.01)
        self.assertLess(exact_continu, benaderd)

    def test_poisson_ligt_tussen_discreet_exact_en_benaderd(self):
        n, k, N_klant = 60, 2, 500
        exact = max_fout_exact_SSO(n, k, N_klant, 0.95, "poisson")
        exact_continu = max_fout_exact_continu_SSO(n, k, N_klant, 0.95, "poisson")
        benaderd = max_fout_benaderd_SSO(n, k, N_klant, 0.95, "poisson")
        self.assertAlmostEqual(exact_continu, exact, delta=0.01)
        self.assertLess(exact_continu, benaderd)

    def test_poisson_komt_overeen_met_gesloten_vorm_identiteit(self):
        # De NB-CDF via de regularized incomplete beta-functie moet exact
        # overeenkomen met scipy.stats.nbinom.cdf op gehele waarden.
        n, k, N_klant = 60, 2, 500
        r = k + 1
        p_succes = n / (n + N_klant)
        x_int = np.arange(0, 50)
        from scipy.special import betainc

        self.assertTrue(
            np.allclose(
                stats.nbinom.cdf(x_int, r, p_succes),
                betainc(r, x_int + 1, p_succes),
            )
        )

    def test_hogere_zekerheid_geeft_hogere_max_fout(self):
        n, k, N_klant = 60, 2, 500
        laag = max_fout_exact_continu_SSO(n, k, N_klant, 0.80, "binomiaal")
        hoog = max_fout_exact_continu_SSO(n, k, N_klant, 0.99, "binomiaal")
        self.assertLess(laag, hoog)

    def test_resultaat_binnen_bereik(self):
        fout = max_fout_exact_continu_SSO(
            n=100, k=0, N_klant=100, zekerheid=0.95, verdeling="binomiaal"
        )
        self.assertTrue(0 <= fout <= 1)

    def test_ongeldige_verdeling(self):
        with self.assertRaises(ValueError):
            max_fout_exact_continu_SSO(100, 0, 100, 0.95, "onbekend")

    def test_N_klant_niet_positief(self):
        with self.assertRaises(ValueError):
            max_fout_exact_continu_SSO(100, 0, 0, 0.95, "binomiaal")

    def test_zekerheid_buiten_bereik(self):
        with self.assertRaises(ValueError):
            max_fout_exact_continu_SSO(100, 0, 100, 1.5, "binomiaal")


if __name__ == "__main__":
    unittest.main()
