import unittest

import numpy as np
from scipy import stats

from auditstat.sso.max_fout_exact_continu_SSO import max_fout_exact_continu_SSO
from auditstat.sso.max_fout_heterogeen_SSO import max_fout_heterogeen_SSO


class TestMaxFoutHeterogeenSSO(unittest.TestCase):
    def test_f_is_1_komt_overeen_met_uitwisselbaar_model_binomiaal(self):
        # Bij f=1 horen alle steekproefposten per definitie bij klant X:
        # dit moet exact samenvallen met de bestaande Beta(k+1, n-k+1)
        # posterior van het uitwisselbare model.
        n, k = 60, 2
        q95_heterogeen = max_fout_heterogeen_SSO(n, k, f=1.0, zekerheid=0.95)
        q95_referentie = stats.beta(k + 1, n - k + 1).ppf(0.95)
        self.assertAlmostEqual(q95_heterogeen, q95_referentie, places=3)

    def test_f_is_1_komt_overeen_met_uitwisselbaar_model_poisson(self):
        # Bij f=1 en verdeling="poisson" moet dit samenvallen met de
        # (op [0, 1] getrunceerde) Gamma(k+1, rate=n) posterior.
        n, k = 60, 2
        q95_heterogeen = max_fout_heterogeen_SSO(
            n, k, f=1.0, zekerheid=0.95, verdeling="poisson"
        )
        theta = np.linspace(0, 1, 20001)
        cdf = stats.gamma(k + 1, scale=1 / n).cdf(theta)
        cdf = cdf / cdf[-1]
        q95_referentie = float(np.interp(0.95, cdf, theta))
        self.assertAlmostEqual(q95_heterogeen, q95_referentie, places=3)

    def test_f_is_0_geeft_de_vlakke_prior_terug(self):
        # Bij f=0 bevat de SSO-brede steekproef geen informatie over
        # klant X: de posterior blijft de vlakke prior, dus het
        # p-kwantiel van een uniforme verdeling op [0, 1] is p zelf.
        n, k = 60, 2
        for verdeling in ("binomiaal", "poisson"):
            with self.subTest(verdeling=verdeling):
                q95 = max_fout_heterogeen_SSO(
                    n, k, f=0.0, zekerheid=0.95, verdeling=verdeling
                )
                self.assertAlmostEqual(q95, 0.95, places=3)

    def test_kleinere_f_geeft_grotere_onzekerheid(self):
        # Een kleiner aandeel van klant X in de SSO-populatie betekent
        # dat de SSO-brede steekproef minder klant-specifieke informatie
        # bevat; het 95%-kwantiel moet dan dichter bij dat van de vlakke
        # prior (0.95) liggen, dus hoger zijn naarmate f kleiner wordt.
        n, k = 60, 2
        for verdeling in ("binomiaal", "poisson"):
            with self.subTest(verdeling=verdeling):
                q_groot_f = max_fout_heterogeen_SSO(n, k, f=0.5, verdeling=verdeling)
                q_klein_f = max_fout_heterogeen_SSO(n, k, f=0.05, verdeling=verdeling)
                q_zeer_klein_f = max_fout_heterogeen_SSO(
                    n, k, f=0.005, verdeling=verdeling
                )
                self.assertLess(q_groot_f, q_klein_f)
                self.assertLess(q_klein_f, q_zeer_klein_f)

    def test_overconfident_versus_uitwisselbaar_model_bij_kleine_klant(self):
        # Voor een klein, specifiek client-aandeel moet het heterogene
        # model een duidelijk ruimere (minder optimistische) maximale
        # foutfractie opleveren dan het bestaande uitwisselbare model,
        # dat de SSO-brede schatting zonder correctie op elke klant
        # projecteert, ongeacht de omvang van die klant.
        n, k, N_klant = 60, 2, 500
        q95_uitwisselbaar = max_fout_exact_continu_SSO(n, k, N_klant, 0.95)
        q95_heterogeen = max_fout_heterogeen_SSO(n, k, f=0.01, zekerheid=0.95)
        self.assertGreater(q95_heterogeen, q95_uitwisselbaar)

    def test_hogere_zekerheid_geeft_hogere_max_fout(self):
        n, k = 60, 2
        laag = max_fout_heterogeen_SSO(n, k, f=0.1, zekerheid=0.80)
        hoog = max_fout_heterogeen_SSO(n, k, f=0.1, zekerheid=0.99)
        self.assertLess(laag, hoog)

    def test_resultaat_binnen_bereik(self):
        for verdeling in ("binomiaal", "poisson"):
            fout = max_fout_heterogeen_SSO(
                n=100, k=0, f=0.2, zekerheid=0.95, verdeling=verdeling
            )
            self.assertTrue(0 <= fout <= 1)

    def test_ongeldige_verdeling(self):
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(100, 0, f=0.5, verdeling="onbekend")

    def test_n_niet_positief(self):
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(0, 0, f=0.5)

    def test_k_negatief(self):
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(100, -1, f=0.5)

    def test_k_groter_dan_n(self):
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(100, 101, f=0.5)

    def test_f_buiten_bereik(self):
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(100, 0, f=1.5)
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(100, 0, f=-0.1)

    def test_zekerheid_buiten_bereik(self):
        with self.assertRaises(ValueError):
            max_fout_heterogeen_SSO(100, 0, f=0.5, zekerheid=1.5)


if __name__ == "__main__":
    unittest.main()
