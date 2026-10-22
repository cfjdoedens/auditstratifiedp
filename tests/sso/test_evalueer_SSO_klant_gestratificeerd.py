import unittest

from auditstat.sso.evalueer_SSO_klant_gestratificeerd import (
    evalueer_SSO_klant_gestratificeerd,
)


class TestEvalueerSSOKlantGestratificeerd(unittest.TestCase):
    def setUp(self):
        self.post_typen = [
            dict(
                naam="Emolumenten",
                n=120,
                k=1,
                N_klant=400,
                waarde_laag=2_000_000.0,
                materialiteit=0.02,
            ),
            dict(
                naam="Inkoopfacturen",
                n=200,
                k=1,
                N_klant=1500,
                waarde_laag=5_000_000.0,
                materialiteit=0.01,
            ),
        ]

    def test_resultaat_bevat_verwachte_sleutels(self):
        res = evalueer_SSO_klant_gestratificeerd(self.post_typen, zekerheid=0.95)
        for sleutel in (
            "max_fout_convolutie",
            "max_fout_convolutie_geld",
            "populatie_totaal",
            "kanskromme",
            "steekproeven",
        ):
            self.assertIn(sleutel, res)

    def test_populatie_totaal_is_som_van_waarde_laag(self):
        res = evalueer_SSO_klant_gestratificeerd(self.post_typen, zekerheid=0.95)
        self.assertAlmostEqual(res["populatie_totaal"], 7_000_000.0)

    def test_max_fout_binnen_plausibele_grenzen(self):
        res = evalueer_SSO_klant_gestratificeerd(self.post_typen, zekerheid=0.95)
        self.assertGreater(res["max_fout_convolutie"], 0.0)
        self.assertLess(res["max_fout_convolutie"], 1.0)
        self.assertLessEqual(res["max_fout_convolutie_geld"], res["populatie_totaal"])


if __name__ == "__main__":
    unittest.main()
