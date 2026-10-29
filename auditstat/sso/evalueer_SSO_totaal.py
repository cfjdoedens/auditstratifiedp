import pandas as pd

from auditstat.stratified.eval_stratified import eval_stratified

_OPTIONELE_KOLOMMEN = (
    "ihr",
    "ibr",
    "car",
    "waarde_hoog",
    "fout_hoog",
    "materialiteit",
)


def _als_geheel(waarde, naam, veld):
    """Zet een geheel getal (ook als float, bijv. 200.0) om naar int."""
    try:
        als_int = int(waarde)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"Type post '{naam}': veld '{veld}' ({waarde!r}) is geen geheel getal."
        ) from e
    if als_int != waarde:
        raise ValueError(
            f"Type post '{naam}': veld '{veld}' ({waarde!r}) is geen geheel getal."
        )
    return als_int


def evalueer_SSO_totaal(
    post_typen,
    model="binomiaal",
    zekerheid=0.95,
    methode="FFT samen",
    granulariteit=None,
):
    """
    Evalueert de hele SSO-populatie (niet één klant) op basis van de
    SSO-brede steekproef.

    Er is hier geen tweede trap en dus geen kalibratie: de SSO-steekproef
    ``(n, k)`` is direct een steekproef uit de populatie waarover
    geoordeeld wordt. Elk type post wordt daarom één stratum met
    ``n_laag = n`` en ``k_laag = k`` over de totale geldwaarde van dat type
    post bij de hele SSO; ``eval_stratified`` combineert de strata.

    Parameters
    ----------
    post_typen : list[dict]
        Eén dict per type post (= stratum), met verplichte sleutels
        ``naam``, ``n`` (geheel), ``k`` (mag niet-geheel zijn, bijv. een gewogen foutaantal bij een geldsteekproef) en ``waarde_laag`` (totale
        geldwaarde van dit type post bij de hele SSO). Optioneel: ``ihr``,
        ``ibr``, ``car``, ``waarde_hoog``, ``fout_hoog``, ``materialiteit``.
        Zonder onderscheid naar typen posten is dit één dict met de
        SSO-brede totalen.
    model, zekerheid, methode, granulariteit
        Zie ``eval_stratified``.

    Returns
    -------
    dict
        Het resultaat van ``eval_stratified`` (bruikbaar met
        ``plot_kanskromme``), met de stratatabel onder ``"steekproeven"``.
    """
    if not post_typen:
        raise ValueError("Geef tenminste 1 type post (stratum) mee.")

    rijen = []
    for post in post_typen:
        naam = post.get("naam")
        if not naam or not str(naam).strip():
            raise ValueError("Elk type post moet een niet-lege 'naam' hebben.")
        ontbrekend = [v for v in ("n", "k", "waarde_laag") if v not in post]
        if ontbrekend:
            raise ValueError(
                f"Type post '{naam}' mist verplicht(e) veld(en): {', '.join(ontbrekend)}."
            )
        rij = {
            "naam": naam,
            "waarde_laag": post["waarde_laag"],
            "n_laag": _als_geheel(post["n"], naam, "n"),
            "k_laag": post["k"],
        }
        for optioneel in _OPTIONELE_KOLOMMEN:
            if optioneel in post:
                rij[optioneel] = post[optioneel]
        rijen.append(rij)

    return eval_stratified(
        steekproeven=pd.DataFrame(rijen),
        model=model,
        zekerheid=zekerheid,
        methode=methode,
        granulariteit=granulariteit,
    )
