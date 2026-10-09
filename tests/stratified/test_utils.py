import pytest

from auditstat.stratified.utils import (  # pyrefly: ignore[missing-import]
    drawsneeded,
    foutloze_posten_equivalent,
    get_R,
    haro_nog_nodige_zekerheid,
    max_defect_rate,
)


class TestHarModelEnZekerheid:
    """
    Groep tests voor het HARo-risicomodel en de bijbehorende zekerheidsberekeningen.
    """

    @pytest.mark.parametrize(
        "ihr, ibr, car, verwachte_zekerheid",
        [
            ("H", "H", "H", 0.95),
            ("M", "H", "H", 0.92),
            ("H", "H", "M", 0.90),
            ("H", "M", "H", 0.90),
            ("L", "H", "H", 0.88),
            ("H", "L", "H", 0.85),
            ("M", "M", "H", 0.85),
            ("M", "H", "M", 0.84),
            ("H", "M", "M", 0.81),
            ("H", "H", "L", 0.80),
            ("M", "L", "H", 0.77),
            ("L", "M", "H", 0.76),
            ("L", "H", "M", 0.75),
            ("H", "L", "M", 0.71),
            ("M", "M", "M", 0.69),
            ("M", "H", "L", 0.68),
            ("L", "L", "H", 0.63),
            ("H", "M", "L", 0.62),
            ("M", "L", "M", 0.53),
            ("L", "M", "M", 0.52),
            ("L", "H", "L", 0.50),
            ("H", "L", "L", 0.41),
            ("M", "M", "L", 0.39),
            ("L", "L", "M", 0.26),
            ("M", "L", "L", 0.12),
            ("L", "M", "L", 0.09),
            ("L", "L", "L", 0.05),
        ],
    )
    def test_haro_nog_nodige_zekerheid_alle_combinaties(
        self, ihr, ibr, car, verwachte_zekerheid
    ):
        """Test alle 27 theoretisch mogelijke HARo-risicocombinaties."""
        berekend = haro_nog_nodige_zekerheid(ihr, ibr, car)
        assert berekend == pytest.approx(verwachte_zekerheid, abs=1e-2), (
            f"HARo zekerheid voor combinatie ({ihr}, {ibr}, {car}) wijkt af. "
            f"Berekend: {berekend:.4f}, Verwacht: {verwachte_zekerheid:.4f}"
        )

    @pytest.mark.parametrize(
        "ihr, ibr, car",
        [
            ("X", "H", "H"),
            ("H", "Y", "H"),
            ("H", "H", "Z"),
        ],
    )
    def test_haro_foutieve_invoer(self, ihr, ibr, car):
        """Test of ongeldige risico-labels netjes worden afgevangen."""
        with pytest.raises(ValueError, match="Risico-inschattingen moeten"):
            haro_nog_nodige_zekerheid(ihr, ibr, car)

    def test_haro_zekerheid_standaard(self):
        """Standaard risico (H, H, H) levert de maximale zekerheid van 0.95 op."""
        res = haro_nog_nodige_zekerheid("H", "H", "H")
        assert res == pytest.approx(0.95, abs=1e-4), (
            f"Standaard HARo zekerheid wijkt af. Berekend: {res:.5f}, Verwacht: 0.95"
        )


