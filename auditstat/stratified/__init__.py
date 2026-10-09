"""
auditstat.stratified: Een Python-pakket voor het evalueren en plannen van
gestratificeerde steekproeven, conform de methodiek van de Rijksoverheid (HARo).
"""

# Importeer de hoofdfuncties direct, zodat de eindgebruiker ze makkelijk kan aanroepen.
from .eval_stratified import eval_stratified
from .plan_stratified import plan_stratified
from .plot_kanskromme import plot_kanskromme
from .utils import foutloze_posten_equivalent, haro_nog_nodige_zekerheid

# Definieer wat er geëxporteerd wordt als iemand 'from auditstat.stratified import *' gebruikt.
__all__ = [
    "eval_stratified",
    "foutloze_posten_equivalent",
    "haro_nog_nodige_zekerheid",
    "plan_stratified",
    "plot_kanskromme",
]
