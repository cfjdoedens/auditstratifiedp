import numpy as np
from scipy.special import comb
from scipy.stats import poisson


def _posterior_theta_klant_binomiaal(n, k, f, theta_grid):
    """Niet-genormaliseerde posterior-dichtheid van theta_klant (binomiaal).

    Model: n_X (het aantal van de n SSO-brede steekproefposten dat bij
    klant X hoort) ~ Binomiaal(n, f). Klant X heeft een eigen, van de
    rest van de SSO-populatie onafhankelijke foutkans theta_klant met
    vlakke Beta(1, 1)-prior; de rest van de SSO-populatie heeft een
    eigen, eveneens vlakke Beta(1, 1)-prior op theta_rest. Alleen de
    som k = k_X + k_rest wordt waargenomen, niet de opsplitsing.

    Omdat een Beta-Binomiaal-marginale verdeling met vlakke prior
    discreet uniform is (P(l | m) = 1 / (m + 1)), marginaliseert
    theta_rest weg tot een constante gewichtsfactor per (n_X, k_X)-
    combinatie. Wat overblijft is een eindige dubbele som die hieronder
    direct wordt opgeteld.
    """
    post = np.zeros_like(theta_grid, dtype=float)
    m_waarden = np.arange(0, n + 1)
    gewicht_m = comb(n, m_waarden) * f**m_waarden * (1 - f) ** (n - m_waarden)
    for m, w_m in zip(m_waarden, gewicht_m, strict=False):
        if w_m == 0.0:
            continue
        marginaal_rest = 1.0 / (n - m + 1)
        j_min = max(0, k - (n - m))
        j_max = min(m, k)
        if j_min > j_max:
            continue
        bijdrage = np.zeros_like(theta_grid)
        for j in range(j_min, j_max + 1):
            bijdrage += comb(m, j) * theta_grid**j * (1 - theta_grid) ** (m - j)
        post += w_m * marginaal_rest * bijdrage
    return post


def _posterior_theta_klant_poisson(n, k, f, theta_grid):
    """Niet-genormaliseerde posterior-dichtheid van theta_klant (poisson).

    Analoge constructie als bij _posterior_theta_klant_binomiaal, maar
    met een Poisson/Gamma-model in plaats van Binomiaal/Beta: n_X ~
    Binomiaal(n, f) (de opsplitsing van de steekproef over klant en
    rest is een eigenschap van het steekproefontwerp en verandert niet
    met het foutmodel), en gegeven n_X = m, k_X | theta_klant ~
    Poisson(m * theta_klant) met vlakke (oneigenlijke) prior op
    theta_klant; analoog voor de rest met expositie n - m.

    Een vlakke prior op een Poisson-snelheid marginaliseert tot een
    (oneigenlijke, maar voor elk vast expositieaantal constante)
    gewicht 1 / (n - m) voor elk mogelijk aantal fouten in de rest. Bij
    n_X = n is er geen rest-expositie: dan ligt k_X = k vast en is er
    geen marginalisatie nodig.
    """
    post = np.zeros_like(theta_grid, dtype=float)
    m_waarden = np.arange(0, n + 1)
    gewicht_m = comb(n, m_waarden) * f**m_waarden * (1 - f) ** (n - m_waarden)
    for m, w_m in zip(m_waarden, gewicht_m, strict=False):
        if w_m == 0.0:
            continue
        if m == n:
            bijdrage = poisson.pmf(k, mu=m * theta_grid)
        else:
            marginaal_rest = 1.0 / (n - m)
            bijdrage = np.zeros_like(theta_grid)
            for j in range(0, k + 1):
                bijdrage += poisson.pmf(j, mu=m * theta_grid)
            bijdrage = marginaal_rest * bijdrage
        post += w_m * bijdrage
    return post


def _kwantiel_van_theta_posterior(theta_grid, dichtheid, p):
    """Kwantiel van een dichtheid gegeven op een vast grid, via lineaire
    interpolatie van de (genormaliseerde) cumulatieve verdeling."""
    cdf = np.concatenate((
        [0.0],
        np.cumsum((dichtheid[1:] + dichtheid[:-1]) / 2 * np.diff(theta_grid)),
    ))
    cdf = cdf / cdf[-1]
    return float(np.interp(p, cdf, theta_grid))


