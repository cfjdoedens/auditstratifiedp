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

    # Onderschrift bij de plot: vaste parameters, plus de gevarieerde
    # parameter met zijn bereik.
    vaste_params = {name: val for name, val in params.items() if name != var_name}
    vaste_params_tekst = ", ".join(
        f"{name}={val}" for name, val in vaste_params.items()
    )
    gevarieerd_tekst = f"{var_name}={min(var_vector)}..{max(var_vector)}"
    onderschrift = f"vast: {vaste_params_tekst}; gevarieerd: {gevarieerd_tekst}"

    plt.figure(figsize=(10, 6))
    plt.plot(
        var_vector, exact_vals, label="Exact (Beta-Binomiaal)", marker="o", markersize=4
    )
    plt.plot(
        var_vector,
        benaderd_vals,
        label="Benadering met $ n_{klant} = (n * N_{klant}) / (n + N_{klant}) $ en $ k_{klant} = k * (n_{klant} / n) $",
        linestyle="--",
        marker="x",
        markersize=4,
    )
    plt.title(
        f"Vergelijking Maximale Foutfractie ({verdeling.capitalize()})"
        f"\n({onderschrift})",
        fontsize=11,
    )
    plt.xlabel(var_name)
    plt.ylabel("Maximale Foutfractie")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
