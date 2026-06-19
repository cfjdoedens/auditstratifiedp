import pytest
import math
from auditstratified.utils import (
    haro_nog_nodige_zekerheid, 
    foutloze_posten_equivalent, 
    drawsneeded, 
    max_defect_rate
)

def test_haro_nog_nodige_zekerheid_alle_combinaties():
    """Test alle 27 risicocombinaties van het HARo-model op basis van exacte afrondingen."""
    # Test alle theoretisch mogelijke HARo-combinaties van IHR, IBR en CAR.
    assert round(haro_nog_nodige_zekerheid("H", "H", "H"), 2) == 0.95
    assert round(haro_nog_nodige_zekerheid("M", "H", "H"), 2) == 0.92
    assert round(haro_nog_nodige_zekerheid("H", "H", "M"), 2) == 0.90
    assert round(haro_nog_nodige_zekerheid("H", "M", "H"), 2) == 0.90
    assert round(haro_nog_nodige_zekerheid("H", "L", "H"), 2) == 0.85
    assert round(haro_nog_nodige_zekerheid("M", "M", "H"), 2) == 0.85
    assert round(haro_nog_nodige_zekerheid("M", "H", "M"), 2) == 0.84
    assert round(haro_nog_nodige_zekerheid("H", "M", "M"), 2) == 0.81
    assert round(haro_nog_nodige_zekerheid("H", "H", "L"), 2) == 0.80
    assert round(haro_nog_nodige_zekerheid("L", "H", "H"), 2) == 0.88
    assert round(haro_nog_nodige_zekerheid("M", "L", "H"), 2) == 0.77
    assert round(haro_nog_nodige_zekerheid("L", "M", "H"), 2) == 0.76
    assert round(haro_nog_nodige_zekerheid("L", "H", "M"), 2) == 0.75
    assert round(haro_nog_nodige_zekerheid("H", "L", "M"), 2) == 0.71
    assert round(haro_nog_nodige_zekerheid("M", "M", "M"), 2) == 0.69
    assert round(haro_nog_nodige_zekerheid("M", "H", "L"), 2) == 0.68
    assert round(haro_nog_nodige_zekerheid("L", "L", "H"), 2) == 0.63
    assert round(haro_nog_nodige_zekerheid("H", "M", "L"), 2) == 0.62
    assert round(haro_nog_nodige_zekerheid("M", "L", "M"), 2) == 0.53
    assert round(haro_nog_nodige_zekerheid("L", "M", "M"), 2) == 0.52
    assert round(haro_nog_nodige_zekerheid("L", "H", "L"), 2) == 0.50
    assert round(haro_nog_nodige_zekerheid("H", "L", "L"), 2) == 0.41
    assert round(haro_nog_nodige_zekerheid("M", "M", "L"), 2) == 0.39
    assert round(haro_nog_nodige_zekerheid("L", "L", "M"), 2) == 0.26
    assert round(haro_nog_nodige_zekerheid("M", "L", "L"), 2) == 0.12
    assert round(haro_nog_nodige_zekerheid("L", "M", "L"), 2) == 0.09
    assert round(haro_nog_nodige_zekerheid("L", "L", "L"), 2) == 0.05

def test_haro_foutieve_invoer():
    """Test of ongeldige invoer voor risico's netjes wordt afgevangen."""
    # Controleer of een niet-bestaande risicoletter een ValueError oplevert.
    with pytest.raises(ValueError):
        haro_nog_nodige_zekerheid("X", "H", "H")

def test_drawsneeded_binomiaal_basis():
    """Test de berekening van het aantal benodigde steken via de binomiale verdeling."""
    # Bereken het benodigde aantal steken voor nul verwachte fouten bij vijf procent materialiteit.
    n_steken = drawsneeded(posited_defect_rate=0.0, allowed_defect_rate=0.05, cert=0.95, distribution="binomial")
    
    # De exacte wiskunde van de gebruikte béta-parameters (n - k + 1) dicteert dat 58 de ondergrens is.
    assert n_steken == 58

def test_drawsneeded_vectorisatie():
    """Test of de functie iterables als invoer kan verwerken via dictionaries."""
    # Voer een lijst met twee verschillende materialiteiten in.
    resultaat = drawsneeded(posited_defect_rate=0.0, allowed_defect_rate=[0.05, 0.10], cert=0.95, distribution="binomial")
    
    # Controleer of de dictionary de correcte modelmatige antwoorden voor beide sleutels bevat.
    assert resultaat[0.05] == 58
    assert resultaat[0.10] == 28

def test_max_defect_rate_binomiaal():
    """Test de terugrekening van de maximale foutfractie bij een gegeven steekproef."""
    # Test met 58 steken, wat volgens het model de grens is om onder de vijf procent te duiken.
    q = max_defect_rate(n=58, posited_defect_rate=0.0, cert=0.95, distribution="binomial")
    
    # Dit levert een specifieke fractiewaarde (0.04947) op die inderdaad net kleiner of gelijk is aan 0.05.
    assert math.isclose(q, 0.04947, abs_tol=1e-4)
    assert q <= 0.05

