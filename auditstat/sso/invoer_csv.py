"""CSV-uitwisseling van de SSO-invoer (instellingen, totalen, klanten, typen posten).

Alle SSO-invoer past in één CSV-bestand in lang formaat, met `;` als
scheidingsteken en getallen in Nederlandse notatie (punt als
duizendtalscheiding, komma als decimaalteken) -- precies zoals de
invoervelden in de app ze tonen, zodat het bestand direct in een
Nederlandse Excel opent en een export/import-ronde de invoer ongewijzigd
laat.

Kolommen: ``onderdeel;klant;type_post;veld;waarde``

=================== ======== ========= ================================================
onderdeel           klant    type_post veld
=================== ======== ========= ================================================
``instelling``      leeg     leeg      model, zekerheid, berekeningsmethode, onderscheid
``totaal``          leeg     leeg      n, k, N_totaal, massa, ihr, ibr, car, materialiteit
``klant``           ingevuld leeg      N_klant, waarde_laag
``type_post``       leeg     ingevuld  n, k, ihr, ibr, car, materialiteit
``klant_type_post`` ingevuld ingevuld  N_klant, waarde_laag
=================== ======== ========= ================================================

``materialiteit`` mag leeg zijn (standaardwaarde van de app); alle andere
velden zijn verplicht zodra de bijbehorende klant/post/het totaal voorkomt.
"""

from __future__ import annotations

import csv
import io
import re

import pandas as pd

KOLOMMEN = ("onderdeel", "klant", "type_post", "veld", "waarde")

_RISICO = ("H", "M", "L")

# Strikte NL-notatie: optioneel duizendtalgroepen van precies drie cijfers
# met een punt ("1.234.567"), optioneel een decimaaldeel met komma. Dit
# weigert bewust "1234.56" (punt-decimaal), want dat zou door de
# NL-parser van de app stilzwijgend als 123456 worden gelezen.
_NL_GETAL = re.compile(r"^(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")

_INSTELLING_VELDEN = {
    "model": ("binomiaal", "poisson"),
    "zekerheid": "getal",
    "berekeningsmethode": ("momentmatching", "naief"),
    "onderscheid": ("nee", "ja"),
}
_TOTAAL_VELDEN = {
    "n": "getal",
    "k": "getal",
    "N_totaal": "getal",
    "massa": "getal",
    "ihr": _RISICO,
    "ibr": _RISICO,
    "car": _RISICO,
    "materialiteit": "getal_optioneel",
}
_KLANT_VELDEN = {"N_klant": "getal", "waarde_laag": "getal"}
_TYPE_POST_VELDEN = {
    "n": "getal",
    "k": "getal",
    "ihr": _RISICO,
    "ibr": _RISICO,
    "car": _RISICO,
    "materialiteit": "getal_optioneel",
}

# onderdeel -> (velden, klant ingevuld?, type_post ingevuld?)
_ONDERDELEN = {
    "instelling": (_INSTELLING_VELDEN, False, False),
    "totaal": (_TOTAAL_VELDEN, False, False),
    "klant": (_KLANT_VELDEN, True, False),
    "type_post": (_TYPE_POST_VELDEN, False, True),
    "klant_type_post": (_KLANT_VELDEN, True, True),
}

_KLANTEN_KOLOMMEN = ["klant", "N_klant", "waarde_laag"]
_TYPEN_POSTEN_KOLOMMEN = ["naam", "n", "k", "ihr", "ibr", "car", "materialiteit"]
_KLANTEN_TYPEN_KOLOMMEN = ["klant", "type_post", "N_klant", "waarde_laag"]


def _tekst(cel) -> str:
    """Celwaarde als nette string; None/NaN worden een lege string."""
    if cel is None or (not isinstance(cel, str) and pd.isna(cel)):
        return ""
    return str(cel).strip()


