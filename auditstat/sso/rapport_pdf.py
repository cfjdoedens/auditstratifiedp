"""PDF-rapport van een SSO-evaluatie (invoer, resultaten en kanskrommen).

De functie :func:`maak_sso_rapport_pdf` zet de invoer van de SSO-tab en de
bijbehorende rekenresultaten om in een PDF (A4, Nederlandse getalnotatie)
en geeft de bytes terug. Er wordt niets naar schijf geschreven.

Dit onderdeel vereist het optionele pakket ``reportlab``
(``pip install auditstat[pdf]``).
"""

from __future__ import annotations

import datetime
import importlib.metadata
import io
import os
import re
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:  # pragma: no cover - afhankelijk van de omgeving
    raise ImportError(
        "Voor het PDF-rapport is 'reportlab' nodig: pip install auditstat[pdf]"
    ) from exc

from auditstat._formatting import nl_getal
from auditstat.sso.evalueer_SSO_totaal import (
    HELE_SSO_NAAM,
    KLANTEN_SAMEN_NAAM,
    klanten_samen,
)
from auditstat.sso.invoer_csv import _tekst
from auditstat.stratified.plot_kanskromme import plot_kanskromme

_LETTER = "DejaVuSans"
_LETTER_VET = "DejaVuSans-Bold"

_KALIBRATIE_LABELS = {
    "momentmatching": "Momentmatching (scherper, complexer)",
    "naief": "Eenvoudig (poolingformule, conservatief)",
}

_INSTELLING_LABELS = [
    ("model", "Model"),
    ("zekerheid", "Zekerheid"),
    ("berekeningsmethode", "Berekeningsmethode"),
    ("onderscheid", "Onderscheid naar typen posten"),
]
_TOTAAL_LABELS = [
    ("n", "n (steekproefomvang)"),
    ("k", "k (fouten)"),
    ("N_totaal", "N totaal (aantal posten)"),
    ("massa", "Totale massa (euro\u2019s)"),
    ("ihr", "ihr"),
    ("ibr", "ibr"),
    ("car", "car"),
    ("materialiteit", "Materialiteit"),
]


def _auditstat_versie() -> str:
    """Versie van auditstat waarmee het rapport wordt gemaakt.

    Bij een broncode-checkout (``pyproject.toml`` naast het pakket) is dat de
    versie uit dat bestand: de metadata van een editable installatie loopt
    na een versieverhoging achter. Anders de metadata van het geïnstalleerde
    pakket, en bij gebrek daaraan "onbekend".
    """
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        tekst = pyproject.read_text(encoding="utf-8")
        if re.search(r'^name\s*=\s*"auditstat"', tekst, re.MULTILINE):
            m = re.search(r'^version\s*=\s*"([^"]+)"', tekst, re.MULTILINE)
            if m:
                return m.group(1)
    except OSError:
        pass
    try:
        return importlib.metadata.version("auditstat")
    except importlib.metadata.PackageNotFoundError:
        return "onbekend"