def max_fout_heterogeen_SSO(
    n, k, f, zekerheid=0.95, verdeling="binomiaal", aantal_theta=4001
):
    """
    Berekent de maximale foutfractie bij een SSO-klant onder een
    heterogeniteitsmodel: klant X heeft een eigen, van de rest van de
    SSO-populatie onafhankelijke foutkans, in plaats van de impliciete
    aanname van max_fout_exact_SSO / max_fout_exact_continu_SSO dat
    elke post (van elke klant) verwisselbaar is met dezelfde,
    SSO-brede foutkans (de "uitwisselbare" aanname).

    Alleen de relatieve omvang van klant X binnen de totale
    SSO-populatie is nodig (f = N_klant / N_totaal), niet N_klant of
    N_totaal afzonderlijk: de totale SSO-populatie wordt verondersteld
    zeer groot (effectief oneindig) te zijn, zowel in aantal posten als
    in waarde, zodat trekken van de steekproef de populatie niet
    noemenswaardig uitput. Onder diezelfde aanname convergeert de
    werkelijke foutfractie bij klant X (die zelf ook een grote
    populatie heeft) naar zijn eigen foutkans theta_klant; het
    teruggegeven kwantiel is dus het kwantiel van de posterior van
    theta_klant zelf, niet van een voorspellende telverdeling over een
    eindige N_klant.

    Model
    -----
    Van de n SSO-brede steekproefposten horen er n_X ~ Binomiaal(n, f)
    toevallig bij klant X. Klant X heeft een eigen vlakke prior op zijn
    foutkans theta_klant, onafhankelijk van de (eveneens vlakke) prior
    op de foutkans van de rest van de SSO-populatie. Alleen de totale
    som k = k_X + k_rest wordt waargenomen; de posterior van
    theta_klant marginaliseert over alle mogelijke opsplitsingen.

    Grenswaarden: bij f = 1 (alle steekproefposten horen bij klant X)
    komt dit exact overeen met het bestaande uitwisselbare model
    (Beta(k + 1, n - k + 1) resp. Gamma(k + 1, n), het laatste
    getrunceerd naar [0, 1]). Bij f = 0 bevat de SSO-brede steekproef
    geen informatie over klant X en blijft de posterior gelijk aan de
    vlakke prior (uniform op [0, 1]).

    Parameters
    ----------
    n, k : int
        Omvang en aantal fouten in de SSO-brede steekproef.
    f : float
        Relatieve omvang van klant X binnen de totale SSO-populatie
        (N_klant / N_totaal), tussen 0 en 1.
    zekerheid : float, standaard 0.95
        Gewenste statistische zekerheid.
    verdeling : {"binomiaal", "poisson"}, standaard "binomiaal"
    aantal_theta : int, standaard 4001
        Resolutie van het grid voor theta_klant op [0, 1].

    Returns
    -------
    float
        Maximale foutfractie bij klant X bij de gekozen zekerheid,
        onder het heterogeniteitsmodel.
    """
    if not isinstance(n, (int, np.integer)) or n <= 0:
        raise ValueError("n moet een positief geheel getal zijn.")
    if not isinstance(k, (int, np.integer)) or k < 0:
        raise ValueError("k moet een niet-negatief geheel getal zijn.")
    if k > n:
        raise ValueError("k mag niet groter zijn dan n.")
    if not (0 <= f <= 1):
        raise ValueError("f moet tussen 0 en 1 liggen.")
    if not (0 < zekerheid < 1):
        raise ValueError("zekerheid moet tussen 0 en 1 liggen.")

    theta_grid = np.linspace(0.0, 1.0, aantal_theta)

    if verdeling == "binomiaal":
        dichtheid = _posterior_theta_klant_binomiaal(n, k, f, theta_grid)
    elif verdeling == "poisson":
        dichtheid = _posterior_theta_klant_poisson(n, k, f, theta_grid)
    else:
        raise ValueError("Kies 'binomiaal' of 'poisson'")

    return _kwantiel_van_theta_posterior(theta_grid, dichtheid, zekerheid)
