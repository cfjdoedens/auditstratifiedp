import sys
import math
import numpy as np
import pandas as pd
from scipy.stats import beta, gamma

def haro_nog_nodige_zekerheid(ihr: str = "H", ibr: str = "H", car: str = "H") -> float:
    """
    Bereken de nog benodigde zekerheid te verkrijgen uit detailcontrole.
    
    In het Handboek Auditing Rijksoverheid (HARo), paragraaf B7.3.4 staat
    beschreven welke zekerheid de auditor moet bereiken met detailcontroles, 
    gegeven het inherente risico (ihr), interne beheersingsrisico (ibr) en 
    cijferanalyserisico (car).
    """
    # Controleer invoerparameters.
    geldige_risicos = ["H", "M", "L"]
    if ihr not in geldige_risicos or ibr not in geldige_risicos or car not in geldige_risicos:
        raise ValueError("Risico-inschattingen moeten 'H', 'M' of 'L' zijn.")

    # Zie HAR0 7.3.4 voor de vertaling van risico's naar getallen.
    ihr_map = {"H": 1.0, "M": 0.63, "L": 0.40}
    ibr_map = {"H": 1.0, "M": 0.52, "L": 0.34}
    car_map = {"H": 1.0, "M": 0.50, "L": 0.25}
    
    ihr_als_getal = ihr_map[ihr]
    ibr_als_getal = ibr_map[ibr]
    car_als_getal = car_map[car]

    # Bereken het detectierisico en de nog nodige zekerheid.
    auditrisico = 0.05
    detectierisico = auditrisico / (ihr_als_getal * ibr_als_getal * car_als_getal)
    nog_nodige_zekerheid = max(0.0, 1.0 - detectierisico)
    
    # Corrigeer voor de extreem lage risico-combinaties volgens het HARo-model.
    if nog_nodige_zekerheid <= 0.07:
        nog_nodige_zekerheid += 0.05
        
    return nog_nodige_zekerheid

def foutloze_posten_equivalent(ihr: str = "H", ibr: str = "H", car: str = "H", materialiteit: float = 0.01) -> float:
    """
    Geef equivalent in getrokken foutloze posten voor verlaagde risicoschattingen.
    
    Volgens het HARo is de benodigde zekerheid bij een gegevensgerichte 
    controle 95%, namelijk 100% minus het accountantsrisico (5%).
    Ook volgens het HARo definiëren ihr, ibr en car samen de nog benodigde 
    zekerheid voor een gegevensgerichte controle.
    Bereken het aantal foutloze posten dat daarmee overeenkomt, 
    rekening houdend met de materialiteit.
    """
    # Controleer de invoerparameters strak op de toegestane risicocategorieën.
    geldige_risicos = ["H", "M", "L"]
    if ihr not in geldige_risicos or ibr not in geldige_risicos or car not in geldige_risicos:
        raise ValueError("Risico-inschattingen moeten 'H', 'M' of 'L' zijn.")

    # Bepaal de referentiewaarde en de specifiek benodigde zekerheid.
    hoogste_zekerheid = 0.95
    benodigde_zekerheid = haro_nog_nodige_zekerheid(ihr, ibr, car)
    
    # Werp een fout op als de benodigde zekerheid onlogisch hoog is.
    if benodigde_zekerheid > hoogste_zekerheid:
        raise ValueError("Benodigde zekerheid mag niet groter zijn dan 0.95.")

    # Bereken het verschil in benodigde posten.
    posten_alles_hoog = drawsneeded(0.0, materialiteit, cert=hoogste_zekerheid)
    posten_niet_alles_hoog = drawsneeded(0.0, materialiteit, cert=benodigde_zekerheid)
    
    return posten_alles_hoog - posten_niet_alles_hoog

def _is_iterable_num(val) -> bool:
    """Controleer of een object een lijst of array is, maar uitsluitend voor getallen (geen strings)."""
    return hasattr(val, '__iter__') and not isinstance(val, str)

