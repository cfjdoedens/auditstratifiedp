"""
Projectie van een nog niet afgeronde gestratificeerde geldsteekproef.

Hoofdfunctie is projecteer_geldsteek_gestratificeerd().
"""

__all__ = ["projecteer_geldsteek_gestratificeerd"]

import numbers

import numpy as np
import pandas as pd
from scipy.stats import betabinom, nbinom

from .evalueer_geldsteek_gestratificeerd import evalueer_geldsteek_gestratificeerd

_VERPLICHT = ("naam", "waarde_laag", "n_laag", "n_tot_nu", "k_tot_nu")
_NAAM_SCENARIO = ("optimistisch", "verwacht", "pessimistisch")


def _is_geheel(x) -> bool:
    return float(x).is_integer()


def _kwantiel_extra_fouten(
    model: str, n: float, k: float, m: int, kwantiel: float
) -> int:
    """
    Kleinste x waarvoor P(X <= x) >= kwantiel, met X het aantal fouten in de m
    nog te beoordelen posten, gegeven k fouten in n beoordeelde posten.

    Vlakke prior voor de foutkans. Binomiaal: Beta-Binomiaal(m, k+1, n-k+1).
    Poisson: Negatief-Binomiaal(k+1, n/(n+m)).
    """
    if m <= 0:
        return 0
    if model == "binomiaal":
        x = betabinom.ppf(kwantiel, m, k + 1, n - k + 1)
    else:
        x = nbinom.ppf(kwantiel, k + 1, n / (n + m))
    return int(min(max(x, 0), m))


