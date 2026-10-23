import unittest

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

from auditstat.sso.plot_posterior_heterogeen_SSO import plot_posterior_heterogeen_SSO


class TestPlotPosteriorHeterogeenSSO(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_geeft_figure_terug(self):
        fig = plot_posterior_heterogeen_SSO(60, 2, f_waarden=[0.5, 0.05, 0.005])
        self.assertIsInstance(fig, matplotlib.figure.Figure)

    def test_werkt_voor_beide_verdelingen(self):
        for verdeling in ("binomiaal", "poisson"):
            with self.subTest(verdeling=verdeling):
                fig = plot_posterior_heterogeen_SSO(
                    60, 2, f_waarden=[0.2, 0.02], verdeling=verdeling
                )
                self.assertIsInstance(fig, matplotlib.figure.Figure)

    def test_werkt_met_enkele_f_waarde(self):
        fig = plot_posterior_heterogeen_SSO(60, 2, f_waarden=0.1)
        self.assertIsInstance(fig, matplotlib.figure.Figure)

    def test_lege_f_waarden(self):
        with self.assertRaises(ValueError):
            plot_posterior_heterogeen_SSO(60, 2, f_waarden=[])

    def test_f_waarde_buiten_bereik(self):
        with self.assertRaises(ValueError):
            plot_posterior_heterogeen_SSO(60, 2, f_waarden=[0.5, 1.5])

    def test_ongeldige_verdeling(self):
        with self.assertRaises(ValueError):
            plot_posterior_heterogeen_SSO(60, 2, f_waarden=[0.5], verdeling="onbekend")

    def test_zekerheid_buiten_bereik(self):
        with self.assertRaises(ValueError):
            plot_posterior_heterogeen_SSO(60, 2, f_waarden=[0.5], zekerheid=1.5)


if __name__ == "__main__":
    unittest.main()
