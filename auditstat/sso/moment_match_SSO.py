import warnings

from scipy.stats import beta, gamma

# Referentiezekerheid waarop, uitsluitend bij klemming, wordt beoordeeld welke
# van de twee methodes (geklemde momentmatching vs. naïeve pooling) de hoogste
# (dus veiligste) maximale foutfractie oplevert. Dit is noodzakelijkerwijs een
# vaste keuze: moment_match_SSO kent de uiteindelijke, door de gebruiker
# gekozen zekerheid van eval_stratified niet (die wordt pas later toegepast).
_ZEKERHEID_VOOR_CONSERVATISME_VERGELIJKING = 0.95


def _naieve_pooling(n, k, N_klant):
    """Herleidt (n_klant, k_klant) door de SSO-steekproef en de klantpopulatie
    naar rato te poolen tot één kleinere "as-if"-steekproef (de vóór
    ``moment_match_SSO`` gebruikte aanpak, zie ``git log`` commit
    "Vervang naïeve pooling door momentmatching in SSO->gestratificeerde brug").
    """
    n_klant = (n * N_klant) / (n + N_klant)
    k_klant = (n_klant / n) * k
    return n_klant, k_klant


def _max_fout_referentie(n_eff, k_eff, verdeling):
    """Maximale foutfractie bij ``_ZEKERHEID_VOOR_CONSERVATISME_VERGELIJKING``,
    volgens dezelfde Beta- resp. Gamma-parametrisatie als ``eval_stratified``
    gebruikt. Uitsluitend bedoeld om twee (n_eff, k_eff)-kandidaten onderling
    te vergelijken op conservatisme, niet als eindresultaat.
    """
    if verdeling == "binomiaal":
        return beta.ppf(
            _ZEKERHEID_VOOR_CONSERVATISME_VERGELIJKING, k_eff + 1, n_eff - k_eff + 1
        )
    return gamma.ppf(
        _ZEKERHEID_VOOR_CONSERVATISME_VERGELIJKING, a=k_eff + 1, scale=1.0 / n_eff
    )


