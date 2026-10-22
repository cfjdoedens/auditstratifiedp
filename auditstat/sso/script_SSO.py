# Pas de diverse functies van auditstat.SSO toe in 1 script.

import numpy as np

from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO
from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO
from auditstat.sso.plot_kanskromme_SSO import plot_kanskromme_SSO
from auditstat.sso.plot_max_fout_vergelijking_SSO import (
    # plot_max_fout_vergelijking_SSO,
    plot_max_fout_vergelijking_SSO_overzicht,
)
from auditstat.sso.simuleer_SSO import simuleer_SSO


def script_SSO():
    n_basis = 200
    k_basis = 0
    N_klant_basis = 1500
    zekerheid_basis = 0.95
    iteraties = 10_000_000
    verdeling = "binomiaal"

    print("--- 1. Puntberekening ---")
    print(
        f"Instellingen: n={n_basis}, k={k_basis}, N_klant={N_klant_basis}, Zekerheid={zekerheid_basis}"
    )

    exact = max_fout_exact_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling
    )
    benaderd = max_fout_benaderd_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling
    )

    print(f"Exacte methode:   {exact:.4f} ({exact * 100:.2f}%)")
    print(f"Benaderingsmethode: {benaderd:.4f} ({benaderd * 100:.2f}%)")

    print("\n--- 2. Validatie via Simulatie ---")
    print(
        f"Instellingen: n={n_basis}, k={k_basis}, N_klant={N_klant_basis}, Zekerheid={zekerheid_basis}"
    )
    print(f"Simuleren over {iteraties} iteraties... Dit duurt enkele seconden.")
    sim = simuleer_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling, iteraties=iteraties
    )

    print(f"Simulatie grens (discreet, empirisch): {sim:.4f} ({sim * 100:.2f}%)")
    print("Let op: De simulatie geeft uiteraard een discrete fractie (bijv. 4/150).")
    print(
        "De analytische exacte methode trekt dit door de interpolatie-logica juist continu door."
    )

    print("\n--- 3. Visuele vergelijking ---")
    n_basis_vec = np.arange(10, 1001, 10)
    k_basis_vec = np.arange(0, n_basis, 1)
    zekerheid_vec = np.arange(0.6, 0.99, 0.01)
    N_klant_vec = np.arange(10, 1001, 10)
    plot_max_fout_vergelijking_SSO_overzicht(
        [
            dict(
                n=n_basis_vec,
                k=k_basis,
                N_klant=N_klant_basis,
                zekerheid=zekerheid_basis,
                verdeling=verdeling,
            ),
            dict(
                n=n_basis,
                k=k_basis_vec,
                N_klant=500,
                zekerheid=zekerheid_basis,
                verdeling=verdeling,
            ),
            dict(
                n=n_basis,
                k=k_basis,
                N_klant=N_klant_vec,
                zekerheid=zekerheid_basis,
                verdeling=verdeling,
            ),
            dict(
                n=n_basis,
                k=k_basis,
                N_klant=N_klant_basis,
                zekerheid=zekerheid_vec,
                verdeling=verdeling,
            ),
        ],
    )

    print("\n--- 4. Kanskromme exact vs. benaderd ---")
    plot_kanskromme_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling
    )


if __name__ == "__main__":
    script_SSO()
