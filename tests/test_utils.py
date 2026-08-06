import math

import pytest

from auditstratified.utils import (  # pyrefly: ignore[missing-import]
    drawsneeded,
    foutloze_posten_equivalent,
    haro_nog_nodige_zekerheid,
    max_defect_rate,
)


# Test alle theoretisch mogelijke HARo-combinaties van IHR, IBR en CAR op basis van exacte afrondingen.
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
def test_haro_nog_nodige_zekerheid_alle_combinaties(ihr, ibr, car, verwachte_zekerheid):
    """Test de 27 risicocombinaties van het HARo-model."""
    # Vergelijk de berekende zekerheid met de theoretische verwachting.
    berekend = haro_nog_nodige_zekerheid(ihr, ibr, car)
    assert math.isclose(berekend, verwachte_zekerheid, abs_tol=1e-2)


# Controleer of ongeldige invoer voor risico's netjes wordt afgevangen met een ValueError.
@pytest.mark.parametrize(
    "ihr, ibr, car",
    [
        ("X", "H", "H"),
        ("H", "Y", "H"),
        ("H", "H", "Z"),
    ],
)
def test_haro_foutieve_invoer(ihr, ibr, car):
    """Test of ongeldige invoer netjes wordt afgevangen."""
    # Verwacht een foutmelding zodra een niet-bestaande risicoletter wordt meegegeven.
    with pytest.raises(ValueError):
        haro_nog_nodige_zekerheid(ihr, ibr, car)


def test_drawsneeded_binomiaal_basis():
    """Test de berekening van het aantal benodigde steken via de binomiale verdeling."""
    # Bereken het benodigde aantal steken voor nul verwachte fouten bij vijf procent materialiteit.
    n_steken = drawsneeded(
        posited_defect_rate=0.0,
        allowed_defect_rate=0.05,
        cert=0.95,
        distribution="binomial",
    )
    # Controleer de theoretische ondergrens.
    assert n_steken == 58


def test_drawsneeded_vectorisatie():
    """Test of de functie iterables als invoer kan verwerken via dictionaries."""
    # Voer een lijst met twee verschillende materialiteiten in.
    resultaat = drawsneeded(
        posited_defect_rate=0.0,
        allowed_defect_rate=[0.05, 0.10],
        cert=0.95,
        distribution="binomial",
    )
    # Controleer of de dictionary de correcte modelmatige antwoorden voor beide sleutels bevat.
    assert resultaat[0.05] == 58
    assert resultaat[0.10] == 28


def test_max_defect_rate_binomiaal():
    """Test de terugrekening van de maximale foutfractie bij een gegeven steekproef."""
    # Test de berekening met de bekende grens van 58 steken.
    q = max_defect_rate(
        n=58, posited_defect_rate=0.0, cert=0.95, distribution="binomial"
    )
    # Controleer of de specifieke fractiewaarde inderdaad kleiner of gelijk is aan 0.05.
    assert math.isclose(q, 0.04947, abs_tol=1e-4)
    assert q <= 0.05


def test_foutloze_posten_equivalent():
    """Test of het foutloze posten equivalent correct wordt afgeleid van de benodigde zekerheid."""
    # Bereken het posten equivalent voor een middelmatig risicoprofiel.
    fpe_mmm = foutloze_posten_equivalent("M", "M", "M", materialiteit=0.01)
    # Valideer dat de functie een positieve numerieke waarde teruggeeft.
    assert isinstance(fpe_mmm, (int, float))
    assert fpe_mmm >= 0


# Test of het equivalente aantal foutloze posten exact overeenkomt met de theorie.
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
    ihr, ibr, car, materialiteit, verwacht_fpe
):
    """Test of het foutloze posten equivalent exact klopt met diverse scenario's."""
    # Bereken het equivalente aantal foutloze posten op basis van de testvariabelen.
    berekend = foutloze_posten_equivalent(ihr, ibr, car, materialiteit=materialiteit)
    # Valideer de afgeronde uitkomst met de referentiewaarde.
    assert round(berekend) == verwacht_fpe
