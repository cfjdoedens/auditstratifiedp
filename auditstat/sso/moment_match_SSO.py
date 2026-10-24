import math
import warnings

from scipy.stats import betabinom, nbinom

# Referentiezekerheid waarop, uitsluitend bij klemming (k_eff < 0), het
# vervangende (n_eff, k_eff)-paar wordt gekalibreerd op de werkelijke,
# exacte Beta-Binomiale/Negatief-Binomiale grens. Dit is noodzakelijkerwijs
# een vaste keuze: moment_match_SSO kent de uiteindelijke, door de
# gebruiker gekozen zekerheid van eval_stratified niet (die wordt pas later
# toegepast).
_ZEKERHEID_VOOR_KLEMKALIBRATIE = 0.95


def _max_fout_exact(n, k, N_klant, verdeling, zekerheid=_ZEKERHEID_VOOR_KLEMKALIBRATIE):
    """De werkelijke, exacte maximale foutfractie bij ``zekerheid``, op basis
    van de volledige samengestelde voorspellende verdeling van het aantal
    fouten bij de klant — Beta-Binomiaal (binomiaal) resp. Negatief-Binomiaal
    (poisson) — zonder de Beta/Gamma-benadering die ``moment_match_SSO``
    verder in deze module gebruikt.

    Dit is per definitie discreet (``N_klant`` is hier een eindig aantal
    posten), en daarom uitsluitend bedoeld als intern ijkpunt bij klemming
    — niet als gebruikersgerichte uitkomst. Zie ``AGENTS.md`` onder
    "Item-count-gebaseerd SSO-pad: verwijderd" voor de achtergrond waarom
    dit soort getrapte, exacte berekening niet rechtstreeks aan gebruikers
    wordt getoond.
    """
    if verdeling == "binomiaal":
        x = betabinom.ppf(zekerheid, N_klant, k + 1, n - k + 1)
    else:
        x = nbinom.ppf(zekerheid, k + 1, n / (n + N_klant))
    return x / N_klant


def _kalibreer_k_eff_nul_op_exacte_grens(doel_max_fout, verdeling, zekerheid):
    """Bepaalt ``n_eff`` bij vastgehouden ``k_eff = 0`` zodanig dat de
    Beta(1, n_eff + 1)- resp. Gamma(1, schaal=1/n_eff)-kwantiel bij
    ``zekerheid`` exact gelijk is aan ``doel_max_fout``.

    Dit heeft een gesloten vorm:

    - Binomiaal: Beta(1, b).ppf(zekerheid) = 1 − (1 − zekerheid)^(1/b), op
      te lossen naar ``b = n_eff + 1``.
    - Poisson: Gamma(1, schaal=1/n_eff) is een Exponentiële verdeling met
      rate ``n_eff``; de ppf daarvan is eenvoudig naar ``n_eff`` te
      herleiden.

    Bij een zeer kleine ``N_klant`` kan ``doel_max_fout`` zelf hoger liggen
    dan wat deze (binomiale) familie ooit kan weergeven, ongeacht ``n_eff``
    (het maximum wordt bereikt bij ``n_eff = 0``, d.w.z. een uniforme
    verdeling, met kwantiel gelijk aan ``zekerheid`` zelf). In dat geval
    wordt ``n_eff = 0`` aangehouden als beste, nog altijd geldige, keuze.
    """
    if verdeling == "binomiaal":
        if doel_max_fout >= zekerheid:
            n_eff = 0.0
        else:
            b = math.log(1.0 - zekerheid) / math.log(1.0 - doel_max_fout)
            n_eff = max(b - 1.0, 0.0)
    else:
        n_eff = -math.log(1.0 - zekerheid) / doel_max_fout
    return n_eff, 0.0


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
    weergeven bij een gegeven gemiddelde, kan dit bij een kleine N_klant
    (t.o.v. de SSO-steekproef) resulteren in een negatieve k_eff. In dat
    geval is vasthouden aan het juiste gemiddelde sowieso niet meer
    houdbaar (zie hieronder), en wordt in plaats daarvan direct
    gekalibreerd op de werkelijke, exacte grens: ``k_eff`` wordt op 0
    gezet (geen fouten specifiek aan de klant toe te rekenen) en ``n_eff``
    wordt zo gekozen dat de resulterende Beta- resp. Gamma-kwantiel bij
    95% zekerheid exact gelijk is aan de werkelijke Beta-Binomiale resp.
    Negatief-Binomiale grens (``_max_fout_exact``) — zie
    ``_kalibreer_k_eff_nul_op_exacte_grens``. Dit vervangt een eerdere
    aanpak die bij klemming vergeleek met een naïeve-poolingmethode: die
    vergelijking is overbodig zodra de werkelijke exacte grens zelf als
    ijkpunt beschikbaar is, en gaf bovendien bij een zeer kleine N_klant
    nodeloos conservatieve uitkomsten (zie ``git log`` voor de
    voorganger van deze aanpak). Een ``RuntimeWarning`` wordt afgevuurd om
    te melden dat dit is gebeurd.

    Deze exacte kalibratie geldt alleen voor de (in de praktijk verreweg
    meest voorkomende) situatie waarin het benodigde k_eff negatief zou
    zijn. Het zeldzame omgekeerde geval (een zeer hoge SSO-foutfractie,
    waarbij het benodigde n_eff kleiner dan k_eff zou zijn) wordt nog
    steeds simpelweg geklemd op n_eff = k_eff, zonder deze exacte-grens-
    kalibratie.

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
        exact_doel = _max_fout_exact(n, k, N_klant, verdeling)
        n_eff, k_eff = _kalibreer_k_eff_nul_op_exacte_grens(
            exact_doel, verdeling, _ZEKERHEID_VOOR_KLEMKALIBRATIE
        )
        geklemd = True
    if n_eff < k_eff:
        n_eff = k_eff
        geklemd = True

    if geklemd:
        warnings.warn(
            "De werkelijke spreiding van de foutfractie bij de klant kon niet "
            "exact gekalibreerd worden binnen de Beta/Gamma-familie (N_klant is "
            "klein t.o.v. de SSO-steekproef n). Het (n_eff, k_eff)-paar is in "
            "plaats daarvan gekalibreerd op de werkelijke, exacte "
            "Beta-Binomiale/Negatief-Binomiale grens bij 95% zekerheid.",
            RuntimeWarning,
            stacklevel=2,
        )

    return n_eff, k_eff
