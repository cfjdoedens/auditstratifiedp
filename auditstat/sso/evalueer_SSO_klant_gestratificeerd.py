from auditstat.sso.strata_SSO_klant import bouw_strata_SSO_klant
from auditstat.stratified.eval_stratified import eval_stratified


def evalueer_SSO_klant_gestratificeerd(
    post_typen,
    model="binomiaal",
    zekerheid=0.95,
    methode="FFT samen",
    granulariteit=None,
    kalibratiemethode="momentmatching",
):
    """
    Evalueert een klant gestratificeerd (één stratum per type post), op
    basis van SSO-steekproeven per type post.

    Bouwt eerst de stratatabel via ``bouw_strata_SSO_klant`` en roept
    daarna ``eval_stratified`` aan. Zie ``bouw_strata_SSO_klant`` voor het
    formaat van ``post_typen``, en ``eval_stratified`` voor de overige
    parameters en het resultaatformaat.

    Per type post wordt een effectieve steekproefomvang en een effectief
    aantal fouten bij de klant gekalibreerd via ``moment_match_SSO``
    (gemiddelde- en variantie-matching op het ``model``-kansmodel), zodat
    de gestratificeerde evaluatie zowel het juiste gemiddelde als (voor
    zover mogelijk binnen de Beta/Gamma-familie) de juiste variantie van
    de werkelijke, continue exacte SSO-onzekerheid draagt — zie
    ``bouw_strata_SSO_klant`` en ``moment_match_SSO`` voor de details.

    Parameters
    ----------
    post_typen : list[dict]
        Zie ``bouw_strata_SSO_klant``.
    model : {"binomiaal", "poisson"}
        Kansmodel voor de gestratificeerde convolutieberekening.
    zekerheid : float
        Gewenste statistische zekerheid, tussen 0 en 1.
    methode : {"FFT paarsgewijs", "FFT samen", "direct", "Monte Carlo"}
        Methode voor de convolutieberekening.
    granulariteit : int, optioneel
        Zie ``eval_stratified``; standaard ``None`` (automatisch bepaald).
    kalibratiemethode : {"momentmatching", "naief"}, standaard "momentmatching"
        Zie ``bouw_strata_SSO_klant``.

    Returns
    -------
    dict
        Het resultaat van ``eval_stratified``, inclusief de kanskromme
        (bruikbaar met ``auditstat.stratified.plot_kanskromme.plot_kanskromme``)
        en de opgebouwde stratatabel onder ``"steekproeven"``.
    """
    steekproeven = bouw_strata_SSO_klant(
        post_typen, model=model, kalibratiemethode=kalibratiemethode
    )
    return eval_stratified(
        steekproeven=steekproeven,
        model=model,
        zekerheid=zekerheid,
        methode=methode,
        granulariteit=granulariteit,
    )
