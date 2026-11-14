import warnings

import pandas as pd

from auditstat.geldsteek_gestratificeerd.utils import foutloze_posten_equivalent
from auditstat.sso.moment_match_SSO import moment_match_SSO
from auditstat.sso.naief_SSO import naief_match_SSO

# Optionele kolommen die, indien aanwezig, worden doorgegeven aan
# evalueer_geldsteek_gestratificeerd (dat zelf standaardwaarden invult als ze ontbreken).
# ``ihr``, ``ibr``, ``car`` en ``materialiteit`` horen bij de eerste trap
# (de SSO-steekproef) en worden hier al verwerkt; ze worden niet doorgegeven,
# anders zou evalueer_geldsteek_gestratificeerd de correctie nogmaals op de klant toepassen.
_OPTIONELE_KOLOMMEN = (
    "waarde_hoog",
    "fout_hoog",
)


def bouw_strata_SSO_klant(
    post_typen,
    model="binomiaal",
    kalibratiemethode="momentmatching",
    zekerheid=0.95,
):
    """
    Bouwt een stratatabel voor één klant op basis van SSO-steekproeven per
    type post, geschikt als invoer voor ``auditstat.geldsteek_gestratificeerd.evalueer_geldsteek_gestratificeerd``.

    Achtergrond
    -----------
    Verschillende klanten maken in verschillende mate gebruik van diverse
    typen posten (bijv. emolumenten, inkoopfacturen) die door een SSO
    worden verwerkt. Per type post is er een steekproef bij de SSO
    beschikbaar (``n``, ``k``), en is bekend hoeveel posten van dat type de
    klant zelf heeft (``N_klant``). Deze functie kalibreert per type post
    een effectieve steekproefomvang en een effectief aantal fouten bij de
    klant (zie ``moment_match_SSO``) en zet dat om in een stratum. Zo kan
    de klant gestratificeerd worden geëvalueerd: één stratum per type
    post.

    ``moment_match_SSO`` kalibreert (n_eff, k_eff) zodanig dat de Beta-
    resp. Gamma-verdeling die ``evalueer_geldsteek_gestratificeerd`` hieruit opbouwt dezelfde
    gemiddelde én variantie heeft als de werkelijke, continue samengestelde
    verdeling van de foutfractie bij de klant. Dat behoudt beide
    onzekerheidslagen (posterior-onzekerheid over de ware foutkans, én
    steekproefvariabiliteit van die foutkans bij de klant) voor zover dat
    binnen een enkele Beta/Gamma-verdeling mogelijk is.

    Parameters
    ----------
    post_typen : list[dict]
        Eén dict per type post (= stratum), met verplichte sleutels:

        - ``naam`` (str): naam van het type post, bijv. "Emolumenten".
        - ``n`` (int): steekproefomvang bij de SSO voor dit type post.
        - ``k`` (int): aantal fouten in de SSO-steekproef voor dit type post.
        - ``N_klant`` (int): aantal posten van dit type bij de klant.
        - ``waarde_laag`` (float): totale geldwaarde van dit type post bij
          de klant.

        Optioneel: ``cv`` (variatiecoëfficiënt van de postgroottes van dit
        type post, standaard 0; niveau 2/3 van de theorie, zie
        ``naief_match_SSO`` en ``moment_match_SSO``).

        Optioneel (standaardwaarden conform ``evalueer_geldsteek_gestratificeerd`` als ze
        ontbreken): ``ihr``, ``ibr``, ``car``, ``waarde_hoog``,
        ``fout_hoog``, ``materialiteit``.

        ``ihr``, ``ibr``, ``car`` en ``materialiteit`` horen bij de eerste
        trap, de SSO-steekproef. Het daarmee overeenkomende aantal
        foutloze posten (``foutloze_posten_equivalent``) wordt eerst bij de
        SSO-``n`` opgeteld (``n + extra``, ``k`` blijft); daaruit wordt dan
        (n_eff, k_eff) voor de klant gekalibreerd. De klantsteekproef zelf
        kent geen risicocorrectie, dus deze kolommen worden niet aan
        ``evalueer_geldsteek_gestratificeerd`` doorgegeven (dat zou de correctie dubbel
        toepassen, op ``n_eff``).
    model : {"binomiaal", "poisson"}, standaard "binomiaal"
        Kansmodel waarop gekalibreerd wordt. Moet overeenkomen met het
        ``model``-argument dat straks aan ``evalueer_geldsteek_gestratificeerd`` wordt
        doorgegeven (zie ``evalueer_SSO_klant_gestratificeerd``).
    kalibratiemethode : {"momentmatching", "naief"}, standaard "momentmatching"
        Welke functie per type post (n_eff, k_eff) berekent:

        - ``"momentmatching"``: ``moment_match_SSO`` (scherper maar
          complexer; matcht gemiddelde én variantie van de werkelijke
          compound-verdeling).
        - ``"naief"``: ``naief_match_SSO`` (eenvoudige poolingformule, eerste-orde variantie-matching,
          meestal conservatiever; zie die functie voor de onderbouwing en
          de beperkingen ervan).

        De waarschuwings-/foutafhandeling bij klemming resp. een
        volledige blinde vlek (zie hieronder) is alleen van toepassing op
        ``"momentmatching"``; ``"naief"`` kent dat onderscheid niet.

    zekerheid : float, standaard 0,95
        Zekerheidsniveau waarop ``moment_match_SSO`` bij klemming op de
        exacte grens kalibreert. Geef hier dezelfde zekerheid door als aan
        ``evalueer_geldsteek_gestratificeerd`` (``evalueer_SSO_klant_gestratificeerd`` doet
        dat automatisch). Heeft geen invloed bij ``"naief"`` en bij
        momentmatching zonder klemming.

    Returns
    -------
    pandas.DataFrame
        Eén rij per type post, met kolommen ``naam``, ``waarde_laag``,
        ``n_laag``, ``k_laag`` en de eventueel meegegeven optionele
        kolommen — rechtstreeks bruikbaar als ``steekproeven``-argument
        van ``evalueer_geldsteek_gestratificeerd``.

    Let op
    ------
    ``evalueer_geldsteek_gestratificeerd`` accepteert een niet-geheel ``n_laag`` (het rekent met
    Beta-/Gamma-verdelingen), dus (n_eff, k_eff) worden ongeafgerond
    doorgegeven; afronden zou de gekalibreerde variantie en het gemiddelde
    verstoren. ``n_laag`` is minstens ``k_laag`` (eis van ``evalueer_geldsteek_gestratificeerd``).

    Als ``moment_match_SSO`` voor een type post moet klemmen, vuurt die
    functie een ``RuntimeWarning`` af; deze functie vangt die op en vuurt
    'm opnieuw af met de naam van het type post ervoor (``"Type post
    '<naam>': ..."``), zodat een aanroeper per type post kan tonen voor
    welke een terugval is toegepast.

    Bij een volledige blinde vlek (N_klant zo klein dat zelfs de exacte
    grens bij de gekozen zekerheid al 0 is) weigert ``moment_match_SSO`` in plaats daarvan een
    resultaat te geven en gooit een ``ValueError``. Deze functie vangt die
    op en gooit 'm opnieuw met de naam van het type post ervoor, zodat de
    hele gestratificeerde evaluatie voor deze klant stopt in plaats van
    een (misleidend geruststellend) resultaat op te leveren.
    """
    if not post_typen:
        raise ValueError("Geef tenminste 1 type post (stratum) mee.")
    if kalibratiemethode not in ("momentmatching", "naief"):
        raise ValueError(
            "kalibratiemethode moet 'momentmatching' of 'naief' zijn, "
            f"kreeg {kalibratiemethode!r}."
        )

    rijen = []
    for post in post_typen:
        naam = post.get("naam")
        if not naam or not str(naam).strip():
            raise ValueError("Elk type post moet een niet-lege 'naam' hebben.")

        ontbrekend = [
            veld for veld in ("n", "k", "N_klant", "waarde_laag") if veld not in post
        ]
        if ontbrekend:
            raise ValueError(
                f"Type post '{naam}' mist verplicht(e) veld(en): {', '.join(ontbrekend)}."
            )

        try:
            extra = float(
                foutloze_posten_equivalent(
                    post.get("ihr", "H"),
                    post.get("ibr", "H"),
                    post.get("car", "H"),
                    post.get("materialiteit", 0.01),
                )
            )
        except ValueError as e:
            raise ValueError(f"Type post '{naam}': {e}") from e
        n_sso = post["n"] + extra
        cv = post.get("cv", 0.0)
        if cv is None or not cv >= 0 or cv == float("inf"):
            raise ValueError(f"Type post '{naam}': cv moet een eindig getal >= 0 zijn.")

        if kalibratiemethode == "naief":
            n_eff, k_eff = naief_match_SSO(n_sso, post["k"], post["N_klant"], cv=cv)
        else:
            # moment_match_SSO vuurt bij klemming een RuntimeWarning af
            # zonder te weten bij welk type post (naam) dat hoort. Die
            # context voegen we hier toe, zodat een aanroeper (bijv. de
            # SSO-tab in app.py) per type post kan tonen voor welke een
            # terugval is toegepast.
            try:
                with warnings.catch_warnings(record=True) as gevangen:
                    warnings.simplefilter("always", RuntimeWarning)
                    n_eff, k_eff = moment_match_SSO(
                        n_sso,
                        post["k"],
                        post["N_klant"],
                        verdeling=model,
                        zekerheid=zekerheid,
                        cv=cv,
                    )
            except ValueError as e:
                # Zie moment_match_SSO: bij een volledige blinde vlek
                # (N_klant zo klein dat zelfs de exacte grens al 0 is)
                # weigert die functie een resultaat te geven. Die
                # ValueError kent de naam van het type post niet; die
                # context voegen we hier toe.
                raise ValueError(f"Type post '{naam}': {e}") from e
            for w in gevangen:
                warnings.warn(
                    f"Type post '{naam}': {w.message}", RuntimeWarning, stacklevel=2
                )
        n_laag = max(n_eff, k_eff)

        rij = {
            "naam": naam,
            "waarde_laag": post["waarde_laag"],
            "n_laag": n_laag,
            "k_laag": k_eff,
            "extra_foutloze_posten_sso": extra,
        }
        for optioneel in _OPTIONELE_KOLOMMEN:
            if optioneel in post:
                rij[optioneel] = post[optioneel]

        rijen.append(rij)

    return pd.DataFrame(rijen)
