import unittest
import warnings

from scipy.stats import beta, betabinom, gamma, nbinom

from auditstat.sso.moment_match_SSO import moment_match_SSO


def _max_fout_95(n_eff, k_eff):
    return beta.ppf(0.95, k_eff + 1, n_eff - k_eff + 1)


def _max_fout_exact_binomiaal(n, k, N_klant, zekerheid=0.95):
    return betabinom.ppf(zekerheid, N_klant, k + 1, n - k + 1) / N_klant


def _max_fout_exact_poisson(n, k, N_klant, zekerheid=0.95):
    return nbinom.ppf(zekerheid, k + 1, n / (n + N_klant)) / N_klant


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

    def test_k_gelijk_aan_n_is_een_volledige_blinde_vlek(self):
        # n=20, k=20, N_klant=20 blijkt een zeer hoge SSO-foutfractie te
        # combineren met een exacte grens van precies 1 (vrijwel zekere
        # 100% fout) -- dit is het spiegelbeeld van de blinde vlek bij
        # exact_doel=0, en moet dus ook geweigerd worden.
        with self.assertRaises(ValueError) as ctx:
            moment_match_SSO(20, 20, 20, "binomiaal")
        self.assertIn("100%", str(ctx.exception))

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

    def test_geklemd_binomiaal_matcht_exacte_grens(self):
        # Bij klemming (k_eff < 0) wordt k_eff op 0 gezet en n_eff zo
        # gekozen dat de 95%-kwantiel van de resulterende Beta-verdeling
        # exact gelijk is aan de werkelijke Beta-Binomiale grens.
        n, k, N_klant = 120, 1, 100
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertEqual(k_eff, 0.0)
        self.assertAlmostEqual(_max_fout_95(n_eff, k_eff), exact, places=6)

    def test_geklemd_binomiaal_matcht_exacte_grens_bij_zeer_kleine_N_klant(self):
        n, k, N_klant = 120, 1, 5
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertEqual(k_eff, 0.0)
        self.assertAlmostEqual(_max_fout_95(n_eff, k_eff), exact, places=6)

    def test_geklemd_poisson_matcht_exacte_grens(self):
        n, k, N_klant = 120, 1, 5
        exact = _max_fout_exact_poisson(n, k, N_klant)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "poisson")
        self.assertEqual(k_eff, 0.0)
        mf = gamma.ppf(0.95, a=k_eff + 1, scale=1.0 / n_eff)
        self.assertAlmostEqual(mf, exact, places=6)
        self.assertGreater(n_eff, 0.0)

    def test_geklemd_binomiaal_is_minstens_zo_conservatief_als_exact(self):
        # Ook in het extreme randgeval (exacte grens zelf dicht bij of
        # boven de haalbare Beta-kwantiel) mag het resultaat de werkelijke
        # grens niet onderschatten.
        n, k, N_klant = 120, 5, 2
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        self.assertGreaterEqual(_max_fout_95(n_eff, k_eff) + 1e-9, min(exact, 0.95))

    def test_geklemd_bij_exacte_grens_nul_geeft_value_error(self):
        # Bij een zeer kleine N_klant met k=0 kan de exacte grens zelf
        # precies 0 zijn (zelfs bij 95% zekerheid worden 0 fouten verwacht).
        # Een Beta/Gamma-verdeling kan dat nooit exact weergeven (strikt
        # positieve drager) en zou dan ten onrechte 0 risico suggereren.
        # In plaats van toch een resultaat te geven (en voorheen een
        # ZeroDivisionError), wordt de berekening geweigerd.
        n, k, N_klant = 120, 0, 2
        self.assertEqual(_max_fout_exact_binomiaal(n, k, N_klant), 0.0)
        with self.assertRaises(ValueError) as ctx:
            moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertIn("100%", str(ctx.exception))
        self.assertIn(str(N_klant), str(ctx.exception))

    def test_geklemd_bij_exacte_grens_nul_poisson_geeft_value_error(self):
        n, k, N_klant = 120, 0, 2
        self.assertEqual(_max_fout_exact_poisson(n, k, N_klant), 0.0)
        with self.assertRaises(ValueError) as ctx:
            moment_match_SSO(n, k, N_klant, "poisson")
        self.assertIn("100%", str(ctx.exception))

    def test_omgekeerd_klemgeval_matcht_exacte_grens(self):
        # Een zeer hoge SSO-foutfractie (k dicht bij n) met een niet al te
        # kleine N_klant: de exacte grens is hier < 1, dus moet exact
        # gereproduceerd worden i.p.v. onderschat (zoals de oude, simpele
        # klem n_eff=k_eff deed).
        n, k, N_klant = 10, 10, 500
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        self.assertLess(exact, 1.0)
        with self.assertWarns(RuntimeWarning):
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertAlmostEqual(n_eff, k_eff, places=6)
        self.assertAlmostEqual(_max_fout_95(n_eff, k_eff), exact, places=6)

    def test_omgekeerd_klemgeval_volledige_blinde_vlek_geeft_value_error(self):
        # n=20, k=19, N_klant=5: zeer hoge SSO-foutfractie + kleine
        # N_klant, exacte grens is hier precies 1 (vrijwel zekere 100%
        # fout). Geen continue verdeling kan kwantiel 1 exact weergeven,
        # dus moet dit geweigerd worden i.p.v. een te optimistisch
        # resultaat (de oude klem gaf hier ten onrechte 0,98).
        n, k, N_klant = 20, 19, 5
        exact = _max_fout_exact_binomiaal(n, k, N_klant)
        self.assertEqual(exact, 1.0)
        with self.assertRaises(ValueError) as ctx:
            moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertIn("100%", str(ctx.exception))
        self.assertIn(str(N_klant), str(ctx.exception))

    def test_omgekeerd_klemgeval_komt_niet_voor_bij_poisson(self):
        # Voor poisson geldt n_eff >= k_eff altijd (gegeven k <= n), dus
        # dit scenario (hoge foutfractie, kleine N_klant) moet gewoon de
        # normale (milde) klemmelding geven, geen 100%-weigering.
        n, k, N_klant = 20, 20, 5
        with warnings.catch_warnings(record=True) as gevangen:
            warnings.simplefilter("always", RuntimeWarning)
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "poisson")
        self.assertGreaterEqual(n_eff, k_eff)
        if gevangen:
            self.assertNotIn("100%", str(gevangen[0].message))

    def test_gewoon_klemgeval_geeft_niet_de_100_procent_weigering(self):
        # Bij klemming waarbij de exacte grens zelf wél positief is (en dus
        # exact gereproduceerd wordt), moet de mildere standaardmelding
        # verschijnen, niet een geweigerde berekening.
        n, k, N_klant = 120, 1, 100
        self.assertGreater(_max_fout_exact_binomiaal(n, k, N_klant), 0.0)
        with warnings.catch_warnings(record=True) as gevangen:
            warnings.simplefilter("always", RuntimeWarning)
            n_eff, k_eff = moment_match_SSO(n, k, N_klant, "binomiaal")
        self.assertEqual(len(gevangen), 1)
        self.assertNotIn("100%", str(gevangen[0].message))
        self.assertGreaterEqual(n_eff, k_eff)
        self.assertGreaterEqual(k_eff, 0.0)


if __name__ == "__main__":
    unittest.main()
