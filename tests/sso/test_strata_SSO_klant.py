import math
import unittest
import warnings

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

    def test_klem_waarschuwing_bevat_naam_van_type_post(self):
        # N_klant=5 t.o.v. n=120 triggert klemming in moment_match_SSO; de
        # waarschuwing moet hier de naam van het type post bevatten, zodat
        # een aanroeper kan tonen voor welk type post is teruggevallen.
        post_typen = [
            dict(naam="Emolumenten", n=120, k=1, N_klant=5, waarde_laag=2_000_000.0),
        ]
        with self.assertWarns(RuntimeWarning) as gevangen:
            bouw_strata_SSO_klant(post_typen)
        self.assertTrue(any("Emolumenten" in str(w.message) for w in gevangen.warnings))

    def test_geen_waarschuwing_zonder_klemming(self):
        post_typen = [
            dict(naam="Emolumenten", n=120, k=1, N_klant=5000, waarde_laag=2_000_000.0),
        ]
        with warnings.catch_warnings(record=True) as gevangen:
            warnings.simplefilter("always", RuntimeWarning)
            bouw_strata_SSO_klant(post_typen)
        self.assertEqual(len(gevangen), 0)

    def test_volledige_blinde_vlek_wordt_geweigerd_met_naam_van_type_post(self):
        # N_klant=2 met k=0 is zo klein dat zelfs de exacte grens bij 95%
        # zekerheid al 0 fouten aangeeft (volledige blinde vlek,
        # moment_match_SSO). De hele gestratificeerde opbouw moet dan
        # stoppen met een ValueError die de naam van het type post bevat,
        # in plaats van door te gaan met een misleidend resultaat.
        post_typen = [
            dict(naam="Emolumenten", n=120, k=0, N_klant=2, waarde_laag=2_000_000.0),
        ]
        with self.assertRaises(ValueError) as ctx:
            bouw_strata_SSO_klant(post_typen)
        self.assertIn("Emolumenten", str(ctx.exception))
        self.assertIn("100%", str(ctx.exception))

    def test_volledige_blinde_vlek_stopt_ook_bij_meerdere_typen_posten(self):
        # Zelfs als andere typen posten prima gekalibreerd kunnen worden,
        # moet één type post met een volledige blinde vlek de hele
        # opbouw laten stoppen (geen gedeeltelijk/stil resultaat).
        post_typen = [
            dict(naam="Emolumenten", n=120, k=0, N_klant=2, waarde_laag=2_000_000.0),
            dict(
                naam="Inkoopfacturen", n=200, k=1, N_klant=1500, waarde_laag=5_000_000.0
            ),
        ]
        with self.assertRaises(ValueError) as ctx:
            bouw_strata_SSO_klant(post_typen)
        self.assertIn("Emolumenten", str(ctx.exception))

    def test_kalibratiemethode_naief_gebruikt_geen_moment_match(self):
        # Bij kalibratiemethode="naief" moet het resultaat overeenkomen met
        # de parallelformule, niet met moment_match_SSO — en een geval dat
        # bij momentmatching een volledige blinde vlek (ValueError) zou
        # geven, moet bij "naief" gewoon een resultaat opleveren.
        post_typen = [
            dict(naam="Emolumenten", n=120, k=0, N_klant=2, waarde_laag=2_000_000.0),
        ]
        df = bouw_strata_SSO_klant(post_typen, kalibratiemethode="naief")
        n_eff_verwacht = 120 * 2 / (120 + 2)
        self.assertAlmostEqual(df.loc[0, "k_laag"], 0.0)
        self.assertGreaterEqual(df.loc[0, "n_laag"], n_eff_verwacht)

    def test_ongeldige_kalibratiemethode_geeft_value_error(self):
        post_typen = [
            dict(naam="Emolumenten", n=120, k=1, N_klant=100, waarde_laag=2_000_000.0),
        ]
        with self.assertRaises(ValueError):
            bouw_strata_SSO_klant(post_typen, kalibratiemethode="onbekend")


if __name__ == "__main__":
    unittest.main()
