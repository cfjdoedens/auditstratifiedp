"""
auditstratified: Een Python-pakket voor het evalueren en plannen van
gestratificeerde steekproeven, conform de methodiek van de Rijksoverheid (HARo).
"""

# Importeer de hoofdfuncties direct, zodat de eindgebruiker ze makkelijk kan aanroepen.
from .eval_stratified import eval_stratified
from .plan_stratified import plan_stratified
from .utils import (
    drawsneeded,
    foutloze_posten_equivalent,
    haro_nog_nodige_zekerheid,
    max_defect_rate,
)
from .valideer_granulariteit import valideer_granulariteit

# Definieer wat er geëxporteerd wordt als iemand 'from auditstratified import *' gebruikt.
__all__ = [
    "eval_stratified",
    "plan_stratified",
    "valideer_granulariteit",
    "haro_nog_nodige_zekerheid",
    "foutloze_posten_equivalent",
    "drawsneeded",
    "max_defect_rate"
]
