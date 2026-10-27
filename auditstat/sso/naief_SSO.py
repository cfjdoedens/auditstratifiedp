def naief_match_SSO(n, k, N_klant):
    """Naïeve pooling-benadering voor een effectieve (n_eff, k_eff) per klant.

    Dit is een eenvoudige, niet-statistisch-onderbouwde heuristiek —
    bedoeld als referentiepunt/vergelijkingsmethode naast de rigoureuzere
    momentmatching-aanpak van ``moment_match_SSO``, niet als vervanging
    ervan.

    Achtergrond
    -----------
    ``n`` is de SSO-brede steekproefomvang voor een type post, ``N_klant``
    is het aantal posten van dat type bij de klant. De heuristiek
    behandelt deze twee grootheden als twee "bronnen van informatie" die
    naar analogie van weerstanden in parallel gepoold worden:

        n_eff = n · N_klant / (n + N_klant)

    Deze formule voldoet aan twee natuurlijke randgevallen:

    - Als ``N_klant`` veel groter is dan ``n`` (een grote klant binnen een
      kleine SSO-steekproef), nadert ``n_eff`` tot ``n``: de SSO-steekproef
      zelf blijft dan de beperkende factor.
    - Als ``N_klant`` veel kleiner is dan ``n`` (een kleine klant binnen
      een grote SSO-steekproef), nadert ``n_eff`` tot ``N_klant``: de
      kleine klantpopulatie zelf is dan de beperkende factor (bij een
      100%-controle van een kleine populatie is de "effectieve
      steekproefomvang" immers hooguit de populatieomvang zelf).

    Dit is uitdrukkelijk geen afleiding uit een onderliggend kansmodel
    (vergelijk de Var(X) ≤ p(1-p)-redenering achter ``moment_match_SSO``'s
    exacte grens) — het is een plausibiliteitsargument op basis van deze
    twee grensgevallen, niet een statistisch gemotiveerde kalibratie.

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