def drawsneeded(posited_defect_rate=0.0, allowed_defect_rate=0.01, cert=0.95, distribution="binomial"):
    """
    Bereken het aantal benodigde steken om de maximale foutfractie met voldoende zekerheid vast te stellen.
    
    Deze functie schat het aantal benodigde steken op basis van een vlakke prior.
    Het maakt gebruik van de binomiale verdeling of de Poissonverdeling.
    """
    # Handel de recursie af voor invoer met meerdere waarden (vectorisatie).
    if _is_iterable_num(posited_defect_rate):
        return {p: drawsneeded(p, allowed_defect_rate, cert, distribution) for p in posited_defect_rate}
        
    if _is_iterable_num(allowed_defect_rate):
        return {a: drawsneeded(posited_defect_rate, a, cert, distribution) for a in allowed_defect_rate}
        
    if _is_iterable_num(cert):
        return {c: drawsneeded(posited_defect_rate, allowed_defect_rate, c, distribution) for c in cert}
        
    if _is_iterable_num(distribution):
        return {d: drawsneeded(posited_defect_rate, allowed_defect_rate, cert, d) for d in distribution}

    # Voer de daadwerkelijke berekening uit voor enkelvoudige numerieke waarden (base case).
    # Controleer of de parameters wiskundig logisch en toegestaan zijn.
    if not (0 <= posited_defect_rate < 1):
        raise ValueError("posited_defect_rate moet in [0, 1) liggen.")
    if not (0 < allowed_defect_rate < 1):
        raise ValueError("allowed_defect_rate moet in (0, 1) liggen.")
    if posited_defect_rate >= allowed_defect_rate:
        raise ValueError("posited_defect_rate moet kleiner zijn dan allowed_defect_rate.")
    if not (0 <= cert <= 1):
        raise ValueError("cert moet in [0, 1] liggen.")
    if distribution not in ["binomial", "Poisson", "Poisson_interpolated"]:
        raise ValueError("Onbekende distributie gekozen.")

    # Vang wiskundige randgevallen direct af.
    if cert == 0:
        return 0
    if cert == 1:
        return float('inf')

    # Gebruik de analytische benadering als daarom gevraagd wordt.
    if distribution == "Poisson_interpolated":
        return calc_n_inverse(allowed_defect_rate, posited_defect_rate, cert)

    # Gebruik een binaire zoektocht om de kleinst mogelijke n te vinden.
    max_n = 100000000
    begin_range = 1
    end_range = max_n
    
    # Controleer of het antwoord zich überhaupt in onze extreme bandbreedte bevindt.
    if max_defect_rate(end_range, posited_defect_rate, cert, distribution) > allowed_defect_rate:
        return float('inf')

    # Blijf het interval halveren zolang de ondergrens en bovengrens niet aan elkaar gelijk zijn.
    while True:
        if begin_range == end_range:
            return begin_range
        elif begin_range + 1 == end_range:
            # We hebben geen echt midden meer, test direct de ondergrens.
            if max_defect_rate(begin_range, posited_defect_rate, cert, distribution) <= allowed_defect_rate:
                return begin_range
            else:
                return end_range
        else:
            # Bepaal het nieuwe midden en evalueer of we in de onderste of bovenste helft verder zoeken.
            middle = (end_range - begin_range) // 2 + begin_range
            if max_defect_rate(middle, posited_defect_rate, cert, distribution) <= allowed_defect_rate:
                end_range = middle
            else:
                begin_range = middle

def get_R(k: int, cert: float = 0.95) -> float:
    """Haal de R-waarde op voor een gegeven k en zekerheidsniveau via de inverse Gamma-verdeling."""
    return gamma.ppf(cert, a=k + 1, scale=1)

def calc_n_inverse(allowed_defect_rate: float, posited_defect_rate: float, cert: float) -> float:
    """Benader het benodigde aantal posten analytisch via de formule van Paul van Batenburg."""
    ratio_target = posited_defect_rate / allowed_defect_rate
    found = False
    k_limit = 1000
    k1 = None
    k2 = None

    # Zoek de twee k-waarden waartussen onze doelratio zich bevindt.
    for k in range(k_limit + 1):
        R_k = get_R(k, cert)
        ratio_k = k / R_k

        R_k_next = get_R(k + 1, cert)
        ratio_k_next = (k + 1) / R_k_next

        if ratio_k <= ratio_target <= ratio_k_next:
            k1 = k
            k2 = k + 1
            found = True
            break

    # Werp een fout op als de waarden te dicht op elkaar liggen voor interpolatie.
    if not found:
        raise ValueError("k niet binnen 0:1000 gevonden; posited_defect_rate ligt te dicht bij allowed_defect_rate.")

    R_k1 = get_R(k1, cert)
    R_k2 = get_R(k2, cert)

    # Pas de teller van de formule toe, waarbij we uitgaan van M = 1.
    numerator = (k2 * R_k1 - k1 * R_k2)

    # Pas de noemer van de formule toe, gebruikmakend van het feit dat k2 - k1 altijd 1 is.
    denominator = allowed_defect_rate - posited_defect_rate * (R_k2 - R_k1)

    return numerator / denominator

def max_defect_rate(n: int, posited_defect_rate: float, cert: float = 0.95, distribution: str = "binomial") -> float:
    """Bereken de maximale foutfractie bij een specifieke steekproefomvang en zekerheid."""
    # Controleer de randvoorwaarden van de parameters.
    if not (n > 0):
        raise ValueError("n moet groter zijn dan 0.")
    if not (0 <= posited_defect_rate <= 1):
        raise ValueError("posited_defect_rate moet tussen 0 en 1 liggen.")
    if not (0 <= cert <= 1):
        raise ValueError("cert moet tussen 0 en 1 liggen.")
    if distribution not in ["binomial", "Poisson"]:
        raise ValueError("Onbekende distributie.")

    k = n * posited_defect_rate

    # Bereken de kwantielwaarde via de gespecificeerde verdeling.
    if distribution == "binomial":
        q = beta.ppf(cert, a=k + 1, b=n - k + 1)
        
        # Voer een robuustheidscontrole uit via de inverse functie.
        controle_cert = beta.cdf(q, a=k + 1, b=n - k + 1)
        if not math.isclose(cert, controle_cert, rel_tol=1e-5):
            raise ArithmeticError("Inversie van de bètaverdeling (pbeta test) gaf een onverwacht resultaat.")
    else:
        risk_factor = gamma.ppf(cert, a=k + 1, scale=1)
        q = risk_factor / n

    return q
