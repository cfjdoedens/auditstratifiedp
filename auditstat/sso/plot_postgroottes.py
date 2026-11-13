"""Visueel inzicht in postgroottes: Lorenz-curven bij een gegeven CV.

De Lorenz-curve zet het cumulatieve aandeel van de posten (kleinste eerst,
horizontaal) uit tegen het cumulatieve aandeel van de totale waarde
(verticaal). Bij gelijke posten (CV = 0) is de curve de diagonaal; hoe groter
de CV, hoe verder de curve eronder zakt: een klein deel van de posten bevat
dan een groot deel van de waarde.

Niveau 2 van de SSO-evaluatie modelleert de postbedragen als Gamma-verdeeld
met variatiecoëfficiënt ``cv``. De Lorenz-curve van een Gamma-verdeling met
vormparameter ``a = 1/cv²`` is, onafhankelijk van het gemiddelde,
``L(p) = I(a+1, Q(p; a))``: de regularized incomplete gamma-functie met
vormparameter ``a+1``, geëvalueerd in het p-kwantiel van Gamma(a).
"""

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from scipy.special import gammainc, gammaincinv, gammaln
from scipy.stats import gamma as gamma_verdeling

from auditstat._formatting import nl_getal, nl_getal_variabel, nl_tick_formatter

_PUNTEN = 400


def _controleer_cv(cv: float) -> float:
    if not isinstance(cv, (int, float)) or isinstance(cv, bool):
        raise TypeError("cv moet een getal zijn.")
    if not math.isfinite(cv) or cv < 0:
        raise ValueError("cv moet een eindig getal van minstens 0 zijn.")
    return float(cv)


def lorenz_gamma(cv: float, p) -> np.ndarray:
    """Lorenz-curve L(p) van Gamma-verdeelde postbedragen met variatiecoëfficiënt ``cv``."""
    cv = _controleer_cv(cv)
    p = np.asarray(p, dtype=float)
    if cv == 0:
        return p.copy()
    a = 1.0 / cv**2
    return np.where(
        (p > 0) & (p < 1),
        gammainc(a + 1, gammaincinv(a, np.clip(p, 1e-300, 1 - 1e-16))),
        p,
    )


def gini_gamma(cv: float) -> float:
    """Gini-coëfficiënt van een Gamma-verdeling met variatiecoëfficiënt ``cv``."""
    cv = _controleer_cv(cv)
    if cv == 0:
        return 0.0
    a = 1.0 / cv**2
    return float(math.exp(gammaln(a + 0.5) - gammaln(a + 1)) / math.sqrt(math.pi))


def aandeel_grootste_gamma(cv: float, deel: float) -> float:
    """Aandeel van de totale waarde in de grootste ``deel`` (0-1) van de posten."""
    if not 0 < deel < 1:
        raise ValueError("deel moet tussen 0 en 1 liggen.")
    return float(1.0 - lorenz_gamma(cv, np.array([1.0 - deel]))[0])


