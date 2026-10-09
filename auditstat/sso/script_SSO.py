# script_sso_toepassing.py

import numpy as np

from auditstat.sso.max_fout_benaderd_SSO import max_fout_benaderd_SSO
from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO
from auditstat.sso.plot_max_fout_vergelijking_SSO import plot_max_fout_vergelijking_SSO
from auditstat.sso.simuleer_SSO import simuleer_SSO


def script_SSO():
    n_basis = 200
    k_basis = 0
    N_klant_basis = 150
    zekerheid_basis = 0.95
    verdeling = "binomiaal"

    print("--- 1. Puntberekening ---")
    exact = max_fout_exact_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling
    )
    benaderd = max_fout_benaderd_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling
    )

    print(
        f"Instellingen: n={n_basis}, k={k_basis}, N_klant={N_klant_basis}, Zekerheid={zekerheid_basis}"
    )
    print(f"Exacte methode:   {exact:.4f} ({exact * 100:.2f}%)")
    print(f"Benaderingsmethode: {benaderd:.4f} ({benaderd * 100:.2f}%)")

    print("\n--- 2. Validatie via Simulatie ---")
    print("Simuleren over 1.000.000 iteraties... Dit duurt enkele seconden.")
    sim = simuleer_SSO(
        n_basis, k_basis, N_klant_basis, zekerheid_basis, verdeling, iteraties=1000000
    )

    print(f"Simulatie grens (discreet, empirisch): {sim:.4f} ({sim * 100:.2f}%)")
    print("Let op: De simulatie geeft uiteraard een discrete fractie (bijv. 4/150).")
    print(
        "De analytische exacte methode trekt dit door de interpolatie-logica juist continu door."
    )

    print("\n--- 3. Visuele vergelijking ---")
    # Vector voor N_klant van 10 tot 500 om het asymptotische effect te zien
    N_klant_vec = np.arange(10, 501, 10)
    print("Grafiek wordt gegenereerd...")
    plot_max_fout_vergelijking_SSO(
        n=n_basis,
        k=k_basis,
        N_klant=N_klant_vec,
        zekerheid=zekerheid_basis,
        verdeling=verdeling,
    )


if __name__ == "__main__":
    script_SSO()
