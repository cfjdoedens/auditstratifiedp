def naief_match_SSO(n, k, N_klant):
    """Naïeve pooling-benadering voor een effectieve (n_eff, k_eff) per klant.

    Dit is een eenvoudige eerste-orde-benadering (variantie-matching), een
    gelijkwaardig alternatief naast de scherpere maar complexere
    momentmatching-aanpak van ``moment_match_SSO``. In de praktijk geeft ze
    meestal een conservatievere (ruimere) grens; onder zeer extreme
    omstandigheden (een zeer kleine ``N_klant``, bijv. 1) is dat niet
    gegarandeerd.

    Achtergrond
    -----------
    ``n`` is de SSO-brede steekproefomvang voor een type post, ``N_klant``
    is het aantal posten van dat type bij de klant. De onzekerheid over
    de foutfractie bij de klant heeft twee bronnen: de posterior-variantie
    van de SSO-brede foutkans ``p`` (bij benadering ``p(1-p)/n``) en de
    steekproefvariantie van de klant rond die foutkans (bij benadering
    ``p(1-p)/N_klant``). Samen (wet van de totale variantie):

        Var ≈ p(1-p) · (1/n + 1/N_klant)

    Gelijkstellen aan ``p(1-p)/n_eff`` geeft de parallelformule (zoals
    weerstanden in parallel):

        n_eff = n · N_klant / (n + N_klant)

    Voor het Poisson-model (varianties ``p/n`` en ``p/N_klant``) komt in
    eerste orde dezelfde formule uit. De formule voldoet aan twee
    natuurlijke randgevallen:

    - Als ``N_klant`` veel groter is dan ``n`` (een grote klant binnen een
      kleine SSO-steekproef), nadert ``n_eff`` tot ``n``: de SSO-steekproef
      zelf blijft dan de beperkende factor.
    - Als ``N_klant`` veel kleiner is dan ``n`` (een kleine klant binnen
      een grote SSO-steekproef), nadert ``n_eff`` tot ``N_klant``: de
      kleine klantpopulatie zelf is dan de beperkende factor (bij een
      100%-controle van een kleine populatie is de "effectieve
      steekproefomvang" immers hooguit de populatieomvang zelf).

    Het blijft een eerste-orde-benadering: ze gebruikt ``p(1-p)/n`` voor de
    posterior-variantie (zonder correcties zoals de ``+2`` in de variantie
    van de Beta-verdeling) en is niet gekalibreerd op de volledige
    samengestelde verdeling, zoals ``moment_match_SSO`` dat wel doet.

    ``k_eff`` wordt proportioneel aan ``n_eff`` meegeschaald, zodat de
    geschatte foutfractie ``k/n`` behouden blijft:

        k_eff = k · n_eff / n

    Parameters
    ----------
    n : float
        Steekproefomvang bij de SSO voor dit type post. Moet positief zijn.
    k : float
        Aantal fouten in de SSO-steekproef voor dit type post. Moet
        tussen 0 en ``n`` liggen.
    N_klant : float
        Aantal posten van dit type bij de klant. Moet positief zijn.

    Returns
    -------
    tuple[float, float]
        ``(n_eff, k_eff)``.
    """
    if n <= 0:
        raise ValueError("n moet positief zijn.")
    if N_klant <= 0:
        raise ValueError("N_klant moet positief zijn.")
    if k < 0 or k > n:
        raise ValueError("k moet tussen 0 en n liggen.")

    n_eff = n * N_klant / (n + N_klant)
    k_eff = k * n_eff / n
    return n_eff, k_eff
