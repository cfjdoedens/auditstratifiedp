import matplotlib.pyplot as plt
import numpy as np

from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO
from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO


def plot_max_fout_vergelijking_SSO(n, k, N_klant, zekerheid, verdeling="binomiaal"):
    """
    Plot de exacte en benaderde foutfractie. Verwacht precies één lijst/array als input
    voor n, k, N_klant of zekerheid om de x-as te bepalen.
    """
    params = {"n": n, "k": k, "N_klant": N_klant, "zekerheid": zekerheid}

    # Detecteer welke parameter de vector is
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

    plt.figure(figsize=(10, 6))
    plt.plot(
        var_vector, exact_vals, label="Exact (Beta-Binomiaal)", marker="o", markersize=4
    )
    plt.plot(
        var_vector,
        benaderd_vals,
        label="Benadering ($n_{klant}$)",
        linestyle="--",
        marker="x",
        markersize=4,
    )
    plt.title(
        f"Vergelijking Maximale Foutfractie ({verdeling.capitalize()}) - Gevarieerd: {var_name}"
    )
    plt.xlabel(var_name)
    plt.ylabel("Maximale Foutfractie")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()