def _registreer_lettertypen() -> None:
    """Registreer de met matplotlib meegeleverde DejaVu Sans (Unicode)."""
    if _LETTER in pdfmetrics.getRegisteredFontNames():
        return
    map_ = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    pdfmetrics.registerFont(TTFont(_LETTER, os.path.join(map_, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(
        TTFont(_LETTER_VET, os.path.join(map_, "DejaVuSans-Bold.ttf"))
    )
    pdfmetrics.registerFontFamily(_LETTER, normal=_LETTER, bold=_LETTER_VET)


def _stijlen() -> dict[str, ParagraphStyle]:
    return {
        "titel": ParagraphStyle(
            "titel", fontName=_LETTER_VET, fontSize=18, leading=22, spaceAfter=4
        ),
        "kop1": ParagraphStyle(
            "kop1",
            fontName=_LETTER_VET,
            fontSize=13,
            leading=16,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "kop2": ParagraphStyle(
            "kop2",
            fontName=_LETTER_VET,
            fontSize=11,
            leading=14,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "tekst": ParagraphStyle("tekst", fontName=_LETTER, fontSize=9, leading=12),
        "klein": ParagraphStyle(
            "klein",
            fontName=_LETTER,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#555555"),
        ),
        "cel": ParagraphStyle("cel", fontName=_LETTER, fontSize=8.5, leading=11),
        "cel_rechts": ParagraphStyle(
            "cel_rechts", fontName=_LETTER, fontSize=8.5, leading=11, alignment=2
        ),
        "kop_cel": ParagraphStyle(
            "kop_cel", fontName=_LETTER_VET, fontSize=8.5, leading=11
        ),
        "kop_cel_rechts": ParagraphStyle(
            "kop_cel_rechts",
            fontName=_LETTER_VET,
            fontSize=8.5,
            leading=11,
            alignment=2,
        ),
        "waarschuwing": ParagraphStyle(
            "waarschuwing",
            fontName=_LETTER,
            fontSize=8.5,
            leading=11,
            backColor=colors.HexColor("#FFF4D6"),
            borderPadding=4,
            spaceAfter=6,
        ),
    }


def _tabel(
    kop: list[str],
    rijen: list[list[str]],
    breedtes: list[float],
    stijlen: dict[str, ParagraphStyle],
    rechts: set[int] | None = None,
) -> Table:
    """Eenvoudige opgemaakte tabel; kolommen in `rechts` rechts uitgelijnd."""
    rechts = rechts or set()

    def cel(tekst: str, i: int, is_kop: bool) -> Paragraph:
        naam = ("kop_cel" if is_kop else "cel") + ("_rechts" if i in rechts else "")
        return Paragraph(escape(tekst), stijlen[naam])

    data = [[cel(t, i, True) for i, t in enumerate(kop)]]
    data += [[cel(t, i, False) for i, t in enumerate(rij)] for rij in rijen]
    tabel = Table(data, colWidths=breedtes, repeatRows=1, hAlign="LEFT")
    tabel.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#7A8794")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D0D5DA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    return tabel


def _df_tabel(
    df: pd.DataFrame,
    kolommen: dict[str, str],
    rechts: set[str],
    breedte: float,
    stijlen: dict[str, ParagraphStyle],
    fracties: list[float] | None = None,
) -> Table | None:
    """Tabel uit een DataFrame (lege tabelrijen overgeslagen), of None."""
    rijen = []
    for _, rij in df.iterrows():
        waarden = [_tekst(rij.get(k)) for k in kolommen]
        if not any(waarden):
            continue
        rijen.append(waarden)
    if not rijen:
        return None
    n = len(kolommen)
    fracties = fracties or [1 / n] * n
    breedtes = [breedte * f for f in fracties]
    return _tabel(
        list(kolommen.values()),
        rijen,
        breedtes,
        stijlen,
        rechts={i for i, k in enumerate(kolommen) if k in rechts},
    )


def _figuur_als_afbeelding(res: dict, breedte: float) -> Image:
    """Teken de kanskromme en geef 'm terug als reportlab-afbeelding."""
    fig = plot_kanskromme(res)
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    finally:
        plt.close(fig)
    buf.seek(0)
    from PIL import Image as PilImage  # matplotlib-afhankelijkheid

    with PilImage.open(buf) as im:
        px_b, px_h = im.size
    buf.seek(0)
    hoogte = breedte * px_h / px_b
    return Image(buf, width=breedte, height=hoogte)


def _methode_onderdelen(
    instellingen: dict[str, str], stijlen: dict[str, ParagraphStyle]
) -> list:
    """Flowables voor de methodebeschrijving, afgestemd op de instellingen."""
    model = instellingen.get("model", "binomiaal")
    kalibratie = instellingen.get("berekeningsmethode", "momentmatching")
    zekerheid = _tekst(instellingen.get("zekerheid")) or "0,95"

    def alinea(tekst: str) -> Paragraph:
        return Paragraph(
            tekst,
            ParagraphStyle("methode", parent=stijlen["tekst"], spaceAfter=5),
        )

    if model == "poisson":
        model_tekst = (
            "Gekozen model: <b>Poisson</b>. De foutkans heeft een "
            "gammaverdeling en het aantal fouten bij de klant een "
            "negatief-binomiale verdeling."
        )
    else:
        model_tekst = (
            "Gekozen model: <b>binomiaal</b>. De foutkans heeft een "
            "betaverdeling en het aantal fouten bij de klant een "
            "beta-binomiale verdeling."
        )

    onderdelen: list = [
        PageBreak(),
        Paragraph("Methodebeschrijving", stijlen["kop1"]),
        Paragraph("Uitgangspunt", stijlen["kop2"]),
        alinea(
            "De SSO trekt \u00e9\u00e9n gezamenlijke steekproef uit alle posten "
            "van de SSO: n posten met daarin k fouten. Uit die steekproef "
            "wordt per klant een bovengrens voor de fout afgeleid. Dat "
            "gebeurt per type post, of voor alle posten samen als er geen "
            "onderscheid naar typen posten is gemaakt."
        ),
        alinea(model_tekst),
        Paragraph("Aannames", stijlen["kop2"]),
        alinea(
            "<b>1. Willekeurige verspreiding.</b> De posten van elke klant "
            "liggen willekeurig verspreid tussen alle posten van de SSO, "
            "zonder herkenbaar patroon, en elke post hoort bij precies "
            "\u00e9\u00e9n klant. Alleen dan is de uit (n, k) geschatte foutkans "
            "een geldig uitgangspunt voor wat er bij \u00e9\u00e9n klant aan "
            "fouten te verwachten is."
        ),
        alinea(
            "<b>2. Vlakke prior.</b> Vooraf is elke foutkans even aannemelijk; "
            "de verdeling van de foutkans volgt dan alleen uit n en k."
        ),
        alinea(
            "<b>3. Elke post volledig goed of volledig fout.</b> Voor de "
            "spreiding bij de klant wordt elke post behandeld als "
            "\u00f3f volledig goed, \u00f3f volledig fout. Dat is de "
            "maximaal conservatieve keuze: voor elke grootheid X tussen 0 "
            "en 1 met gemiddelde p geldt Var(X) \u2264 p(1\u2212p), met "
            "gelijkheid alleen in dit binaire geval. Posten die in de "
            "praktijk gedeeltelijk fout zijn (tainting), hebben minder "
            "spreiding, dus de berekende grens is eerder te ruim dan te "
            "krap. Een op echte tainting-data gekalibreerd model is niet "
            "toegepast."
        ),
        Paragraph("Kalibratie per klant", stijlen["kop2"]),
    ]

    if kalibratie == "naief":
        onderdelen += [
            alinea(
                "Gekozen methode: <b>eenvoudig (poolingformule)</b>. Per type post "
                "wordt een effectieve steekproef bepaald met een "
                "poolingformule, naar analogie van weerstanden in parallel: "
                "n_eff = n\u00b7N_klant / (n + N_klant) en "
                "k_eff = k\u00b7n_eff / n, waarbij N_klant het aantal posten "
                "van de klant is."
            ),
            alinea(
                "De formule is gemotiveerd door twee grensgevallen "
                "(N_klant veel groter dan n: n_eff nadert n; N_klant veel "
                "kleiner dan n: n_eff nadert N_klant) en is geen afleiding "
                "uit een kansmodel. In de praktijk geeft ze meestal een "
                "conservatieve grens, ruimer dan die van de scherpere maar "
                "complexere kalibratiemethode. Onder zeer extreme "
                "omstandigheden, bij een zeer kleine N_klant (bijvoorbeeld 1 "
                "of enkele posten), kan de grens te laag uitvallen. Ze kent "
                "geen afhandeling van extreem kleine klanten en geeft "
                "daarom ook geen waarschuwing of weigering in die gevallen."
            ),
        ]
    else:
        onderdelen += [
            alinea(
                "Gekozen methode: <b>momentmatching</b>. Het aantal fouten "
                "bij de klant volgt een samengestelde verdeling: de "
                "onzekerheid over de SSO-brede foutkans, gecombineerd met de "
                "steekproefvariatie binnen de N_klant posten van de klant. "
                "Om die verdeling in de gestratificeerde berekening te "
                "kunnen gebruiken, wordt per type post een effectieve "
                "steekproef (n_eff, k_eff) gekozen waarvan de beta- "
                "(binomiaal) of gammaverdeling (Poisson) hetzelfde "
                "gemiddelde en dezelfde variantie heeft. Dit is scherper "
                "dan de eenvoudige poolingformule, maar ook complexer."
            ),
            alinea(
                "Is N_klant zo klein dat dit niet meer binnen de beta- of "
                "gammafamilie kan (k_eff zou negatief worden, of n_eff "
                "kleiner dan k_eff), dan wordt een (n_eff, k_eff) gekozen "
                "waarvan de 95%-grens gelijk is aan de grens van de "
                "samengestelde verdeling onder aanname 3. Dit gebeurt "
                f"altijd bij 95%, ook als de gekozen zekerheid {zekerheid} is, "
                "en het rapport toont dan een waarschuwing. Kan zelfs dat "
                "niet (de grens is vrijwel zeker 0 of 1), dan wordt de "
                "berekening geweigerd: controleer de posten van dat type bij "
                "die klant dan rechtstreeks."
            ),
        ]

    onderdelen += [
        Paragraph("Combineren en uitkomst", stijlen["kop2"]),
        alinea(
            "Elk type post vormt een stratum in euro\u2019s met zijn "
            "(n_eff, k_eff). De verdelingen van de foutfractie per stratum "
            "worden door convolutie (FFT) samengevoegd tot \u00e9\u00e9n verdeling "
            "van de totale fout van de klant. De risico-inschatting "
            "(ihr, ibr, car) en de materialiteit worden verwerkt als extra "
            "foutloze posten (HARo)."
        ),
        alinea(
            "De <b>maximale fout</b> in het rapport is de bovengrens van "
            f"die verdeling bij de gekozen zekerheid ({zekerheid}): met die "
            "zekerheid is de werkelijke fout bij de klant niet groter, "
            "onder bovenstaande aannames. De uitkomst is daarmee zo goed "
            "als deze aannames, in het bijzonder aanname 1."
        ),
    ]
    return onderdelen


def _paginanummer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(_LETTER, 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Pagina {doc.page}")
    canvas.drawString(2 * cm, 1.2 * cm, "auditstat \u2014 SSO-evaluatierapport")
    canvas.restoreState()


def maak_sso_rapport_pdf(
    invoer: dict,
    resultaten: dict,
    waarschuwingen: dict[str, list[str]] | None = None,
    tijdstip: datetime.datetime | None = None,
    methodebeschrijving: bool = False,
    resultaat_totaal: dict | None = None,
    voortgang: Callable[[float, str], None] | None = None,
) -> bytes:
    """Maak een PDF-rapport van een SSO-evaluatie.

    Parameters
    ----------
    invoer : dict
        De invoer waarmee is gerekend, in dezelfde vorm als de uitvoer van
        :func:`auditstat.sso.invoer_csv.lees_sso_invoer_csv`: sleutels
        ``instellingen`` en ``totaal`` (dicts met tekstwaarden in NL-notatie)
        en ``klanten``, ``typen_posten``, ``klanten_typen`` (DataFrames of
        None). Bij ``onderscheid == "ja"`` worden de typen-posten-tabellen
        getoond, anders de klantentabel.
    resultaten : dict
        Per klantnaam het resultaat van
        :func:`auditstat.sso.evalueer_SSO_klant_gestratificeerd.evalueer_SSO_klant_gestratificeerd`.
    waarschuwingen : dict, optional
        Per klantnaam een lijst met waarschuwingsteksten.
    tijdstip : datetime.datetime, optional
        Datum en tijd van maken, zoals vermeld in het rapport (standaard
        nu).
    methodebeschrijving : bool, standaard False
        Voeg aan het eind een pagina toe met de gekozen kalibratiemethode
        en de aannames van het model.
    resultaat_totaal : dict, optional
        Resultaat van
        :func:`auditstat.sso.evalueer_SSO_totaal.evalueer_SSO_totaal`; als
        opgegeven komt er een sectie "Hele SSO" met resultaat en kanskromme.
    voortgang : callable, optional
        Wordt na elke getekende kanskromme aangeroepen als
        ``voortgang(fractie, tekst)`` met ``fractie`` tussen 0 en 1, zodat
        een aanroeper (bijv. een voortgangsbalk) kan tonen dat het werk
        vordert. Het tekenen van de kanskrommen is het trage deel.

    Returns
    -------
    bytes
        De inhoud van het PDF-bestand.

    Raises
    ------
    ValueError
        Als `resultaten` leeg is.
    """
    if not resultaten:
        raise ValueError("Er zijn geen resultaten om in een rapport op te nemen.")

    _registreer_lettertypen()
    stijlen = _stijlen()
    waarschuwingen = waarschuwingen or {}
    tijdstip = tijdstip or datetime.datetime.now()
    instellingen = dict(invoer.get("instellingen") or {})
    totaal = invoer.get("totaal") or {}
    breedte = A4[0] - 4 * cm

    totaal_stappen = len(resultaten) + (1 if resultaat_totaal is not None else 0)
    gedaan = 0

    def _figuur(res: dict, naam: str) -> Image:
        nonlocal gedaan
        if voortgang is not None:
            voortgang(gedaan / totaal_stappen, f"Kanskromme tekenen: {naam}")
        afbeelding = _figuur_als_afbeelding(res, breedte)
        gedaan += 1
        if voortgang is not None:
            voortgang(gedaan / totaal_stappen, f"Kanskromme getekend: {naam}")
        return afbeelding

    onderdelen: list = [
        Paragraph("SSO-evaluatierapport", stijlen["titel"]),
        Paragraph(
            f"Gemaakt op {tijdstip.day}-{tijdstip.month}-{tijdstip.year}.",
            stijlen["klein"],
        ),
        Paragraph("Instellingen", stijlen["kop1"]),
    ]

    onderscheid = instellingen.get("onderscheid", "nee")
    weergave = dict(instellingen)
    weergave["berekeningsmethode"] = _KALIBRATIE_LABELS.get(
        instellingen.get("berekeningsmethode", ""),
        instellingen.get("berekeningsmethode", ""),
    )
    weergave["onderscheid"] = "ja" if onderscheid == "ja" else "nee"
    onderdelen.append(
        _tabel(
            ["Instelling", "Waarde"],
            [[lbl, _tekst(weergave.get(sl))] for sl, lbl in _INSTELLING_LABELS],
            [breedte * 0.5, breedte * 0.5],
            stijlen,
            rechts={1},
        )
    )

    onderdelen.append(Paragraph("SSO-totalen", stijlen["kop1"]))
    onderdelen.append(
        _tabel(
            ["Veld", "Waarde"],
            [[lbl, _tekst(totaal.get(sl))] for sl, lbl in _TOTAAL_LABELS],
            [breedte * 0.5, breedte * 0.5],
            stijlen,
            rechts={1},
        )
    )

    onderdelen.append(Paragraph("Klanten", stijlen["kop1"]))
    if onderscheid == "ja":
        tabellen = [
            (
                "Typen posten (SSO-breed)",
                invoer.get("typen_posten"),
                {
                    "naam": "Type post",
                    "n": "n",
                    "k": "k",
                    "ihr": "ihr",
                    "ibr": "ibr",
                    "car": "car",
                    "materialiteit": "Materialiteit",
                },
                {"n", "k", "materialiteit"},
                [0.26, 0.12, 0.08, 0.1, 0.1, 0.1, 0.24],
            ),
            (
                "Klanten per type post",
                invoer.get("klanten_typen"),
                {
                    "klant": "Klant",
                    "type_post": "Type post",
                    "N_klant": "N klant",
                    "waarde_laag": "Waarde (euro\u2019s)",
                },
                {"N_klant", "waarde_laag"},
                None,
            ),
        ]
    else:
        tabellen = [
            (
                None,
                invoer.get("klanten"),
                {
                    "klant": "Klant",
                    "N_klant": "N klant",
                    "waarde_laag": "Waarde (euro\u2019s)",
                },
                {"N_klant", "waarde_laag"},
                None,
            )
        ]
    for titel, df, kolommen, rechts, fracties in tabellen:
        if titel:
            onderdelen.append(Paragraph(titel, stijlen["kop2"]))
        tabel = (
            _df_tabel(df, kolommen, rechts, breedte, stijlen, fracties)
            if df is not None
            else None
        )
        onderdelen.append(
            tabel
            if tabel is not None
            else Paragraph("(geen gegevens)", stijlen["klein"])
        )

    onderdelen.append(Paragraph("Resultaat", stijlen["kop1"]))
    onderdelen.append(
        _tabel(
            ["Klant", "Maximale fout (fractie)", "Maximale fout (euro\u2019s)"],
            [
                [
                    klant,
                    nl_getal(res["max_fout_convolutie"], 4),
                    nl_getal(res["max_fout_convolutie_geld"], 2),
                ]
                for klant, res in resultaten.items()
            ],
            [breedte * 0.4, breedte * 0.3, breedte * 0.3],
            stijlen,
            rechts={1, 2},
        )
    )

    samen_fractie, samen_euro, _ = klanten_samen(resultaten)
    totalen_rijen = [
        [KLANTEN_SAMEN_NAAM, nl_getal(samen_fractie, 4), nl_getal(samen_euro, 2)]
    ]
    if resultaat_totaal is not None:
        totalen_rijen.append([
            HELE_SSO_NAAM,
            nl_getal(resultaat_totaal["max_fout_convolutie"], 4),
            nl_getal(resultaat_totaal["max_fout_convolutie_geld"], 2),
        ])
    onderdelen.append(Spacer(1, 10))
    onderdelen.append(
        _tabel(
            ["Totaal", "Maximale fout (fractie)", "Maximale fout (euro\u2019s)"],
            totalen_rijen,
            [breedte * 0.4, breedte * 0.3, breedte * 0.3],
            stijlen,
            rechts={1, 2},
        )
    )
    toelichting = (
        "Klanten samen is de som van de afzonderlijke klantgrenzen (de "
        "foutfractie is gewogen naar de massa van elke klant) en daardoor "
        "ruimer dan een gezamenlijke grens voor de klanten samen."
    )
    if resultaat_totaal is not None:
        toelichting += (
            " Hele SSO is een eigenstandige berekening op de gegevens van "
            "de hele SSO."
        )
    onderdelen.append(Paragraph(toelichting, stijlen["klein"]))

    if resultaat_totaal is not None:
        onderdelen.append(
            KeepTogether([
                Paragraph("Hele SSO", stijlen["kop1"]),
                Paragraph(
                    "Dit resultaat is niet de optelling van de resultaten "
                    "van de afzonderlijke klanten, maar een eigenstandige "
                    "berekening die alleen uitgaat van de gegevens van de "
                    "hele SSO: n, k, de totale massa, IHR, IBR, CAR en de "
                    "materialiteit. Maximale fout: "
                    f"<b>{nl_getal(resultaat_totaal['max_fout_convolutie'], 4)}"
                    "</b> (fractie), "
                    f"<b>{nl_getal(resultaat_totaal['max_fout_convolutie_geld'], 2)}"
                    "</b> euro\u2019s.",
                    stijlen["tekst"],
                ),
                Spacer(1, 6),
                _tabel(
                    ["Type post", "Waarde (euro\u2019s)", "n", "k"],
                    [
                        [
                            _tekst(r["naam"]),
                            nl_getal(r["waarde_laag"], 2),
                            nl_getal(r["n_laag"], 0),
                            nl_getal(r["k_laag"], 0),
                        ]
                        for _, r in resultaat_totaal["steekproeven"].iterrows()
                    ],
                    [breedte * 0.34, breedte * 0.26, breedte * 0.2, breedte * 0.2],
                    stijlen,
                    rechts={1, 2, 3},
                ),
            ])
        )
        onderdelen.append(_figuur(resultaat_totaal, "Hele SSO"))

    alle_waarschuwingen = [
        f"Klant \u2019{klant}\u2019: {w}"
        for klant, ws in waarschuwingen.items()
        for w in ws
    ]
    if alle_waarschuwingen:
        onderdelen.append(Paragraph("Waarschuwingen", stijlen["kop2"]))
        for w in alle_waarschuwingen:
            onderdelen.append(Paragraph(escape(w), stijlen["waarschuwing"]))

    for klant, res in resultaten.items():
        steekproeven = res["steekproeven"]
        rijen = [
            [
                _tekst(r["naam"]),
                nl_getal(r["waarde_laag"], 2),
                nl_getal(r["n_laag"], 2),
                nl_getal(r["k_laag"], 2),
            ]
            for _, r in steekproeven.iterrows()
        ]
        blok = [
            Paragraph(escape(klant), stijlen["kop1"]),
            Paragraph(
                "Maximale fout: "
                f"<b>{nl_getal(res['max_fout_convolutie'], 4)}</b> (fractie), "
                f"<b>{nl_getal(res['max_fout_convolutie_geld'], 2)}</b> euro\u2019s.",
                stijlen["tekst"],
            ),
            Spacer(1, 6),
            _tabel(
                ["Type post", "Waarde (euro\u2019s)", "n (effectief)", "k (effectief)"],
                rijen,
                [breedte * 0.34, breedte * 0.26, breedte * 0.2, breedte * 0.2],
                stijlen,
                rechts={1, 2, 3},
            ),
            Paragraph(
                "n en k zijn de gekalibreerde, effectieve waarden voor deze "
                "klant (geen gehele tellingen).",
                stijlen["klein"],
            ),
            Spacer(1, 8),
        ]
        onderdelen.append(KeepTogether(blok))
        onderdelen.append(_figuur(res, klant))

    if methodebeschrijving:
        onderdelen += _methode_onderdelen(instellingen, stijlen)

    onderdelen.append(Spacer(1, 18))
    onderdelen.append(
        Paragraph(
            f"Dit rapport is gemaakt met auditstat versie {escape(_auditstat_versie())} "
            f"op {tijdstip.day}-{tijdstip.month}-{tijdstip.year} "
            f"om {tijdstip:%H:%M:%S}.",
            stijlen["klein"],
        )
    )

    uit = io.BytesIO()
    doc = SimpleDocTemplate(
        uit,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="SSO-evaluatierapport",
        author="auditstat",
    )
    doc.build(onderdelen, onFirstPage=_paginanummer, onLaterPages=_paginanummer)
    return uit.getvalue()
