"""
Validatiehulpfunctie die controleert of de granulariteit hoog genoeg is
om bij de gegeven (of verwachte) steekproefgrootte nog een meetbare
foutreductie te garanderen.

Zie §5.2 van VERANTWOORDING.md voor de theoretische achtergrond en voorbeelden.
"""

__all__ = ["valideer_granulariteit"]

import math
import warnings

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist


def valideer_granulariteit(
    steekproeven: pd.DataFrame,
    granulariteit: int,
    zekerheid: float = 0.95,
    n_kolom: str | None = None,
) -> pd.DataFrame:
    """Controleer of de granulariteit volstaat voor de (verwachte) steekproefgrootte.

    Voor elk stratum wordt bepaald wat de maximale steekproefgrootte is waarbij
    de FFT nog een meetbare foutreductie kan detecteren. Wanneer een n_kolom is
    opgegeven, wordt de huidige steekproefgrootte daarmee vergeleken en volgt
    een waarschuwing bij overschrijding.

    De berekening is gebaseerd op de exacte Beta-verdeling (zie §5.2 van
    VERANTWOORDING.md) en maakt geen gebruik van benaderingen.
    Als ``verwachte_foutfractie`` aanwezig is in steekproeven, wordt die
    meegenomen; anders wordt d_i = 0 aangenomen.

    Parameters
    ----------
    steekproeven : pd.DataFrame
        DataFrame met minimaal de kolommen ``naam`` en ``waarde_laag``.
        Als ook ``waarde_hoog``, ``fout_hoog`` en ``verwachte_foutfractie``
        aanwezig zijn, worden die meegenomen.
    granulariteit : int
        Het aantal roosterpunten dat in de FFT-convolutie wordt gebruikt.
    zekerheid : float, default 0.95
        De vereiste statistische zekerheid (bijv. 0.95 voor 95%).
    n_kolom : str or None, default None
        Naam van de kolom met de huidige of verwachte steekproefgrootte
        (bijv. ``"n_laag"``). Als None, worden alleen
        de grenzen gerapporteerd zonder vergelijking.

    Returns
    -------
    pd.DataFrame
        Een overzicht per stratum met de kolommen:

        - ``naam``
        - ``gewicht``   : relatief gewicht wᵢ = Vᵢ / V_totaal
        - ``d_i``       : verwachte foutfractie (0 indien niet opgegeven)
        - ``n_max``     : maximale n waarbij Δᵢ gegarandeerd detecteerbaar is
        - ``g_min``     : minimale granulariteit die nodig is voor n_huidig
        - ``n_huidig``  : huidige steekproefgrootte (alleen als n_kolom opgegeven)
        - ``status``    : ``"OK"`` of ``"WAARSCHUWING"``

    Raises
    ------
    ValueError
        Als n_kolom is opgegeven maar niet in steekproeven voorkomt.
    """
    if n_kolom is not None and n_kolom not in steekproeven.columns:
        raise ValueError(
            f"Kolom '{n_kolom}' niet gevonden in steekproeven. "
            f"Beschikbare kolommen: {list(steekproeven.columns)}"
        )

    waarde_hoog = (
        steekproeven["waarde_hoog"].fillna(0)
        if "waarde_hoog" in steekproeven.columns
        else 0
    )
    fout_hoog = (
        steekproeven["fout_hoog"].fillna(0)
        if "fout_hoog" in steekproeven.columns
        else 0
    )
    v_totaal = float(
        steekproeven["waarde_laag"].sum() + np.asarray(waarde_hoog + fout_hoog).sum()
    )

    heeft_d_kolom = "verwachte_foutfractie" in steekproeven.columns

    rijen = []

    for _, rij in steekproeven.iterrows():
        v_i = float(rij["waarde_laag"])
        gewicht = v_i / v_totaal if v_totaal > 0 else 0.0
        d_i = float(rij["verwachte_foutfractie"]) if heeft_d_kolom else 0.0

        n_huidig = int(rij[n_kolom]) if n_kolom is not None else None

        n_max = _maximale_n(granulariteit, d_i, gewicht, zekerheid)
        g_min = (
            _minimale_granulariteit(n_huidig, d_i, gewicht, zekerheid)
            if n_huidig
            else None
        )

        if n_huidig is not None and n_huidig >= n_max:
            status = "WAARSCHUWING"
            g_min_str = f"{g_min:,}" if g_min is not None else "onbekend"
            warnings.warn(
                f"Stratum '{rij['naam']}': n={n_huidig} ≥ n_max={n_max}. "
                f"De foutreductie per stap kan ondetecteerbaar worden voor de FFT. "
                f"Verhoog granulariteit naar minimaal {g_min_str} "
                f"(nu: {granulariteit:,}).",
                stacklevel=2,
            )
        else:
            status = "OK"

        rijen.append({
            "naam": rij["naam"],
            "gewicht": round(gewicht, 4),
            "d_i": round(d_i, 6),
            "n_max": n_max,
            "g_min": g_min,
            "n_huidig": n_huidig,
            "status": status,
        })

    rapport = pd.DataFrame(rijen)

    if n_kolom is None:
        rapport = rapport.drop(columns=["n_huidig", "g_min", "status"])

    return rapport


def _delta_i(n_i: int, d_i: float, w_i: float, zekerheid: float) -> float:
    """Exacte reductie in de proxy-maximale fout bij toevoeging van één waarneming."""

    def f_max(n: int) -> float:
        k = n * d_i
        return w_i * beta_dist.ppf(zekerheid, k + 1, n - k + 1)

    return f_max(n_i) - f_max(n_i + 1)


def _maximale_n(granulariteit: int, d_i: float, w_i: float, zekerheid: float) -> int:
    """Grootste gehele n waarbij Δᵢ(n) ≥ 1/g, bepaald via binair zoeken."""
    target = 1.0 / granulariteit
    if _delta_i(1, d_i, w_i, zekerheid) < target:
        return 0
    lo, hi = 1, 100_000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _delta_i(mid, d_i, w_i, zekerheid) >= target:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _minimale_granulariteit(
    n_target: int, d_i: float, w_i: float, zekerheid: float
) -> int | None:
    """Minimale granulariteit g, waarbij Δᵢ(n_target) ≥ 1/g."""
    d = _delta_i(n_target, d_i, w_i, zekerheid)
    if d <= 0:
        return None
    return int(math.ceil(1.0 / d))  # Dus ⌈1/d⌉
