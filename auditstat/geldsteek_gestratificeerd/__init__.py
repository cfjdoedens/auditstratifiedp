"""
auditstat.geldsteek_gestratificeerd: Een Python-pakket voor het evalueren en plannen van
gestratificeerde steekproeven, conform de methodiek van de Rijksoverheid (HARo).
"""

# Importeer de hoofdfuncties direct, zodat de eindgebruiker ze makkelijk kan aanroepen.
from .evalueer_geldsteek_gestratificeerd import evalueer_geldsteek_gestratificeerd
from .plan_geldsteek_gestratificeerd import plan_geldsteek_gestratificeerd
from .plot_kanskromme import plot_kanskromme
from .utils import foutloze_posten_equivalent, haro_nog_nodige_zekerheid

# Definieer wat er geëxporteerd wordt als iemand 'from auditstat.geldsteek_gestratificeerd import *' gebruikt.
__all__ = [
    "evalueer_geldsteek_gestratificeerd",
    "foutloze_posten_equivalent",
    "haro_nog_nodige_zekerheid",
    "plan_geldsteek_gestratificeerd",
    "plot_kanskromme",
]
