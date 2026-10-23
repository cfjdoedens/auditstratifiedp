import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from auditstat._formatting import nl_getal, nl_tick_formatter
from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO
from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO

hoofdtitel = (
    "Vergelijking maximale foutfractie van klant SSO op basis van steekproef uit SSO, n, \n"
    "som foutfracties, k, en aantal posten klant, N_klant"
)


def _nl_param_waarde(naam, waarde):
    """Formatteert een parameterwaarde met Nederlandse notatie: 2
    decimalen voor zekerheid (een fractie), geen decimalen (met
    duizendtal-scheidingsteken) voor de overige (gehele) parameters."""
    return nl_getal(waarde, 2 if naam == "zekerheid" else 0)


def _teken_vergelijking(
    ax, n, k, N_klant, zekerheid, verdeling="binomiaal", met_titel=True
):
    """
    Berekent de exacte en benaderde foutfractie en tekent deze op de
    meegegeven Axes. Verwacht precies één lijst/array als input voor
    n, k, N_klant of zekerheid om de x-as te bepalen.
    """
    params = {"n": n, "k": k, "N_klant": N_klant, "zekerheid": zekerheid}

    # Detecteer welke parameter de vector is.
    var_name = None
    var_vector = None
    for name, val in params.items():
        if isinstance(val, (list, np.ndarray)):
            if var_name is not None:
                raise ValueError("Slechts 1 parameter mag een vector zijn.")
            var_name = name
            var_vector = val

    if var_name is None:
        raise ValueError("Geef tenminste 1 list/array mee om over te variëren.")

    exact_vals = []
    benaderd_vals = []

    for val in var_vector:
        p = params.copy()
        p[var_name] = val
        exact_vals.append(
            max_fout_exact_SSO(p["n"], p["k"], p["N_klant"], p["zekerheid"], verdeling)
        )
        benaderd_vals.append(
            max_fout_benaderd_SSO(
                p["n"], p["k"], p["N_klant"], p["zekerheid"], verdeling
            )
        )

    # Subtitel bij de plot:
    #   vaste parameters, plus de gevarieerde parameter met zijn bereik, en de verdeling.
    vaste_params = {name: val for name, val in params.items() if name != var_name}
    vaste_params_tekst = ", ".join(
        f"{name}={_nl_param_waarde(name, val)}" for name, val in vaste_params.items()
    )
    gevarieerd_tekst = (
        f"{var_name}={_nl_param_waarde(var_name, min(var_vector))}.."
        f"{_nl_param_waarde(var_name, max(var_vector))}"
    )
    subtitel = f"{vaste_params_tekst}; {gevarieerd_tekst}, verdeling: {verdeling}"

    ax.plot(
        var_vector, exact_vals, label="Exact (Beta-Binomiaal)", marker="o", markersize=4
    )
    ax.plot(
        var_vector,
        benaderd_vals,
        label="Benadering met $ n_{klant} = (n * N_{klant}) / (n + N_{klant}) $ en $ k_{klant} = k * (n_{klant} / n) $",
        linestyle="--",
        marker="x",
        markersize=4,
    )
    if met_titel:
        ax.set_title(
            f"{hoofdtitel}\n{subtitel}",
            fontsize=11,
        )
    else:
        ax.set_title(
            f"{subtitel}",
            fontsize=11,
        )
    ax.set_xlabel(var_name)
    ax.set_ylabel("maximale foutfractie")
    ax.xaxis.set_major_formatter(nl_tick_formatter(2 if var_name == "zekerheid" else 0))
    ax.yaxis.set_major_formatter(nl_tick_formatter(4))
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    return var_name


def plot_max_fout_vergelijking_SSO(n, k, N_klant, zekerheid, verdeling="binomiaal"):
    """
    Plot de exacte en benaderde foutfractie. Verwacht precies één lijst/array als input
    voor n, k, N_klant of zekerheid om de x-as te bepalen.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    _teken_vergelijking(ax, n, k, N_klant, zekerheid, verdeling, met_titel=True)
    plt.tight_layout()
    # Alleen tonen bij een interactieve backend; bij bijv. Streamlit (Agg)
    # geeft plt.show() alleen een onnodige waarschuwing.
    if matplotlib.get_backend().lower() != "agg":
        plt.show()
    return fig


def plot_max_fout_vergelijking_SSO_overzicht(parameter_sets):
    """
    Combineert meerdere aanroepen van plot_max_fout_vergelijking_SSO in één
    figuur met een 2x2-raster subplots.

    Parameters
    ----------
    parameter_sets : list[dict]
        Lijst van precies 4 kwargs-dictionaries, elk met dezelfde sleutels
        als plot_max_fout_vergelijking_SSO (n, k, N_klant, zekerheid en
        optioneel verdeling). Per dictionary moet precies één van
        n/k/N_klant/zekerheid een lijst/array zijn.
    titel : str, optioneel
        Gezamenlijke titel boven de 4 subplots.

    Returns
    -------
    matplotlib.figure.Figure
        De figuur met de 4 subplots, zodat deze desgewenst verder bewerkt
        of opgeslagen kan worden door de aanroeper.
    """
    if len(parameter_sets) != 4:
        raise ValueError(
            "Verwacht precies 4 parametersets voor het 2x2-overzicht, "
            f"kreeg er {len(parameter_sets)}."
        )

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for ax, params in zip(axes.flat, parameter_sets, strict=True):
        _teken_vergelijking(ax, **params, met_titel=False)

    fig.suptitle(hoofdtitel, fontsize=14)

    plt.tight_layout()
    # Alleen tonen bij een interactieve backend; bij bijv. Streamlit (Agg)
    # geeft plt.show() alleen een onnodige waarschuwing.
    if matplotlib.get_backend().lower() != "agg":
        plt.show()
    return fig