def projecteer_geldsteek_gestratificeerd(
    steekproeven: pd.DataFrame,
    model: str = "binomiaal",
    zekerheid: float = 0.95,
    granulariteit: int | None = None,
    pessimistisch_kwantiel: float = 0.80,
    materialiteit_geld: float | None = None,
) -> dict:
    """
    Projecteer de eindevaluatie van een nog niet afgeronde geldsteekproef.

    Tijdens het uitvoeren van een steekproef zijn per stratum alleen de eerste
    ``n_tot_nu`` van de geplande ``n_laag`` posten beoordeeld. Deze functie
    rekent drie scenario's door voor de fouten in de nog te beoordelen
    ``n_laag - n_tot_nu`` posten en zoekt per stratum hoeveel extra fouten er
    nog bij mogen komen voordat de maximale fout boven de materialiteit uitkomt.

    Scenario's voor het aantal fouten ``k_laag`` aan het einde:

    - ``optimistisch``: in de rest van de posten komt geen enkele fout meer voor.
    - ``verwacht``: de rest heeft dezelfde foutfractie als tot nu toe,
      ``k_laag = k_tot_nu + (n_laag - n_tot_nu) * p_rest`` met standaard
      ``p_rest = k_tot_nu / n_tot_nu``. Dat is gelijk aan
      ``k_tot_nu * n_laag / n_tot_nu``. Per stratum te overschrijven met de
      kolom ``p_rest``.
    - ``pessimistisch``: het ``pessimistisch_kwantiel`` van het aantal fouten
      in de rest, onder het kansmodel (vlakke prior op de foutkans; het
      aantal fouten in de rest is Beta-Binomiaal resp. Negatief-Binomiaal).
      Elk stratum krijgt zijn eigen kwantiel; samen is dat extremer dan dat
      kwantiel voor het geheel.

    De HARo-correctie voor lagere risico's (ihr, ibr, car) werkt zoals in
    ``evalueer_geldsteek_gestratificeerd``: extra foutloze posten tellen mee in
    ``n`` en niet in ``k``. Ze tellen ook mee in de voorspellende verdeling van
    het pessimistische scenario (``n_tot_nu`` plus de extra foutloze posten),
    omdat de uiteindelijke berekening ze ook meetelt. Het verwachte scenario
    extrapoleert daarentegen de waargenomen foutfractie van de echte posten
    (of ``p_rest``). Extra pessimisme zit alleen in ``pessimistisch_kwantiel``,
    los van de waarden van ihr, ibr en car.

    De grootste toelaatbare extra ``k`` per stratum (``max_extra_k``) wordt met
    binair zoeken bepaald, terwijl alle andere strata op hun verwachte ``k``
    blijven staan. De marges van de strata zijn dus niet tegelijk beschikbaar:
    gebruikt het ene stratum zijn marge, dan krimpt die van de andere.

    Aannamen: de beoordeelde posten zijn een willekeurige trekking uit het
    hele stratum, en de foutkans in het nog te beoordelen deel is gelijk aan die
    in het al beoordeelde deel. Bij een steekproef die per tranche (bijvoorbeeld
    per maand) wordt getrokken uit alleen de posten van die tranche, is die
    aanname zwaar.

    Parameters
    ----------
    steekproeven : pd.DataFrame
        Een rij per stratum. Verplicht: ``naam``, ``waarde_laag``, ``n_laag``
        (geplande totale omvang, geheel), ``n_tot_nu`` (aantal tot nu toe
        beoordeelde posten, geheel), ``k_tot_nu`` (gevonden fouten, mag
        niet-geheel zijn). Optioneel, zoals bij
        ``evalueer_geldsteek_gestratificeerd``: ``ihr``, ``ibr``, ``car``,
        ``waarde_hoog``, ``fout_hoog``, ``materialiteit``. Daarnaast de
        optionele kolom ``p_rest``: de foutfractie die je aanneemt voor de nog
        te beoordelen posten van dat stratum, in [0, 1]. Een lege waarde
        betekent: gebruik de waargenomen fractie ``k_tot_nu / n_tot_nu``.
        Verplicht voor een stratum met ``n_tot_nu = 0``.
    model : {"binomiaal", "poisson"}
        Kansmodel.
    zekerheid : float
        Zekerheid voor de maximale fout.
    granulariteit : int, optional
        Aantal roostercellen van de FFT; standaard zoals in de evaluatiefunctie.
    pessimistisch_kwantiel : float
        Kwantiel voor het pessimistische scenario, in (0, 1). Standaard 0,80.
    materialiteit_geld : float, optional
        Toelaatbare fout in euro's voor het geheel. Standaard de som over de
        strata van ``materialiteit * (waarde_laag + waarde_hoog)``. De
        evaluatie rekent de maximale fout inclusief ``fout_hoog``.

    Returns
    -------
    dict
        - ``strata``: DataFrame per stratum met ``n_rest``, ``k_optimistisch``,
          ``k_verwacht``, ``k_pessimistisch``, ``max_extra_k`` (grootste aantal
          extra fouten in de rest waarbij de maximale fout niet boven de
          materialiteit komt; ``<NA>`` als dat al bij nul extra fouten niet
          lukt) en ``marge_boven_verwacht`` (``max_extra_k`` min het verwachte
          aantal extra fouten).
        - ``samenvatting``: DataFrame per scenario met ``max_fout``,
          ``max_fout_geld``, ``materialiteit_geld`` en ``overschreden``.
        - ``evaluaties``: dict scenario -> resultaat van
          ``evalueer_geldsteek_gestratificeerd`` (voor ``plot_kanskromme``).
        - ``materialiteit_geld``, ``invoer``.

    Raises
    ------
    TypeError
        Bij een verkeerd type argument.
    ValueError
        Bij ontbrekende kolommen, ongeldige waarden, of een ongeldige
        ``pessimistisch_kwantiel`` of de kolom ``p_rest``; en de fouten van
        ``evalueer_geldsteek_gestratificeerd``.
    """
    if not isinstance(steekproeven, pd.DataFrame):
        raise TypeError("`steekproeven` moet een pandas DataFrame zijn.")
    if model not in ("binomiaal", "poisson"):
        raise ValueError("`model` moet 'binomiaal' of 'poisson' zijn.")
    for naam, waarde in (
        ("zekerheid", zekerheid),
        ("pessimistisch_kwantiel", pessimistisch_kwantiel),
    ):
        if not isinstance(waarde, numbers.Real) or isinstance(waarde, bool):
            raise TypeError(f"`{naam}` moet een getal zijn.")
    if not 0 < pessimistisch_kwantiel < 1:
        raise ValueError("`pessimistisch_kwantiel` moet in (0, 1) liggen.")
    if steekproeven.empty:
        raise ValueError("`steekproeven` is leeg.")
    ontbrekend = [k for k in _VERPLICHT if k not in steekproeven.columns]
    if ontbrekend:
        raise ValueError(f"Ontbrekende kolommen: {', '.join(ontbrekend)}.")

    basis = steekproeven.reset_index(drop=True).copy()
    if basis[list(_VERPLICHT)].isna().any().any():
        raise ValueError("NaN of ontbrekende waarden in de verplichte kolommen.")
    for kolom in ("waarde_laag", "n_laag", "n_tot_nu", "k_tot_nu"):
        if not pd.api.types.is_numeric_dtype(basis[kolom]):
            raise ValueError(f"Kolom `{kolom}` moet numeriek zijn.")
    for rij in basis.itertuples():
        label = f"Stratum '{rij.naam}'"
        if not (_is_geheel(rij.n_laag) and _is_geheel(rij.n_tot_nu)):
            raise ValueError(f"{label}: `n_laag` en `n_tot_nu` moeten geheel zijn.")
        if rij.n_tot_nu < 0 or rij.k_tot_nu < 0:
            raise ValueError(
                f"{label}: `n_tot_nu` en `k_tot_nu` mogen niet negatief zijn."
            )
        if rij.n_tot_nu > rij.n_laag:
            raise ValueError(f"{label}: `n_tot_nu` is groter dan `n_laag`.")
        if rij.k_tot_nu > rij.n_tot_nu:
            raise ValueError(f"{label}: `k_tot_nu` is groter dan `n_tot_nu`.")

    # Foutfractie in de rest per stratum: kolom `p_rest` (niet leeg), anders de
    # waargenomen fractie.
    if "p_rest" in basis.columns:
        # Een kolom met alleen None heeft dtype object; die telt als leeg.
        if basis["p_rest"].isna().all():
            basis["p_rest"] = basis["p_rest"].astype(float)
        if not pd.api.types.is_numeric_dtype(basis["p_rest"]):
            raise ValueError("Kolom `p_rest` moet numeriek zijn (of leeg).")
        p_kolom = basis["p_rest"].astype(float)
        if ((p_kolom < 0) | (p_kolom > 1)).any():
            raise ValueError("Kolom `p_rest` moet waarden in [0, 1] hebben.")
    else:
        p_kolom = pd.Series(np.nan, index=basis.index)
    p = p_kolom
    for rij, p_i in zip(basis.itertuples(), p, strict=True):
        if rij.n_tot_nu == 0 and np.isnan(p_i):
            raise ValueError(
                f"Stratum '{rij.naam}': nog niets beoordeeld; geef `p_rest` op "
                "in de kolom `p_rest` om te projecteren."
            )
    p = p.fillna(basis["k_tot_nu"] / basis["n_tot_nu"].replace(0, np.nan))
    n_rest = (basis["n_laag"] - basis["n_tot_nu"]).astype(int)
    k_nu = basis["k_tot_nu"].astype(float)
    extra_verwacht = n_rest * p

    # Kolommen voor de evaluatie: n_laag blijft de geplande omvang.
    evalueer_kolommen = [
        c
        for c in (
            "naam",
            "waarde_laag",
            "n_laag",
            "ihr",
            "ibr",
            "car",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        )
        if c in basis.columns
    ]

    def evalueer(k_laag: pd.Series) -> dict:
        tabel = basis[evalueer_kolommen].copy()
        tabel["k_laag"] = k_laag.to_numpy()
        return evalueer_geldsteek_gestratificeerd(
            tabel,
            model=model,
            zekerheid=zekerheid,
            granulariteit=granulariteit,
            vergelijk=False,
        )

    # De extra foutloze posten (HARo) hangen niet van k af; haal ze uit de
    # evaluatie van het optimistische scenario. Ze tellen mee in n, ook in de
    # voorspellende verdeling van het pessimistische scenario, net als in de
    # uiteindelijke berekening.
    evaluaties = {"optimistisch": evalueer(k_nu)}
    extra_posten = pd.Series(
        evaluaties["optimistisch"]["steekproeven"]["extra_foutloze_posten"]
        .astype(float)
        .to_numpy(),
        index=basis.index,
    )
    extra_pessimistisch = pd.Series(
        [
            _kwantiel_extra_fouten(
                model,
                r.n_tot_nu + e,
                r.k_tot_nu,
                int(m),
                pessimistisch_kwantiel,
            )
            for r, e, m in zip(basis.itertuples(), extra_posten, n_rest, strict=True)
        ],
        index=basis.index,
        dtype=float,
    )
    k_scenario = {
        "optimistisch": k_nu,
        "verwacht": k_nu + extra_verwacht,
        "pessimistisch": k_nu + extra_pessimistisch,
    }
    for naam in ("verwacht", "pessimistisch"):
        evaluaties[naam] = evalueer(k_scenario[naam])
    evaluaties = {naam: evaluaties[naam] for naam in _NAAM_SCENARIO}

    if materialiteit_geld is None:
        mat = basis["materialiteit"] if "materialiteit" in basis.columns else 0.01
        hoog = basis["waarde_hoog"] if "waarde_hoog" in basis.columns else 0.0
        materialiteit_geld = float(((basis["waarde_laag"] + hoog) * mat).sum())
    elif not materialiteit_geld > 0:
        raise ValueError("`materialiteit_geld` moet positief zijn.")

    def max_fout_geld(k_laag: pd.Series) -> float:
        return evalueer(k_laag)["max_fout_convolutie_geld"]

    def grootste_toelaatbare_extra(i: int) -> int | None:
        """Binair zoeken: max_fout is niet-dalend in k, dus halveer het interval."""
        m = int(n_rest.iloc[i])

        def f(x: int) -> float:
            k = k_scenario["verwacht"].copy()
            k.iloc[i] = k_nu.iloc[i] + x
            return max_fout_geld(k)

        if f(0) > materialiteit_geld:
            return None
        if m == 0 or f(m) <= materialiteit_geld:
            return m
        laag, hoog = 0, m  # f(laag) toelaatbaar, f(hoog) niet
        while hoog - laag > 1:
            midden = (laag + hoog) // 2
            if f(midden) <= materialiteit_geld:
                laag = midden
            else:
                hoog = midden
        return laag

    max_extra = [grootste_toelaatbare_extra(i) for i in range(len(basis))]

    strata = basis[["naam", "waarde_laag", "n_laag", "n_tot_nu", "k_tot_nu"]].copy()
    strata["n_rest"] = n_rest
    strata["extra_foutloze_posten"] = extra_posten
    strata["p_rest"] = p
    for naam, k in k_scenario.items():
        strata[f"k_{naam}"] = k
    strata["max_extra_k"] = pd.array(max_extra, dtype="Int64")
    strata["marge_boven_verwacht"] = (
        strata["max_extra_k"].astype(float) - extra_verwacht
    )

    samenvatting = pd.DataFrame({
        "scenario": list(_NAAM_SCENARIO),
        "max_fout": [evaluaties[s]["max_fout_convolutie"] for s in _NAAM_SCENARIO],
        "max_fout_geld": [
            evaluaties[s]["max_fout_convolutie_geld"] for s in _NAAM_SCENARIO
        ],
    })
    samenvatting["materialiteit_geld"] = materialiteit_geld
    samenvatting["overschreden"] = samenvatting["max_fout_geld"] > materialiteit_geld

    return {
        "strata": strata,
        "samenvatting": samenvatting,
        "evaluaties": evaluaties,
        "materialiteit_geld": materialiteit_geld,
        "invoer": {
            "model": model,
            "zekerheid": zekerheid,
            "granulariteit": granulariteit,
            "pessimistisch_kwantiel": pessimistisch_kwantiel,
        },
    }