def test_foutloze_posten_equivalent():
    """Test of het foutloze posten equivalent correct wordt afgeleid van de benodigde zekerheid."""
    # Bereken het posten equivalent voor een middelmatig risicoprofiel.
    fpe_mmm = foutloze_posten_equivalent("M", "M", "M", materialiteit=0.01)
    
    # Valideer dat de functie een numerieke waarde teruggeeft.
    assert isinstance(fpe_mmm, (int, float))
    
    # Valideer dat het equivalent een positief getal of nul is.
    assert fpe_mmm >= 0

    """Test of het equivalente aantal foutloze posten exact overeenkomt met de R-berekeningen."""
    # Test maximale risico's met 1 procent materialiteit.
    assert round(foutloze_posten_equivalent("H", "H", "H", materialiteit=0.01)) == 0
    
    # Test hoog risico behalve het cijferanalyserisico met 1 procent materialiteit.
    assert round(foutloze_posten_equivalent("H", "H", "L", materialiteit=0.01)) == 138
    
    # Test hoog risico behalve het cijferanalyserisico met 2 procent materialiteit.
    assert round(foutloze_posten_equivalent("H", "H", "L", materialiteit=0.02)) == 69
    
    # Test minimale risico's met 1 procent materialiteit.
    assert round(foutloze_posten_equivalent("L", "L", "L", materialiteit=0.01)) == 293
    
    # Test minimale risico's met een grotere materialiteit (2 procent) leidt tot veel minder equivalente foutloze steken.
    assert round(foutloze_posten_equivalent("L", "L", "L", materialiteit=0.02)) == 146

def test_haro_nog_nodige_zekerheid_standaard():
    """Test de standaard HARo berekeningen op uiterste waarden."""
    # Test de maximale risico-inschatting waarbij alle factoren hoog zijn.
    nnz_hhh = haro_nog_nodige_zekerheid("H", "H", "H")
    assert math.isclose(nnz_hhh, 0.95, rel_tol=1e-5)
    
    # Test de minimale risico-inschatting inclusief de 0.05 correctie.
    nnz_lll = haro_nog_nodige_zekerheid("L", "L", "L")
    assert math.isclose(nnz_lll, 0.05, rel_tol=1e-5)

def test_haro_foutieve_invoer():
    """Test of ongeldige invoer voor risico's netjes wordt afgevangen."""
    # Controleer of een niet-bestaande risicoletter een ValueError oplevert.
    with pytest.raises(ValueError):
        haro_nog_nodige_zekerheid("X", "H", "H")

def test_drawsneeded_binomiaal_basis():
    """Test de berekening van het aantal benodigde steken via de binomiale verdeling."""
    # Bereken het benodigde aantal steken voor nul verwachte fouten bij vijf procent materialiteit.
    n_steken = drawsneeded(posited_defect_rate=0.0, allowed_defect_rate=0.05, cert=0.95, distribution="binomial")
    
    # De exacte wiskunde van de gebruikte béta-parameters (n - k + 1) dicteert dat 58 de ondergrens is.
    assert n_steken == 58

def test_drawsneeded_vectorisatie():
    """Test of de functie iterables als invoer kan verwerken via dictionaries."""
    # Voer een lijst met twee verschillende materialiteiten in.
    resultaat = drawsneeded(posited_defect_rate=0.0, allowed_defect_rate=[0.05, 0.10], cert=0.95, distribution="binomial")
    
    # Controleer of de dictionary de correcte modelmatige antwoorden voor beide sleutels bevat.
    assert resultaat[0.05] == 58
    assert resultaat[0.10] == 28

def test_max_defect_rate_binomiaal():
    """Test de terugrekening van de maximale foutfractie bij een gegeven steekproef."""
    # Test met 58 steken, wat volgens het model de grens is om onder de vijf procent te duiken.
    q = max_defect_rate(n=58, posited_defect_rate=0.0, cert=0.95, distribution="binomial")
    
    # Dit levert een specifieke fractiewaarde (0.04947) op die inderdaad net kleiner of gelijk is aan 0.05.
    assert math.isclose(q, 0.04947, abs_tol=1e-4)
    assert q <= 0.05

def test_foutloze_posten_equivalent():
    """Test of het foutloze posten equivalent correct wordt afgeleid van de benodigde zekerheid."""
    # Bereken het posten equivalent voor een middelmatig risicoprofiel.
    fpe_mmm = foutloze_posten_equivalent("M", "M", "M", materialiteit=0.01)
    
    # Valideer dat de functie een numerieke waarde teruggeeft.
    assert isinstance(fpe_mmm, (int, float))
    
    # Valideer dat het equivalent een positief getal of nul is.
    assert fpe_mmm >= 0
