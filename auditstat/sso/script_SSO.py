# Demonstreert de gestratificeerde, geld-gebaseerde SSO-klantevaluatie.

from auditstat.sso.evalueer_SSO_klant_gestratificeerd import (
    evalueer_SSO_klant_gestratificeerd,
)
from auditstat.stratified.plot_kanskromme import plot_kanskromme


def script_SSO():
    post_typen = [
        dict(
            naam="Emolumenten",
            n=120,
            k=1,
            N_klant=400,
            waarde_laag=2_000_000.0,
        ),
        dict(
            naam="Inkoopfacturen",
            n=200,
            k=1,
            N_klant=1500,
            waarde_laag=5_000_000.0,
        ),
    ]
    zekerheid = 0.95

    print("--- Gestratificeerde evaluatie van een SSO-klant ---")
    print(f"Zekerheid: {zekerheid}")
    for post in post_typen:
        print(
            f"  {post['naam']}: n={post['n']}, k={post['k']}, "
            f"N_klant={post['N_klant']}, waarde_laag={post['waarde_laag']:,.0f}"
        )

    resultaat = evalueer_SSO_klant_gestratificeerd(
        post_typen, model="binomiaal", zekerheid=zekerheid
    )

    print(f"\nMaximale fout (fractie): {resultaat['max_fout_convolutie']:.4f}")
    print(f"Maximale fout (euro's): {resultaat['max_fout_convolutie_geld']:,.2f}")

    plot_kanskromme(resultaat)


if __name__ == "__main__":
    script_SSO()