class TestDrawsNeeded:
    """
    Tests voor de steekproefomvang-bepaling (drawsneeded).
    """

    def test_drawsneeded_binomiaal_basis(self):
        """Test de berekening van het aantal benodigde steken via de binomiale verdeling."""
        n_steken = drawsneeded(
            posited_defect_rate=0.0,
            allowed_defect_rate=0.05,
            cert=0.95,
            distribution="binomial",
        )
        assert n_steken == 58

    def test_drawsneeded_vectorisatie(self):
        """Test of de functie iterables als invoer correct verwerkt via dictionaries."""
        resultaat = drawsneeded(
            posited_defect_rate=0.0,
            allowed_defect_rate=[0.05, 0.10],
            cert=0.95,
            distribution="binomial",
        )
        assert resultaat[0.05] == 58
        assert resultaat[0.10] == 28

    def test_drawsneeded_randgevallen_zekerheid(self):
        """Zekerheid 0 levert 0 steken op; zekerheid 1 levert oneindig op."""
        assert drawsneeded(cert=0) == 0
        assert drawsneeded(cert=1) == float("inf")

    def test_drawsneeded_ongeldige_parameters(self):
        """Ongeldige foutfracties of omgekeerde grenzen moeten falen."""
        with pytest.raises(ValueError, match="posited_defect_rate moet in"):
            drawsneeded(posited_defect_rate=-0.1)
        with pytest.raises(ValueError, match="kleiner zijn dan"):
            drawsneeded(posited_defect_rate=0.02, allowed_defect_rate=0.01)


class TestStatistischeHulpfuncties:
    """
    Tests voor get_R, calc_n_inverse, max_defect_rate en foutloze posten equivalent.
    """

    def test_get_r_waarde(self):
        """Get_R berekent correct de risicofactor via de inverse Gamma-verdeling."""
        r = get_R(k=2, cert=0.95)
        assert r > 0
        assert r == pytest.approx(6.29579, rel=1e-3), (
            f"Risicofactor R wijkt af. Berekend: {r:.5f}, Verwacht: 6.29579 (rel_tol=1e-3)"
        )

    def test_max_defect_rate_binomiaal(self):
        """Test de terugrekening van de maximale foutfractie via de binomiale verdeling."""
        q = max_defect_rate(
            n=58, posited_defect_rate=0.0, cert=0.95, distribution="binomial"
        )
        assert q == pytest.approx(0.04947, abs=1e-4), (
            f"Maximale defect rate (binomiaal) wijkt af. Berekend: {q:.5f}, Verwacht: 0.04947"
        )
        assert q <= 0.05

    def test_max_defect_rate_poisson(self):
        """Maximale foutfractie via de Poisson-verdeling."""
        q = max_defect_rate(
            n=100, posited_defect_rate=0.01, cert=0.95, distribution="Poisson"
        )
        assert 0.0 < q < 1.0

    def test_max_defect_rate_ongeldige_n(self):
        """Een steekproefomvang n <= 0 moet een ValueError opleveren."""
        with pytest.raises(ValueError, match="n moet groter zijn dan 0"):
            max_defect_rate(n=0, posited_defect_rate=0.0)

    def test_foutloze_posten_equivalent(self):
        """Test of het foutloze posten equivalent correct wordt afgeleid van de benodigde zekerheid."""
        fpe_mmm = foutloze_posten_equivalent("M", "M", "M", materialiteit=0.01)
        assert isinstance(fpe_mmm, (int, float))
        assert fpe_mmm >= 0

    @pytest.mark.parametrize(
        "ihr, ibr, car, materialiteit, verwacht_fpe",
        [
            ("H", "H", "H", 0.01, 0),
            ("H", "H", "L", 0.01, 138),
            ("H", "H", "L", 0.02, 69),
            ("L", "L", "L", 0.01, 293),
            ("L", "L", "L", 0.02, 146),
        ],
    )
    def test_foutloze_posten_equivalent_exacte_waarden(
        self, ihr, ibr, car, materialiteit, verwacht_fpe
    ):
        """Test of het foutloze posten equivalent exact klopt met diverse scenario's."""
        berekend = foutloze_posten_equivalent(
            ihr, ibr, car, materialiteit=materialiteit
        )
        assert round(berekend) == verwacht_fpe, (
            f"Foutloze posten equivalent voor ({ihr}, {ibr}, {car}, materialiteit={materialiteit}) wijkt af. "
            f"Berekend: {berekend:.2f} (afgerond: {round(berekend)}), Verwacht: {verwacht_fpe}"
        )