def lorenz_empirisch(waarden, max_punten: int = _PUNTEN):
    """Lorenz-curve, Gini en aandeel van de grootste 10% van een rij postbedragen.

    Geeft ``(p, L, gini, top10)``; ``p`` en ``L`` zijn uitgedund tot
    ongeveer ``max_punten`` punten (begin en eind blijven behouden).
    """
    w = np.sort(np.asarray(waarden, dtype=float))
    if w.size == 0 or not np.all(w > 0):
        raise ValueError(
            "Postbedragen moeten een niet-lege rij positieve getallen zijn."
        )
    n = w.size
    cum = np.concatenate(([0.0], np.cumsum(w) / w.sum()))
    p = np.arange(n + 1) / n
    gini = float(1.0 - 2.0 * np.trapezoid(cum, p))
    top10 = float(1.0 - np.interp(0.9, p, cum))
    stap = max(1, n // max_punten)
    idx = np.unique(np.concatenate((np.arange(0, n + 1, stap), [n])))
    return p[idx], cum[idx], gini, top10


def kenmerken_gamma(cv: float, gemiddelde: float | None = None) -> dict:
    """Kenmerken van Gamma-verdeelde postbedragen met variatiecoëfficiënt ``cv``.

    Geeft ``gini`` en ``top10`` (aandeel van de waarde in de grootste 10% van
    de posten). Is ``gemiddelde`` (euro per post) bekend, dan ook ``mediaan``
    en ``drempel_top10`` (vanaf dit bedrag hoort een post bij de grootste
    10%). Bij ``cv = 0`` zijn alle posten gelijk aan het gemiddelde. Bij
    ``cv = 1`` is het de exponentiële verdeling; voor ``cv >= 1`` is de
    dichtheid dalend (kleine posten komen het vaakst voor), voor ``cv < 1``
    ligt de modus boven nul.
    """
    cv = _controleer_cv(cv)
    res = {"gini": gini_gamma(cv), "top10": aandeel_grootste_gamma(cv, 0.1)}
    if gemiddelde is not None:
        if cv == 0:
            res["mediaan"] = res["drempel_top10"] = float(gemiddelde)
        else:
            a = 1.0 / cv**2
            schaal = gemiddelde * cv**2
            res["mediaan"] = float(gamma_verdeling.ppf(0.5, a, scale=schaal))
            res["drempel_top10"] = float(gamma_verdeling.ppf(0.9, a, scale=schaal))
    return res


def kenmerken_empirisch(waarden) -> dict:
    """Kenmerken van een rij postbedragen: aantal, gemiddelde, cv, mediaan,
    drempel van de grootste 10%, gini en aandeel van de grootste 10%."""
    w = np.asarray(waarden, dtype=float)
    _, _, gini, top10 = lorenz_empirisch(w)
    return {
        "aantal": int(w.size),
        "gemiddelde": float(w.mean()),
        "cv": float(w.std() / w.mean()),
        "mediaan": float(np.median(w)),
        "drempel_top10": float(np.quantile(w, 0.9)),
        "gini": gini,
        "top10": top10,
    }


def plot_lorenz_postgroottes(
    cv: float | None = None,
    postwaarden=None,
    referentie_cvs=(0.5, 1.0, 2.0),
    compact: bool = False,
) -> Figure:
    """Lorenz-curven van postgroottes.

    Parameters
    ----------
    cv : variatiecoëfficiënt die de gebruiker wil begrijpen (Gamma-model,
        niveau 2); wordt vet getekend.
    postwaarden : optioneel, rij postbedragen (niveau 3); de empirische
        Lorenz-curve wordt erbij getekend.
    referentie_cvs : dunne grijze referentiecurven, ter oriëntatie.
    compact : kleinere figuur met de legenda onder de grafiek, voor een smalle kolom.

    De legenda noemt per curve de Gini-coëfficiënt en het aandeel van de
    totale waarde in de grootste 10% van de posten.
    """
    if cv is None and postwaarden is None:
        raise ValueError("Geef een cv, postwaarden of beide.")
    p = np.linspace(0, 1, _PUNTEN + 1)
    fig, ax = plt.subplots(figsize=(4.6, 4.6) if compact else (7.2, 6.0))
    ax.plot(
        [0, 1],
        [0, 1],
        color="black",
        linestyle="--",
        linewidth=1,
        label="CV 0: alle posten even groot",
    )

    def _label(naam, gini, top10):
        if compact:
            return f"{naam}\nGini {nl_getal(gini, 2)}; grootste 10% = {nl_getal(100 * top10, 0)}% van de waarde"
        return f"{naam} (Gini {nl_getal(gini, 2)}; grootste 10% = {nl_getal(100 * top10, 0)}% van de waarde)"

    for rcv in referentie_cvs:
        if cv is not None and math.isclose(rcv, cv):
            continue
        ax.plot(
            p,
            lorenz_gamma(rcv, p),
            color="0.65",
            linewidth=1,
            label=_label(
                f"CV {nl_getal_variabel(rcv)}",
                gini_gamma(rcv),
                aandeel_grootste_gamma(rcv, 0.1),
            ),
        )
    if cv is not None and cv > 0:
        ax.plot(
            p,
            lorenz_gamma(cv, p),
            color="tab:blue",
            linewidth=2.5,
            label=_label(
                f"CV {nl_getal_variabel(round(cv, 4))} (Gamma)",
                gini_gamma(cv),
                aandeel_grootste_gamma(cv, 0.1),
            ),
        )
    if postwaarden is not None:
        pe, le, gini_e, top_e = lorenz_empirisch(postwaarden)
        cv_e = float(np.std(postwaarden) / np.mean(postwaarden))
        ax.plot(
            pe,
            le,
            color="tab:red",
            linewidth=2.5,
            label=_label(f"postenbestand (CV {nl_getal(cv_e, 2)})", gini_e, top_e),
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.xaxis.set_major_formatter(nl_tick_formatter(1))
    ax.yaxis.set_major_formatter(nl_tick_formatter(1))
    ax.set_xlabel(
        "aandeel van de posten (kleinste eerst)"
        if compact
        else "cumulatief aandeel van de posten (kleinste eerst)",
        fontsize=8 if compact else None,
    )
    ax.set_ylabel(
        "aandeel van de totale waarde"
        if compact
        else "cumulatief aandeel van de totale waarde",
        fontsize=8 if compact else None,
    )
    ax.set_title("Lorenz-curve van de postgroottes", fontsize=10 if compact else None)
    ax.grid(alpha=0.3)
    if compact:
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            fontsize=7,
            frameon=False,
        )
    else:
        ax.legend(loc="upper left", fontsize=8, frameon=True)
    fig.tight_layout()
    return fig