def maak_sso_invoer_csv(
    instellingen: dict[str, str],
    totaal: dict[str, str],
    klanten: pd.DataFrame,
    typen_posten: pd.DataFrame,
    klanten_typen: pd.DataFrame,
) -> str:
    """Zet de SSO-invoer om naar CSV-tekst (lang formaat, `;`, NL-getallen).

    Parameters
    ----------
    instellingen : dict
        Sleutels ``model``, ``zekerheid``, ``berekeningsmethode``,
        ``onderscheid``.
    totaal : dict
        Sleutels ``n``, ``k``, ``N_totaal``, ``massa``, ``ihr``, ``ibr``,
        ``car``, ``materialiteit``.
    klanten : DataFrame
        Kolommen ``klant``, ``N_klant``, ``waarde_laag``.
    typen_posten : DataFrame
        Kolommen ``naam``, ``n``, ``k``, ``ihr``, ``ibr``, ``car``,
        ``materialiteit``.
    klanten_typen : DataFrame
        Kolommen ``klant``, ``type_post``, ``N_klant``, ``waarde_laag``.

    De waarden worden ongewijzigd (als tekst) weggeschreven; rijen zonder
    naam (lege tabelrijen) worden overgeslagen.
    """
    uit = io.StringIO()
    schrijver = csv.writer(uit, delimiter=";", lineterminator="\n")
    schrijver.writerow(KOLOMMEN)

    for veld in _INSTELLING_VELDEN:
        schrijver.writerow(["instelling", "", "", veld, _tekst(instellingen.get(veld))])
    for veld in _TOTAAL_VELDEN:
        schrijver.writerow(["totaal", "", "", veld, _tekst(totaal.get(veld))])

    for _, rij in klanten.iterrows():
        klant = _tekst(rij.get("klant"))
        if not klant:
            continue
        for veld in _KLANT_VELDEN:
            schrijver.writerow(["klant", klant, "", veld, _tekst(rij.get(veld))])

    for _, rij in typen_posten.iterrows():
        naam = _tekst(rij.get("naam"))
        if not naam:
            continue
        for veld in _TYPE_POST_VELDEN:
            schrijver.writerow(["type_post", "", naam, veld, _tekst(rij.get(veld))])

    for _, rij in klanten_typen.iterrows():
        klant = _tekst(rij.get("klant"))
        type_post = _tekst(rij.get("type_post"))
        if not klant or not type_post:
            continue
        for veld in _KLANT_VELDEN:
            schrijver.writerow([
                "klant_type_post",
                klant,
                type_post,
                veld,
                _tekst(rij.get(veld)),
            ])

    return uit.getvalue()


def _label(onderdeel: str, klant: str, type_post: str) -> str:
    """Leesbaar label voor een regel in foutmeldingen."""
    delen = [x for x in (klant, type_post) if x]
    return f'{onderdeel} "{" / ".join(delen)}"' if delen else onderdeel


def _controleer_waarde(soort, waarde: str) -> str | None:
    """Geef een foutomschrijving, of None als de waarde geldig is."""
    if soort == "getal_optioneel" and waarde == "":
        return None
    if waarde == "":
        return "waarde ontbreekt"
    if soort in ("getal", "getal_optioneel"):
        if not _NL_GETAL.match(waarde):
            return (
                f'"{waarde}" is geen geldig getal in Nederlandse notatie '
                "(punt als duizendtalscheiding, komma als decimaalteken)"
            )
        return None
    if waarde not in soort:
        return f'"{waarde}" is ongeldig; toegestaan: {", ".join(soort)}'
    return None


