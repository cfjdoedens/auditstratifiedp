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
    """De exacte maximale foutfractie bij ``zekerheid`` binnen het
    samengestelde voorspellende model van het aantal fouten bij de klant —
    Beta-Binomiaal (binomiaal) resp. Negatief-Binomiaal (poisson) — zonder
    de Beta/Gamma-benadering die ``moment_match_SSO`` verder in deze module
    gebruikt. "Exact" slaat dus op het ontbreken van die benadering, niet
    op een absolute waarheid los van het model: dit model zelf steunt nog
    altijd op aannames (vlakke prior, ``N_klant`` als een exact eindige
    populatie).

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


def _kalibreer_n_eff_gelijk_k_eff_op_exacte_grens(doel_max_fout, zekerheid):
    """Spiegelbeeld van ``_kalibreer_k_eff_nul_op_exacte_grens``, voor het
    omgekeerde klemgeval (een zeer hoge SSO-foutfractie, waarbij het
    benodigde n_eff kleiner dan k_eff zou zijn). Bepaalt ``n_eff = k_eff``
    (de kleinst mogelijke ``beta``-parameter, ``n_eff - k_eff + 1 = 1``,
    binnen eval_stratified's vereiste ``n_laag >= k_laag``) zodanig dat de
    Beta(n_eff + 1, 1)-kwantiel bij ``zekerheid`` exact gelijk is aan
    ``doel_max_fout``.

    Gesloten vorm: Beta(a, 1).ppf(zekerheid) = zekerheid^(1/a) = doel, op
    te lossen naar ``a = n_eff + 1 = ln(zekerheid) / ln(doel)``. Alleen
    geldig (binnen ``a >= 1``, d.w.z. ``n_eff >= 0``) als
    ``doel_max_fout >= zekerheid``; in het zeldzame geval dat dat niet zo
    is, is de eenvoudige klem (ongewijzigde momentmatching-waarden) al
    conservatiever dan nodig en wordt die aangehouden (zie aanroeper).
    """
    a = math.log(zekerheid) / math.log(doel_max_fout)
    n_eff = a - 1.0
    return n_eff, n_eff


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
    weergeven bij een gegeven gemiddelde, kan dit bij een absoluut kleine
    N_klant resulteren in een negatieve k_eff — niet omdat N_klant klein
    is *ten opzichte van* de SSO-steekproef n, maar omdat de
    steekproefvariabiliteit van de foutfractie bij de klant zelf schaalt
    met 1/N_klant: bij een vaste (bijna-bekende) foutkans kan zelfs een
    N_klant die veel groter is dan n nog tot klemming leiden, en een
    N_klant die veel kleiner is dan n soms net niet (n bepaalt vooral hoe
    zeker de SSO-foutkans zelf al is, een secundair effect). In dat
    geval is vasthouden aan het juiste gemiddelde sowieso niet meer
    houdbaar (zie hieronder), en wordt in plaats daarvan direct
    gekalibreerd op de exacte grens: ``k_eff`` wordt op 0 gezet (geen
    fouten specifiek aan de klant toe te rekenen) en ``n_eff`` wordt zo
    gekozen dat de resulterende Beta- resp. Gamma-kwantiel bij 95%
    zekerheid exact gelijk is aan de Beta-Binomiale resp. Negatief-
    Binomiale grens (``_max_fout_exact``) — zie
    ``_kalibreer_k_eff_nul_op_exacte_grens``. Dit vervangt een eerdere
    aanpak die bij klemming vergeleek met een naïeve-poolingmethode: die
    vergelijking is overbodig zodra de werkelijke exacte grens zelf als
    ijkpunt beschikbaar is, en gaf bovendien bij een zeer kleine N_klant
    nodeloos conservatieve uitkomsten (zie ``git log`` voor de
    voorganger van deze aanpak). Een ``RuntimeWarning`` wordt afgevuurd om
    te melden dat dit is gebeurd.

    Het zeldzame omgekeerde klemgeval — een zeer hoge SSO-foutfractie (k
    dicht bij n) in combinatie met een kleine N_klant, waarbij het
    benodigde n_eff kleiner dan k_eff zou zijn — krijgt analoog dezelfde
    behandeling, maar gespiegeld: ``n_eff`` wordt op ``k_eff`` gezet (de
    kleinst mogelijke ``beta``-parameter binnen de door ``eval_stratified``
    vereiste ``n_laag >= k_laag``) en samen opgehoogd zodat de Beta(n_eff +
    1, 1)-kwantiel bij 95% zekerheid exact gelijk is aan de werkelijke
    grens (``_kalibreer_n_eff_gelijk_k_eff_op_exacte_grens``). Dit geval
    komt alleen voor bij het binomiale model: bij poisson geldt n_eff >=
    k_eff altijd (gegeven k <= n kan het benodigde gemiddelde daar nooit
    ver genoeg boven 1 uitkomen om deze klem te bereiken — algebraïsch en
    numeriek geverifieerd over een brede reeks (n, k, N_klant)), dus die
    tak behoudt voor poisson de eenvoudige klem (n_eff = k_eff) als
    defensieve terugval.

    Volledige blinde vlek bij extreem kleine N_klant: geweigerd
    -------------------------------------------------------------
    Als de exacte grens zelf al 0 is (``_max_fout_exact`` geeft
    0, wat gebeurt zodra P(0 fouten bij de klant) ≥ 95% — bij een zeer
    kleine N_klant en/of lage SSO-foutfractie), kan geen enkele continue
    verdeling nog een reëel, positief foutscenario weergeven: elk eindig,
    niet-negatief (n_eff, k_eff)-paar zou dan vrijwel 0 kans toekennen aan
    ieder foutscenario, terwijl de werkelijke kans op minstens 1 fout (hoe
    klein ook) altijd positief blijft. Dit is geen gradueel
    precisieverlies maar een volledige blinde vlek, en dus kwalitatief
    anders dan het gewone klemgeval hierboven (waarin de exacte grens
    zelf wél positief is en de kalibratie die nog altijd exact
    reproduceert). In dit geval wordt daarom geen (misleidend
    geruststellend) resultaat geretourneerd: ``moment_match_SSO`` gooit
    een ``ValueError`` die aanraadt de posten van dit type bij deze klant
    rechtstreeks (100%) te controleren in plaats van te extrapoleren.
    ``bouw_strata_SSO_klant`` vangt deze op en vuurt 'm opnieuw af met de
    naam van het type post ervoor; ``app.py`` toont 'm vervolgens als
    foutmelding (net als elke andere ``ValueError`` uit de
    gestratificeerde SSO-evaluatie).

    Het omgekeerde klemgeval (zie hierboven, alleen bij binomiaal) heeft
    een spiegelbeeldige blinde vlek: als de exacte grens zelf al 1 is
    (vrijwel zekere 100% fout), kan geen enkele continue verdeling een
    kwantiel van exact 1 weergeven (strikt begrensde drager), en wordt om
    dezelfde reden eveneens een ``ValueError`` gegooid in plaats van een
    te optimistisch resultaat.

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
        if exact_doel <= 0.0:
            # De exacte grens is hier zelf 0 (zeer kleine N_klant en/of
            # k = 0, zodat zelfs bij 95% zekerheid 0 fouten te verwachten
            # zijn). Een Beta/Gamma-verdeling heeft een strikt positieve
            # drager en kan dus nooit exact kwantiel 0 weergeven: elk
            # eindig, niet-negatief (n_eff, k_eff)-paar zou dan
            # noodzakelijkerwijs vrijwel 0 kans toekennen aan ieder
            # foutscenario, terwijl de werkelijke kans op minstens 1 fout
            # (hoe klein ook) altijd positief blijft. Dit is geen
            # gradueel precisieverlies maar een volledige blinde vlek:
            # statistische extrapolatie geeft hier helemaal geen houvast
            # meer. In plaats van toch een (misleidend geruststellend)
            # resultaat te retourneren, wordt de berekening geweigerd.
            raise ValueError(
                f"N_klant = {N_klant:g} is zo klein dat zelfs de exacte "
                "grens bij 95% zekerheid al 0 fouten aangeeft: de "
                "SSO-steekproef geeft dan geen enkel statistisch houvast "
                "meer voor dit type post bij deze klant, ook al blijft de "
                "kans op een fout (hoe klein ook) reëel. Een gekalibreerde "
                "kanskromme zou dat risico dan ten onrechte verbergen. "
                "Controleer deze posten rechtstreeks (100%) in plaats van "
                "te extrapoleren."
            )
        n_eff, k_eff = _kalibreer_k_eff_nul_op_exacte_grens(
            exact_doel, verdeling, _ZEKERHEID_VOOR_KLEMKALIBRATIE
        )
        geklemd = True
    elif n_eff < k_eff:
        # Omgekeerd klemgeval: een zeer hoge SSO-foutfractie (k dicht bij
        # n) in combinatie met een kleine N_klant. Alleen bij het
        # binomiale model komt dit voor: bij poisson geldt n_eff >= k_eff
        # altijd (het benodigde gemiddelde kan daar, gegeven k <= n,
        # nooit ver genoeg boven 1 uitkomen om deze klem te bereiken), dus
        # die tak behoudt de eenvoudige klem als defensieve terugval.
        if verdeling == "binomiaal":
            exact_doel = _max_fout_exact(n, k, N_klant, verdeling)
            if exact_doel >= 1.0:
                # Spiegelbeeld van de blinde vlek hierboven: de exacte
                # grens is hier zelf al 1 (vrijwel zekere 100% fout), en
                # geen enkele continue verdeling kan kwantiel 1 exact
                # weergeven (strikt begrensde drager). Ook hier wordt de
                # berekening geweigerd in plaats van een te optimistisch
                # resultaat te tonen.
                raise ValueError(
                    f"N_klant = {N_klant:g} is zo klein, in combinatie met "
                    "een zeer hoge SSO-foutfractie, dat zelfs de exacte "
                    "grens bij 95% zekerheid al op (vrijwel) 100% fout "
                    "uitkomt: de SSO-steekproef geeft "
                    "dan geen enkel statistisch houvast meer voor dit type "
                    "post bij deze klant. Controleer deze posten "
                    "rechtstreeks (100%) in plaats van te extrapoleren."
                )
            if exact_doel >= _ZEKERHEID_VOOR_KLEMKALIBRATIE:
                n_eff, k_eff = _kalibreer_n_eff_gelijk_k_eff_op_exacte_grens(
                    exact_doel, _ZEKERHEID_VOOR_KLEMKALIBRATIE
                )
            else:
                # Zeldzaam randgeval: de exacte grens is lager dan de
                # referentiezekerheid zelf, zodat zelfs de minst
                # geconcentreerde optie binnen deze familie (n_eff=k_eff=0)
                # al conservatiever is dan nodig. De eenvoudige klem
                # (oorspronkelijke momentmatching-waarden) volstaat dan.
                n_eff = k_eff
        else:
            n_eff = k_eff
        geklemd = True

    if geklemd:
        warnings.warn(
            "De werkelijke spreiding van de foutfractie bij de klant kon niet "
            "exact gekalibreerd worden binnen de Beta/Gamma-familie (N_klant is "
            "te klein om de steekproefvariabiliteit van de foutfractie bij de "
            "klant nog weer te geven). Het (n_eff, k_eff)-paar is in plaats "
            "daarvan gekalibreerd op de exacte "
            "Beta-Binomiale/Negatief-Binomiale grens bij 95% zekerheid.",
            RuntimeWarning,
            stacklevel=2,
        )

    return n_eff, k_eff
