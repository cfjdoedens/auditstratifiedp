import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import trapezoid

from auditstat.sso.max_fout_heterogeen_SSO import (
    _kwantiel_van_theta_posterior,
    _posterior_theta_klant_binomiaal,
    _posterior_theta_klant_poisson,
)


def _genormaliseerde_dichtheid(theta_grid, dichtheid_ongenormaliseerd):
    """Normaliseert een dichtheid op een vast grid zodat de oppervlakte
    eronder (via trapeziumregel) gelijk is aan 1."""
    oppervlakte = trapezoid(dichtheid_ongenormaliseerd, theta_grid)
    return dichtheid_ongenormaliseerd / oppervlakte


def plot_posterior_heterogeen_SSO(
    n, k, f_waarden, zekerheid=0.95, verdeling="binomiaal", aantal_theta=2001
):
    """
    Vergelijkt de posterior-dichtheid van de foutkans bij een SSO-klant
    onder het heterogeniteitsmodel (zie max_fout_heterogeen_SSO), voor
    een reeks waarden van f (het relatieve aandeel van de klant in de
    totale SSO-populatie), met de posterior onder het bestaande
    uitwisselbare model (max_fout_exact_SSO /
    max_fout_exact_continu_SSO). Dat laatste model gaat impliciet uit
    van f = 1: het projecteert de SSO-brede schatting zonder correctie
    op elke klant, ongeacht diens werkelijke omvang.

    Het uitwisselbare model levert een vaste, van f onafhankelijke
    posterior op theta_klant op (Beta(k + 1, n - k + 1) resp. een op
    [0, 1] getrunceerde Gamma(k + 1, n)). Het heterogene model levert
    voor elke f-waarde een eigen, doorgaans vlakkere posterior op, die
    voor kleinere f dichter bij de vlakke prior komt te liggen: hoe
    kleiner het aandeel van de klant in de SSO-brede steekproef, hoe
    minder klant-specifieke informatie die steekproef bevat.

    Parameters
    ----------
    n, k : int
        Omvang en aantal fouten in de SSO-brede steekproef.
    f_waarden : array-like van float
        Reeks te vergelijken waarden van f (relatieve omvang van de
        klant binnen de totale SSO-populatie), elk tussen 0 en 1.
    zekerheid : float, standaard 0.95
        Zekerheid waarvoor de verticale kwantiellijnen worden getekend.
    verdeling : {"binomiaal", "poisson"}, standaard "binomiaal"
    aantal_theta : int, standaard 2001
        Resolutie van het grid voor theta op [0, 1].

    Returns
    -------
    matplotlib.figure.Figure
    """
    if verdeling not in ("binomiaal", "poisson"):
        raise ValueError("Kies 'binomiaal' of 'poisson'")

    f_waarden = np.atleast_1d(np.asarray(f_waarden, dtype=float))
    if f_waarden.size == 0:
        raise ValueError("f_waarden mag niet leeg zijn.")
    if np.any((f_waarden < 0) | (f_waarden > 1)):
        raise ValueError("Elke waarde in f_waarden moet tussen 0 en 1 liggen.")
    if not (0 < zekerheid < 1):
        raise ValueError("zekerheid moet tussen 0 en 1 liggen.")

    theta_grid = np.linspace(0.0, 1.0, aantal_theta)
    posterior_fn = (
        _posterior_theta_klant_binomiaal
        if verdeling == "binomiaal"
        else _posterior_theta_klant_poisson
    )

    # Het uitwisselbare model komt overeen met f = 1 in het heterogene
    # model (zie max_fout_heterogeen_SSO voor de verificatie hiervan).
    dichtheid_ongenorm_uitwisselbaar = posterior_fn(n, k, 1.0, theta_grid)
    dichtheid_uitwisselbaar = _genormaliseerde_dichtheid(
        theta_grid, dichtheid_ongenorm_uitwisselbaar
    )
    kwantiel_uitwisselbaar = _kwantiel_van_theta_posterior(
        theta_grid, dichtheid_ongenorm_uitwisselbaar, zekerheid
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(
        theta_grid,
        dichtheid_uitwisselbaar,
        color="black",
        linewidth=2.5,
        label=f"Uitwisselbaar model (f = 1): {zekerheid * 100:.0f}%-kwantiel = {kwantiel_uitwisselbaar:.4f}",
    )
    ax.axvline(kwantiel_uitwisselbaar, color="black", linestyle="--", linewidth=1.2)

    kleuren = plt.cm.viridis(np.linspace(0.15, 0.85, len(f_waarden)))
    for f, kleur in zip(f_waarden, kleuren, strict=True):
        dichtheid_ongenorm = posterior_fn(n, k, f, theta_grid)
        dichtheid = _genormaliseerde_dichtheid(theta_grid, dichtheid_ongenorm)
        kwantiel = _kwantiel_van_theta_posterior(
            theta_grid, dichtheid_ongenorm, zekerheid
        )
        ax.plot(
            theta_grid,
            dichtheid,
            color=kleur,
            linewidth=1.8,
            label=f"Heterogeen model (f = {f:g}): {zekerheid * 100:.0f}%-kwantiel = {kwantiel:.4f}",
        )
        ax.axvline(kwantiel, color=kleur, linestyle="--", linewidth=1.0)

    ax.set_xlim(0, 1)
    ax.set_xlabel("foutkans/-fractie bij de klant (theta_klant)")
    ax.set_ylabel("kansdichtheid")
    fig.suptitle(
        "Posterior foutkans bij de klant: uitwisselbaar vs. heterogeen model",
        fontweight="bold",
        fontsize=13,
    )
    ax.set_title(f"n={n}, k={k}, verdeling={verdeling}", fontsize=10)
    ax.legend(fontsize=8.5)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    fig.tight_layout()
    # Alleen tonen bij een interactieve backend; bij bijv. Streamlit (Agg)
    # geeft plt.show() alleen een onnodige waarschuwing.
    if matplotlib.get_backend().lower() != "agg":
        plt.show()
    return fig
