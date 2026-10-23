"""Gedeelde hulpfuncties voor Nederlandse getalnotatie in plots.

Nederlandse notatie gebruikt een komma als decimaalteken en een punt als
duizendtal-scheidingsteken (bijv. "1.234,56"), het omgekeerde van de
Engelse/Amerikaanse notatie die matplotlib standaard gebruikt voor
astabels, legenda's en titels.
"""

import matplotlib.pyplot as plt


def nl_getal(x, decimalen=2):
    """Formatteert een getal met Nederlandse notatie (vast aantal
    decimalen, komma als decimaalteken, punt als duizendtal-
    scheidingsteken)."""
    fmt = f"{x:,.{decimalen}f}"
    return fmt.replace(",", "X").replace(".", ",").replace("X", ".")


def nl_getal_variabel(x):
    """Formatteert een getal met een door Python zelf gekozen, compact
    aantal decimalen (zoals %g), maar met komma als decimaalteken.
    Geschikt voor labels waar de precisie per waarde sterk uiteenloopt
    (bijv. 0,5 / 0,05 / 0,005)."""
    return f"{x:g}".replace(".", ",")


def nl_tick_formatter(decimalen=2):
    """Geeft een matplotlib-tickformatter terug die getallen weergeeft
    met Nederlandse notatie (komma als decimaalteken, punt als
    duizendtal-scheidingsteken)."""
    return plt.FuncFormatter(lambda x, _pos=None: nl_getal(x, decimalen))
