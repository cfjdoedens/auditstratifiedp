import math

import pandas as pd
import pytest
from scipy.optimize import brentq
from scipy.stats import beta, gamma

from auditstat.stratified import eval_stratified

# --- Globale testconstanten ---
DEFAULT_TOL = 5e-3
DEFAULT_ABS_TOL = 1e-4
DEFAULT_GRANULARITEIT = 200_000
DIRECT_GRANULARITEIT = 5_000  # Specifiek licht voor de trage 'direct' methode
PERMUTATIE_GRANULARITEIT = 50_000  # Voldoende voor permutatie-check


def bates_cdf(x, m):
    """Bereken de exacte cumulatieve verdelingsfunctie (CDF) van de Bates-verdeling."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0

    # Initialiseer de startwaarde voor de sommatie.
    val = 0.0

    # Bepaal de maximale iteratiegrens voor de Bates-formule.
    mx = m * x

    # Voer de reeksontwikkeling van de sommatie uit.
    for k in range(math.floor(mx) + 1):
        val += ((-1) ** k) * math.comb(m, k) * ((mx - k) ** m)

    # Deel door de faculteit van het aantal strata om de kans te voltooien.
    return val / math.factorial(m)


def bates_ppf(q, m):
    """Bereken de kwantielfunctie van de Bates-verdeling via root-finding."""
    return brentq(lambda x: bates_cdf(x, m) - q, 0, 1)


class TestAnalytischeValidatie:
    """
    Groep 1: Analytische tests.
    Test het vlaggenschip ('FFT samen') tegen de exacte wiskundige theorie.
    Dit levert het sterkste bewijs dat de wiskundige kern klopt.
    """

    def test_enkel_stratum_binomiaal(self):
        # Bepaal de vaste parameters voor het testscenario.
        n_steek = 100
        k_fout = 2
        waarde = 1_000_000.0
        zekerheid = 0.95

        # Bouw het DataFrame voor een enkel stratum zonder fouten in de hoog-populatie.
        data = pd.DataFrame({
            "naam": ["Enkel Stratum"],
            "waarde_laag": [waarde],
            "n_laag": [n_steek],
            "k_laag": [k_fout],
            "ihr": ["H"],
            "ibr": ["H"],
            "car": ["H"],
            "waarde_hoog": [0.0],
            "fout_hoog": [0.0],
            "materialiteit": [0.05],
        })

        # Bereken het resultaat via het primaire FFT-algoritme.
        res = eval_stratified(
            steekproeven=data,
            model="binomiaal",
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=DEFAULT_GRANULARITEIT,
            vergelijk=False,
        )

        # Bereken de vormparameters voor de exacte theoretische Beta-verdeling.
        a_exact = k_fout + 1
        b_exact = n_steek - k_fout + 1

        # Genereer de ankerpunten vanuit de theorie.
        exact_max = beta.ppf(zekerheid, a_exact, b_exact)
        exact_min = beta.ppf(1 - zekerheid, a_exact, b_exact)
        exact_med = beta.ppf(0.5, a_exact, b_exact)
        exact_gem = beta.mean(a_exact, b_exact)
        exact_mod = (a_exact - 1) / (a_exact + b_exact - 2)

        # Verifieer of alle uitkomsten binnen de gestelde marges van de theorie vallen.
        assert res["max_fout_convolutie"] == pytest.approx(
            exact_max, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Maximale fout wijkt af van theorie. Berekend: {res['max_fout_convolutie']:.6f}, "
            f"Theorie: {exact_max:.6f} (rel_tol={DEFAULT_TOL}, abs_tol={DEFAULT_ABS_TOL})"
        )
        assert res["min_fout_convolutie"] == pytest.approx(
            exact_min, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Minimale fout wijkt af van theorie. Berekend: {res['min_fout_convolutie']:.6f}, "
            f"Theorie: {exact_min:.6f}"
        )
        assert res["mediaan_fout_convolutie"] == pytest.approx(
            exact_med, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Mediaan fout wijkt af van theorie. Berekend: {res['mediaan_fout_convolutie']:.6f}, "
            f"Theorie: {exact_med:.6f}"
        )
        assert res["gemiddelde_fout_convolutie"] == pytest.approx(
            exact_gem, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Gemiddelde fout wijkt af van theorie. Berekend: {res['gemiddelde_fout_convolutie']:.6f}, "
            f"Theorie: {exact_gem:.6f}"
        )
        assert res["modus_fout_convolutie"] == pytest.approx(
            exact_mod, abs=DEFAULT_ABS_TOL
        ), (
            f"Modus fout wijkt af van theorie. Berekend: {res['modus_fout_convolutie']:.6f}, "
            f"Theorie: {exact_mod:.6f}"
        )

    @pytest.mark.parametrize("m", [1, 2, 3, 5, 10])
    def test_poisson_gamma_reproductie_m_strata(self, m):
        # Initialiseer de eigenschappen voor een geparametriseerd aantal strata.
        n_steek = 100
        k_fout = 2
        waarde = 1_000_000.0
        zekerheid = 0.95

        # Construeer het DataFrame met m identieke rijen.
        data = pd.DataFrame({
            "naam": [f"Stratum {i}" for i in range(m)],
            "waarde_laag": [waarde] * m,
            "n_laag": [n_steek] * m,
            "k_laag": [k_fout] * m,
            "ihr": ["H"] * m,
            "ibr": ["H"] * m,
            "car": ["H"] * m,
            "waarde_hoog": [0.0] * m,
            "fout_hoog": [0.0] * m,
            "materialiteit": [0.05] * m,
        })

        # Voer de FFT-convolutie uit voor de gecombineerde strata.
        res = eval_stratified(
            steekproeven=data,
            model="poisson",
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=DEFAULT_GRANULARITEIT,
            vergelijk=False,
        )

        # Bepaal de cumulatieve theorieparameters via de reproductie-eigenschap.
        a_exact = m * (k_fout + 1)
        schaal_exact = 1.0 / (m * n_steek)

        # Vraag de exacte Gamma-kwantielen op.
        exact_max = gamma.ppf(zekerheid, a=a_exact, scale=schaal_exact)
        exact_min = gamma.ppf(1 - zekerheid, a=a_exact, scale=schaal_exact)
        exact_med = gamma.ppf(0.5, a=a_exact, scale=schaal_exact)
        exact_gem = gamma.mean(a=a_exact, scale=schaal_exact)
        exact_mod = (a_exact - 1) * schaal_exact

        # Bevestig dat de numerieke stapeling correct aansluit bij de Gamma-theorie.
        assert res["max_fout_convolutie"] == pytest.approx(
            exact_max, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Poisson max fout ({m} strata) wijkt af. Berekend: {res['max_fout_convolutie']:.6f}, Theorie: {exact_max:.6f}"
        )
        assert res["min_fout_convolutie"] == pytest.approx(
            exact_min, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Poisson min fout ({m} strata) wijkt af. Berekend: {res['min_fout_convolutie']:.6f}, Theorie: {exact_min:.6f}"
        )
        assert res["mediaan_fout_convolutie"] == pytest.approx(
            exact_med, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Poisson mediaan fout ({m} strata) wijkt af. Berekend: {res['mediaan_fout_convolutie']:.6f}, Theorie: {exact_med:.6f}"
        )
        assert res["gemiddelde_fout_convolutie"] == pytest.approx(
            exact_gem, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Poisson gemiddelde fout ({m} strata) wijkt af. Berekend: {res['gemiddelde_fout_convolutie']:.6f}, Theorie: {exact_gem:.6f}"
        )
        assert res["modus_fout_convolutie"] == pytest.approx(
            exact_mod, abs=DEFAULT_ABS_TOL
        ), (
            f"Poisson modus fout ({m} strata) wijkt af. Berekend: {res['modus_fout_convolutie']:.6f}, Theorie: {exact_mod:.6f}"
        )

    @pytest.mark.parametrize("m", [2, 3, 4, 5])
    def test_binomiaal_uniform_bates_m_strata(self, m):
        """Test de convolutie van uniforme strata tegen de theoretische Bates-verdeling via bates_ppf."""
        waarde = 1_000_000.0
        zekerheid = 0.95

        # Definieer strata als Uniform(0,1) variabelen door n en k op 0 te zetten.
        data = pd.DataFrame({
            "naam": [f"Stratum {i}" for i in range(m)],
            "waarde_laag": [waarde] * m,
            "n_laag": [0] * m,
            "k_laag": [0] * m,
            "ihr": ["H"] * m,
            "ibr": ["H"] * m,
            "car": ["H"] * m,
            "waarde_hoog": [0.0] * m,
            "fout_hoog": [0.0] * m,
            "materialiteit": [0.05] * m,
        })

        res = eval_stratified(
            steekproeven=data,
            model="binomiaal",
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=DEFAULT_GRANULARITEIT,
            vergelijk=False,
        )

        # Hier wordt bates_ppf() aangeroepen om de exacte theoretische kwantielen te bepalen
        exact_max = bates_ppf(zekerheid, m)
        exact_min = bates_ppf(1 - zekerheid, m)

        assert res["max_fout_convolutie"] == pytest.approx(
            exact_max, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Bates max fout ({m} strata) wijkt af. Berekend: {res['max_fout_convolutie']:.6f}, Theorie: {exact_max:.6f}"
        )
        assert res["min_fout_convolutie"] == pytest.approx(
            exact_min, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Bates min fout ({m} strata) wijkt af. Berekend: {res['min_fout_convolutie']:.6f}, Theorie: {exact_min:.6f}"
        )
        assert res["mediaan_fout_convolutie"] == pytest.approx(
            0.5, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Bates mediaan fout ({m} strata) wijkt af. Berekend: {res['mediaan_fout_convolutie']:.6f}"
        )
        assert res["gemiddelde_fout_convolutie"] == pytest.approx(
            0.5, rel=DEFAULT_TOL, abs=DEFAULT_ABS_TOL
        ), (
            f"Bates gemiddelde fout ({m} strata) wijkt af. Berekend: {res['gemiddelde_fout_convolutie']:.6f}"
        )
        assert res["modus_fout_convolutie"] == pytest.approx(
            0.5, abs=DEFAULT_ABS_TOL
        ), (
            f"Bates modus fout ({m} strata) wijkt af. Berekend: {res['modus_fout_convolutie']:.6f}"
        )
