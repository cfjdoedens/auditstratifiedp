def n_klant_k_klant_SSO(n, k, N_klant):
    """
    Herleidt een effectieve steekproefomvang (n_klant) en een effectief
    aantal fouten (k_klant) bij de klant, op basis van een steekproef bij
    de SSO (n, k) en de omvang van de klantpopulatie (N_klant).

    Dit combineert de bewijskracht van de SSO-steekproef met de omvang
    van de klantpopulatie tot een enkele, kleinere effectieve steekproef
    bij de klant zelf (n_klant <= min(n, N_klant)), met k_klant naar rato
    verdeeld. Dit is dezelfde benadering als gebruikt in
    max_fout_benaderd_SSO.

    Parameters
    ----------
    n : int of float
        Steekproefomvang bij de SSO.
    k : int of float
        Aantal fouten in de steekproef bij de SSO.
    N_klant : int of float
        Aantal posten bij de klant.

    Returns
    -------
    tuple[float, float]
        (n_klant, k_klant)
    """
    if n <= 0:
        raise ValueError("n moet groter zijn dan 0.")
    if N_klant <= 0:
        raise ValueError("N_klant moet groter zijn dan 0.")
    if k < 0:
        raise ValueError("k mag niet negatief zijn.")
    if k > n:
        raise ValueError("k mag niet groter zijn dan n.")

    n_klant = (n * N_klant) / (n + N_klant)
    k_klant = (n_klant / n) * k
    return n_klant, k_klant
