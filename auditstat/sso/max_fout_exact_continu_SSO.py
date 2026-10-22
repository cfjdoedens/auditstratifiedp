import numpy as np
from scipy.optimize import brentq
from scipy.special import betainc, betaln, gammaln


def _betabinom_continu_pdf(x, N_klant, alpha, beta):
    """Continue (reële) uitbreiding van de Beta-Binomiaal kansmassafunctie.

    Vervangt de binomiaalcoëfficiënt C(N_klant, x) door zijn continue
    uitbreiding via de Gammafunctie, zodat x reële waarden in [0, N_klant]
    mag aannemen in plaats van uitsluitend gehele getallen. Op gehele x
    komt dit exact overeen met scipy.stats.betabinom.pmf(x, N_klant,
    alpha, beta); ertussenin levert het een analytisch vloeiende
    dichtheid op in plaats van een trapsgewijze interpolatie.
    """
    log_coef = gammaln(N_klant + 1) - gammaln(x + 1) - gammaln(N_klant - x + 1)
    log_dichtheid = (
        log_coef + betaln(x + alpha, N_klant - x + beta) - betaln(alpha, beta)
    )
    return np.exp(log_dichtheid)


def _betabinom_continu_cdf_grid(N_klant, alpha, beta, aantal_punten=4000):
    """Geeft (x_grid, cdf_grid) terug: een genormaliseerde cumulatieve
    verdeling van de continue Beta-Binomiaal-dichtheid op [0, N_klant]."""
    x = np.linspace(0, N_klant, aantal_punten)
    dichtheid = _betabinom_continu_pdf(x, N_klant, alpha, beta)
    cdf = np.concatenate((
        [0.0],
        np.cumsum((dichtheid[1:] + dichtheid[:-1]) / 2 * np.diff(x)),
    ))
    # Normaliseren: numerieke kwadratuur over een eindig grid benadert de
    # (exacte) integraal van 1 niet perfect; dit forceert cdf(N_klant) = 1.
    cdf = cdf / cdf[-1]
    return x, dichtheid, cdf


def max_fout_exact_continu_SSO(
    n, k, N_klant, zekerheid=0.95, verdeling="binomiaal", aantal_punten=4000
):
    """
    Berekent de maximale foutfractie bij de klant via een continue
    uitbreiding van het exacte model (Beta-Binomiaal resp.
    Negatief-Binomiaal), zonder de twee onzekerheidslagen samen te
    voegen zoals bij max_fout_benaderd_SSO.

    max_fout_exact_SSO rekent met de werkelijke, discrete voorspellende
    verdeling en trekt alleen de resulterende kwantielfunctie lineair
    door tussen gehele waarden. Hier wordt in plaats daarvan de
    kansmassafunctie zélf analytisch doorgetrokken naar reële x: voor
    "binomiaal" via de Gammafunctie-uitbreiding van de
    binomiaalcoëfficiënt (zie _betabinom_continu_pdf), voor "poisson"
    via de gesloten-vorm-identiteit tussen de Negatief-Binomiale CDF en
    de regularized incomplete beta-functie (die zelf al analytisch is
    in het aantal "fouten"). Beide onzekerheidslagen blijven behouden:
    de posterior-onzekerheid over de ware foutkans (Beta) én de
    steekproefvariabiliteit van die foutkans toegepast op de (hier
    continu benaderde) klantpopulatie van omvang N_klant.

    Parameters
    ----------
    n, k : int
        Omvang en aantal fouten in de steekproef bij SSO.
    N_klant : int
        Aantal posten bij de klant.
    zekerheid : float, standaard 0.95
        Gewenste statistische zekerheid.
    verdeling : {"binomiaal", "poisson"}, standaard "binomiaal"
    aantal_punten : int, standaard 4000
        Resolutie van het grid voor de numerieke integratie (alleen
        gebruikt voor verdeling="binomiaal"; "poisson" gebruikt een
        gesloten-vorm CDF en heeft dit niet nodig).

    Returns
    -------
    float
        Maximale foutfractie (aantal fouten / N_klant) bij de gekozen
        zekerheid.
    """
    if N_klant <= 0:
        raise ValueError("N_klant moet groter zijn dan 0.")
    if not (0 < zekerheid < 1):
        raise ValueError("zekerheid moet tussen 0 en 1 liggen.")

    if verdeling == "binomiaal":
        alpha, beta = k + 1, n - k + 1
        x, _, cdf = _betabinom_continu_cdf_grid(N_klant, alpha, beta, aantal_punten)
        aantal_fouten = float(np.interp(zekerheid, cdf, x))
        return aantal_fouten / N_klant

    elif verdeling == "poisson":
        r = k + 1
        p_succes = n / (n + N_klant)

        def cdf_func(x):
            return betainc(r, x + 1, p_succes)

        if cdf_func(0.0) >= zekerheid:
            aantal_fouten = 0.0
        elif cdf_func(N_klant) <= zekerheid:
            aantal_fouten = float(N_klant)
        else:
            aantal_fouten = brentq(lambda x: cdf_func(x) - zekerheid, 0.0, N_klant)
        return aantal_fouten / N_klant

    else:
        raise ValueError("Kies 'binomiaal' of 'poisson'")