def moment_match_SSO(n, k, N_klant, verdeling="binomiaal"):
    """
    Kalibreert een effectieve steekproefomvang (n_eff) en een effectief
    aantal fouten (k_eff) bij de klant, zodanig dat de resulterende
    Beta- (binomiaal) resp. Gamma-verdeling (poisson) dezelfde
    gemiddelde en variantie heeft als de werkelijke, continue
    samengestelde verdeling van de foutfractie bij de klant
    (Beta-Binomiaal resp. Negatief-Binomiaal, met zowel
    posterior-onzekerheid over de ware foutkans als
    steekproefvariabiliteit van die foutkans bij de klant).

    Achtergrond
    -----------
    Een naïeve aanpak poolt de SSO-steekproef en de klantpopulatie tot
    één kleinere "as-if"-steekproef. Dat voegt de twee onzekerheidslagen
    samen tot één enkele laag, en levert daardoor zowel een vertekend
    gemiddelde als een te lage variantie op.

    Deze functie kiest in plaats daarvan (n_eff, k_eff) zó dat de
    Beta(k_eff + 1, n_eff - k_eff + 1)- resp. Gamma(k_eff + 1, schaal=1 /
    n_eff)-verdeling dezelfde eerste twee momenten heeft als de
    werkelijke samengestelde verdeling van de foutfractie bij de klant.
    Dit is bedoeld om als (n_laag, k_laag)-paar te dienen voor
    ``eval_stratified``, dat zelf intern een Beta- resp.
    Gamma-verdeling per stratum opbouwt uit (n_laag, k_laag) — zo
    draagt de gestratificeerde evaluatie zowel het juiste gemiddelde als
    (voor zover binnen de Beta/Gamma-familie mogelijk) de juiste
    variantie van de werkelijke tweelagen-onzekerheid.

    Omdat de Beta- en Gamma-familie een beperkte spreiding kunnen
    weergeven bij een gegeven gemiddelde, kan dit bij een kleine
    N_klant (t.o.v. de SSO-steekproef) resulteren in een (n_eff, k_eff)
    buiten het toegestane bereik (k_eff < 0 of k_eff > n_eff). In dat
    geval wordt eerst geklemd aan de dichtstbijzijnde geldige grens.
    Vervolgens wordt, uitsluitend in dit klemgeval, ook de (oudere,
    eenvoudiger) naïeve-poolingmethode berekend (``_naieve_pooling``) en
    wordt van de twee kandidaten — geklemde momentmatching vs. naïeve
    pooling — degene met de hoogste (dus veiligste) maximale foutfractie
    bij 95% zekerheid aangehouden. Dit is nodig omdat gebleken is dat
    geen van beide methodes in het klemgebied stelselmatig conservatiever
    is dan de ander: bij een matig kleine N_klant is naïeve pooling vaak
    conservatiever, maar bij een zeer kleine N_klant (waar de klem het
    hardst toeslaat) kan de geklemde momentmatching júist conservatiever
    uitpakken. Er wordt een ``RuntimeWarning`` afgevuurd om te melden dat
    dit is gebeurd.

    Parameters
    ----------
    n : int of float
        Steekproefomvang bij de SSO.
    k : int of float
        Aantal fouten in de steekproef bij de SSO.
    N_klant : int of float
        Aantal posten bij de klant.
    verdeling : {"binomiaal", "poisson"}, standaard "binomiaal"
        Moet overeenkomen met het ``model``-argument waarmee het
        resulterende (n_eff, k_eff)-paar straks aan ``eval_stratified``
        wordt doorgegeven.

    Returns
    -------
    tuple[float, float]
        (n_eff, k_eff)
    """
    if n <= 0:
        raise ValueError("n moet groter zijn dan 0.")
    if N_klant <= 0:
        raise ValueError("N_klant moet groter zijn dan 0.")
    if k < 0:
        raise ValueError("k mag niet negatief zijn.")
    if k > n:
        raise ValueError("k mag niet groter zijn dan n.")

    if verdeling == "binomiaal":
        alpha, beta_ = k + 1, n - k + 1
        s = alpha + beta_
        gemiddelde = alpha / s
        variantie = alpha * beta_ * (s + N_klant) / (s**2 * (s + 1) * N_klant)
        s_eff = gemiddelde * (1 - gemiddelde) / variantie - 1
        n_eff = s_eff - 2
        k_eff = gemiddelde * s_eff - 1

    elif verdeling == "poisson":
        r = k + 1
        p_succes = n / (n + N_klant)
        gemiddelde_aantal = r * (1 - p_succes) / p_succes
        variantie_aantal = r * (1 - p_succes) / p_succes**2
        gemiddelde = gemiddelde_aantal / N_klant
        variantie = variantie_aantal / N_klant**2
        n_eff = gemiddelde / variantie
        k_eff = gemiddelde**2 / variantie - 1

    else:
        raise ValueError("Kies 'binomiaal' of 'poisson'")

    geklemd = False
    if k_eff < 0:
        k_eff = 0.0
        geklemd = True
    if n_eff < k_eff:
        n_eff = k_eff
        geklemd = True

    if geklemd:
        n_naief, k_naief = _naieve_pooling(n, k, N_klant)
        if n_eff > 0:
            mf_geklemd = _max_fout_referentie(n_eff, k_eff, verdeling)
            mf_naief = _max_fout_referentie(n_naief, k_naief, verdeling)
            gebruik_naief = mf_naief > mf_geklemd
        else:
            # (n_eff, k_eff) is gedegenereerd (n_eff = 0, geen bruikbare
            # Gamma/Beta-parametrisatie); de naïeve pooling is dan sowieso
            # de enige bruikbare kandidaat.
            gebruik_naief = True

        if gebruik_naief:
            n_eff, k_eff = n_naief, k_naief

        warnings.warn(
            "De werkelijke spreiding van de foutfractie bij de klant kon niet "
            "exact gekalibreerd worden binnen de Beta/Gamma-familie (N_klant is "
            "klein t.o.v. de SSO-steekproef n). Het (n_eff, k_eff)-paar is "
            "geklemd aan de dichtstbijzijnde geldige grens, en er is "
            "vergeleken met de naïeve-poolingmethode; de conservatiefste "
            "(hoogste maximale foutfractie bij 95% zekerheid) van de twee is "
            f"aangehouden ({'naïeve pooling' if gebruik_naief else 'geklemde momentmatching'}).",
            RuntimeWarning,
            stacklevel=2,
        )

    return n_eff, k_eff
