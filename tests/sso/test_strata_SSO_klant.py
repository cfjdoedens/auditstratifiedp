import math
import unittest

from auditstat.sso.moment_match_SSO import moment_match_SSO
from auditstat.sso.strata_SSO_klant import bouw_strata_SSO_klant


class TestBouwStrataSSOKlant(unittest.TestCase):
    def test_basis_kolommen_en_waarden(self):
        post_typen = [
            dict(naam="Emolumenten", n=120, k=1, N_klant=400, waarde_laag=2_000_000.0),
            dict(
                naam="Inkoopfacturen", n=200, k=1, N_klant=1500, waarde_laag=5_000_000.0
            ),
        ]
        df = bouw_strata_SSO_klant(post_typen)

        self.assertEqual(list(df["naam"]), ["Emolumenten", "Inkoopfacturen"])
        self.assertEqual(list(df["waarde_laag"]), [2_000_000.0, 5_000_000.0])

        n_eff_0, k_eff_0 = moment_match_SSO(120, 1, 400, verdeling="binomiaal")
        self.assertEqual(df["n_laag"].iloc[0], max(round(n_eff_0), math.ceil(k_eff_0)))
        self.assertAlmostEqual(df["k_laag"].iloc[0], k_eff_0)

    def test_n_laag_is_geheel_getal_en_niet_kleiner_dan_k_laag(self):
        post_typen = [
            dict(naam="Emolumenten", n=120, k=1, N_klant=401, waarde_laag=2_000_000.0),
        ]
        df = bouw_strata_SSO_klant(post_typen)
        self.assertEqual(df["n_laag"].iloc[0], round(df["n_laag"].iloc[0]))
        self.assertGreaterEqual(df["n_laag"].iloc[0], df["k_laag"].iloc[0])

    def test_model_poisson_geeft_andere_kalibratie_dan_binomiaal(self):
        post_typen = [
            dict(naam="Emolumenten", n=60, k=2, N_klant=500, waarde_laag=2_000_000.0),
        ]
        df_binomiaal = bouw_strata_SSO_klant(post_typen, model="binomiaal")
        df_poisson = bouw_strata_SSO_klant(post_typen, model="poisson")
        self.assertNotAlmostEqual(
            df_binomiaal["k_laag"].iloc[0], df_poisson["k_laag"].iloc[0]
        )

    def test_optionele_kolommen_worden_doorgegeven(self):
        post_typen = [
            dict(
                naam="Emolumenten",
                n=120,
                k=1,
                N_klant=400,
                waarde_laag=2_000_000.0,
                ihr="M",
                materialiteit=0.02,
            ),
        ]
        df = bouw_strata_SSO_klant(post_typen)
        self.assertEqual(df["ihr"].iloc[0], "M")
        self.assertEqual(df["materialiteit"].iloc[0], 0.02)
        self.assertNotIn("ibr", df.columns)

    def test_lege_lijst(self):
        with self.assertRaises(ValueError):
            bouw_strata_SSO_klant([])

    def test_ontbrekende_naam(self):
        with self.assertRaises(ValueError):
            bouw_strata_SSO_klant([
                dict(n=120, k=1, N_klant=400, waarde_laag=2_000_000.0)
            ])

    def test_ontbrekend_verplicht_veld(self):
        with self.assertRaises(ValueError):
            bouw_strata_SSO_klant([
                dict(naam="Emolumenten", n=120, k=1, waarde_laag=2_000_000.0)
            ])


if __name__ == "__main__":
    unittest.main()
