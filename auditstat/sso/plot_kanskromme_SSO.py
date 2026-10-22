import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from scipy.special import gammaln

from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO
from auditstat.sso.max_fout_exact_continu_SSO import (
    _betabinom_continu_pdf,
    max_fout_exact_continu_SSO,
)
from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO


def plot_kanskromme_SSO(n, k, N_klant, zekerheid=0.95, verdeling="binomiaal"):
    """
    Plot de kanskromme (kansdichtheid) van de foutfractie bij de klant,
    voor de exacte, de continu-doorgetrokken-exacte en de benaderde
    methode.

    De exacte methode gaat uit van de werkelijke, discrete voorspellende
    verdeling (Beta-Binomiaal resp. Negatief-Binomiaal): de foutfractie kan
    alleen de waarden 0/N_klant, 1/N_klant, ..., N_klant/N_klant aannemen.
    Deze wordt getoond als een getrapte, gevulde kromme.

    De exact-continue methode trekt dezelfde kansmassafunctie analytisch
    door naar reële foutfracties (zie max_fout_exact_continu_SSO), zonder
    de twee onzekerheidslagen (Beta-posterior en steekproefvariabiliteit
    bij de klant) samen te voegen. Deze wordt getoond als een vloeiende
    stippellijn boven op de getrapte kromme.

    De benaderde methode vervangt dit door een andere, eenvoudiger
    continue verdeling (Beta resp. Gamma) op basis van een effectieve
    steekproefomvang bij de klant (n_klant, k_klant), waarbij de twee
    onzekerheidslagen wél worden samengevoegd tot één enkele. Deze wordt
    getoond als een vloeiende lijn.

    De bijbehorende maximale foutfracties (bij de gekozen zekerheid) worden
    als verticale stippellijnen getoond.

    Parameters
    ----------
    n, k : int
        Omvang en aantal fouten in de steekproef bij SSO.
    N_klant : int
        Aantal posten bij de klant.
    zekerheid : float, standaard 0.95
        Gewenste statistische zekerheid.
    verdeling : {"binomiaal", "poisson"}, standaard "binomiaal"

    Returns
    -------
    matplotlib.figure.Figure
    """
    if verdeling not in ("binomiaal", "poisson"):
        raise ValueError("Kies 'binomiaal' of 'poisson'")

    exact_max = max_fout_exact_SSO(n, k, N_klant, zekerheid, verdeling)
    exact_continu_max = max_fout_exact_continu_SSO(n, k, N_klant, zekerheid, verdeling)
    benaderd_max = max_fout_benaderd_SSO(n, k, N_klant, zekerheid, verdeling)

    # Effectieve steekproefomvang/aantal fouten bij de klant (voor de
    # benaderde, continue verdeling).
    n_klant = (n * N_klant) / (n + N_klant)
    k_klant = (n_klant / n) * k

    x_counts = np.arange(0, N_klant + 1)
    exact_fracties = x_counts / N_klant

    x_lim = min(1.0, max(exact_max, exact_continu_max, benaderd_max) * 3)
    if x_lim <= 0:
        x_lim = 1.0
    fracties_cont = np.linspace(0, x_lim, 500)
    # De exact-continue dichtheid is alleen gedefinieerd op [0, N_klant]
    # (aantal fouten), dus begrensd tot x_lim in foutfractie-termen.
    tellingen_cont = fracties_cont * N_klant

    if verdeling == "binomiaal":
        exact_pmf = stats.betabinom.pmf(x_counts, N_klant, k + 1, n - k + 1)
        exact_continu_dichtheid = (
            _betabinom_continu_pdf(tellingen_cont, N_klant, k + 1, n - k + 1) * N_klant
        )
        benaderd_dichtheid = stats.beta.pdf(
            fracties_cont, k_klant + 1, n_klant - k_klant + 1
        )
        exact_label = "Exact (Beta-Binomiaal, discreet)"
        exact_continu_label = "Exact, continu doorgetrokken"
        benaderd_label = "Benadering (Beta)"
    else:
        p_succes = n / (n + N_klant)
        exact_pmf = stats.nbinom.pmf(x_counts, k + 1, p_succes)
        r = k + 1
        exact_continu_dichtheid = (
            np.exp(
                r * np.log(p_succes)
                + tellingen_cont * np.log(1 - p_succes)
                + gammaln(tellingen_cont + r)
                - gammaln(r)
                - gammaln(tellingen_cont + 1)
            )
            * N_klant
        )
        benaderd_dichtheid = stats.gamma.pdf(
            fracties_cont, a=k_klant + 1, scale=1.0 / n_klant
        )
        exact_label = "Exact (Negatief-Binomiaal, discreet)"
        exact_continu_label = "Exact, continu doorgetrokken"
        benaderd_label = "Benadering (Gamma)"

    # Kansdichtheid per eenheid fractie: de PMF-massa op elk gridpunt
    # i/N_klant omgerekend naar een dichtheid (gridpunten liggen 1/N_klant
    # uit elkaar).
    exact_dichtheid = exact_pmf * N_klant

    zichtbaar = exact_fracties <= x_lim

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.fill_between(
        exact_fracties[zichtbaar],
        exact_dichtheid[zichtbaar],
        step="mid",
        alpha=0.35,
        color="#2980b9",
    )
    ax.plot(
        exact_fracties[zichtbaar],
        exact_dichtheid[zichtbaar],
        drawstyle="steps-mid",
        color="#2980b9",
        linewidth=1.2,
        label=exact_label,
    )
    ax.plot(
        fracties_cont,
        exact_continu_dichtheid,
        color="#1b4f72",
        linestyle=":",
        linewidth=2,
        label=exact_continu_label,
    )
    ax.plot(
        fracties_cont,
        benaderd_dichtheid,
        color="#e67e22",
        linewidth=2,
        label=benaderd_label,
    )

    ax.axvline(
        exact_max,
        color="#2980b9",
        linestyle="--",
        linewidth=1.5,
        label=f"Max. fout exact ({zekerheid * 100:.0f}%): {exact_max:.4f}",
    )
    ax.axvline(
        exact_continu_max,
        color="#1b4f72",
        linestyle=":",
        linewidth=1.5,
        label=f"Max. fout exact continu ({zekerheid * 100:.0f}%): {exact_continu_max:.4f}",
    )
    ax.axvline(
        benaderd_max,
        color="#e67e22",
        linestyle="--",
        linewidth=1.5,
        label=f"Max. fout benaderd ({zekerheid * 100:.0f}%): {benaderd_max:.4f}",
    )

    ax.set_xlim(0, x_lim)
    ax.set_xlabel("foutfractie bij de klant")
    ax.set_ylabel("kansdichtheid")
    fig.suptitle(
        "Kanskromme foutfractie bij de klant: exact vs. benaderd",
        fontweight="bold",
        fontsize=13,
    )
    ax.set_title(
        f"n={n}, k={k}, N_klant={N_klant}, zekerheid={zekerheid}, "
        f"verdeling={verdeling}",
        fontsize=10,
    )
    ax.legend(fontsize=9)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    fig.tight_layout()
    # Alleen tonen bij een interactieve backend; bij bijv. Streamlit (Agg)
    # geeft plt.show() alleen een onnodige waarschuwing.
    if matplotlib.get_backend().lower() != "agg":
        plt.show()
    return fig