def lees_sso_invoer_csv(inhoud: str | bytes) -> dict:
    """Lees een SSO-invoer-CSV (zie moduledocstring) strikt in en valideer.

    Geeft een dict terug met de sleutels:

    - ``instellingen``: dict met de in het bestand aanwezige instellingen
    - ``totaal``: dict met de in het bestand aanwezige totaalvelden
    - ``klanten``: DataFrame (``klant``, ``N_klant``, ``waarde_laag``) of None
    - ``typen_posten``: DataFrame (``naam``, ``n``, ... ) of None
    - ``klanten_typen``: DataFrame (``klant``, ``type_post``, ``N_klant``,
      ``waarde_laag``) of None

    Onderdelen die niet in het bestand voorkomen krijgen None (resp. een
    leeg dict); de aanroeper laat dan de bestaande waarden ongemoeid.

    Raises
    ------
    ValueError
        Met één melding per gevonden probleem (met regelnummer), als het
        bestand niet voldoet. Er wordt dan niets teruggegeven, zodat een
        half-geldig bestand nooit half wordt toegepast.
    """
    if isinstance(inhoud, bytes):
        try:
            inhoud = inhoud.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "Het bestand is geen geldige UTF-8-tekst; sla het op als 'CSV UTF-8'."
            ) from exc
    inhoud = inhoud.lstrip("\ufeff")

    eerste_regel = next((r for r in inhoud.splitlines() if r.strip()), "")
    scheidingsteken = ";" if ";" in eerste_regel else ","
    lezer = csv.reader(io.StringIO(inhoud), delimiter=scheidingsteken)

    fouten: list[str] = []
    records: dict[tuple, str] = {}
    volgorde: dict[str, list[tuple]] = {naam: [] for naam in _ONDERDELEN}
    kop_gezien = False

    for rij in lezer:
        regel = lezer.line_num
        if not any(cel.strip() for cel in rij):
            continue
        cellen = [c.strip() for c in rij] + [""] * (len(KOLOMMEN) - len(rij))
        if not kop_gezien:
            kop_gezien = True
            if [c.lower() for c in cellen[: len(KOLOMMEN)]] != list(KOLOMMEN):
                raise ValueError(
                    f"Ongeldige kop; verwacht de kolommen {';'.join(KOLOMMEN)}."
                )
            continue
        if len(rij) > len(KOLOMMEN):
            fouten.append(
                f"Regel {regel}: te veel kolommen (verwacht {len(KOLOMMEN)})."
            )
            continue

        onderdeel, klant, type_post, veld, waarde = cellen[: len(KOLOMMEN)]
        if onderdeel not in _ONDERDELEN:
            fouten.append(
                f'Regel {regel}: onbekend onderdeel "{onderdeel}"; '
                f"toegestaan: {', '.join(_ONDERDELEN)}."
            )
            continue
        velden, klant_nodig, type_nodig = _ONDERDELEN[onderdeel]
        if veld not in velden:
            fouten.append(
                f'Regel {regel}: onbekend veld "{veld}" voor onderdeel '
                f'"{onderdeel}"; toegestaan: {", ".join(velden)}.'
            )
            continue
        if bool(klant) != klant_nodig:
            fouten.append(
                f'Regel {regel}: kolom "klant" moet bij onderdeel '
                f'"{onderdeel}" {"ingevuld" if klant_nodig else "leeg"} zijn.'
            )
            continue
        if bool(type_post) != type_nodig:
            fouten.append(
                f'Regel {regel}: kolom "type_post" moet bij onderdeel '
                f'"{onderdeel}" {"ingevuld" if type_nodig else "leeg"} zijn.'
            )
            continue
        melding = _controleer_waarde(velden[veld], waarde)
        if melding:
            fouten.append(
                f'Regel {regel} ({onderdeel} "{klant or type_post}" {veld}): {melding}.'.replace(
                    ' ""', ""
                )
            )
            continue
        sleutel = (onderdeel, klant, type_post, veld)
        if sleutel in records:
            fouten.append(
                f"Regel {regel}: dubbele regel voor {onderdeel} {klant} {type_post} {veld}.".replace(
                    "  ", " "
                )
            )
            continue
        records[sleutel] = waarde
        volgorde[onderdeel].append(sleutel)

    if not kop_gezien:
        raise ValueError("Het bestand is leeg.")

    def _tabel(onderdeel: str, kolommen: list[str], sleutelindices: tuple[int, ...]):
        """Bouw een DataFrame uit de records van één tabel-onderdeel.

        `sleutelindices` kiest uit het (klant, type_post)-paar welke delen
        de eerste kolommen vormen (bijv. (1,) voor type_post: alleen de
        naam; (0, 1) voor klant_type_post).
        """
        entiteiten = list(dict.fromkeys((k, t) for _, k, t, _ in volgorde[onderdeel]))
        if not entiteiten:
            return None
        velden = _ONDERDELEN[onderdeel][0]
        rijen = []
        for klant, type_post in entiteiten:
            rij = dict(
                zip(
                    kolommen,
                    [(klant, type_post)[i] for i in sleutelindices],
                    strict=False,
                )
            )
            for veld, soort in velden.items():
                waarde = records.get((onderdeel, klant, type_post, veld))
                if waarde is None:
                    if soort != "getal_optioneel":
                        fouten.append(
                            f"{_label(onderdeel, klant, type_post)}: "
                            f"veld {veld} ontbreekt."
                        )
                    waarde = ""
                rij[veld] = waarde
            rijen.append(rij)
        return pd.DataFrame(rijen, columns=kolommen)

    klanten = _tabel("klant", _KLANTEN_KOLOMMEN, (0,))
    typen_posten = _tabel("type_post", _TYPEN_POSTEN_KOLOMMEN, (1,))
    klanten_typen = _tabel("klant_type_post", _KLANTEN_TYPEN_KOLOMMEN, (0, 1))

    instellingen = {
        veld: waarde
        for (onderdeel, _, _, veld), waarde in records.items()
        if onderdeel == "instelling"
    }
    totaal = {
        veld: waarde
        for (onderdeel, _, _, veld), waarde in records.items()
        if onderdeel == "totaal"
    }

    if typen_posten is not None and klanten_typen is not None:
        bekend = set(typen_posten["naam"])
        for type_post in dict.fromkeys(klanten_typen["type_post"]):
            if type_post not in bekend:
                fouten.append(
                    f'klant_type_post verwijst naar type post "{type_post}", '
                    "die niet als type_post in het bestand staat."
                )
    if instellingen.get("onderscheid") == "ja" and (
        typen_posten is None or klanten_typen is None
    ):
        fouten.append(
            'onderscheid = "ja" vereist zowel type_post- als '
            "klant_type_post-regels in het bestand."
        )

    if fouten:
        raise ValueError("\n".join(fouten))

    return {
        "instellingen": instellingen,
        "totaal": totaal,
        "klanten": klanten,
        "typen_posten": typen_posten,
        "klanten_typen": klanten_typen,
    }
