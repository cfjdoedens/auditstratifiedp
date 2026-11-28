"""PDF-rapport van een planning voor een gestratificeerde geldsteekproef.

Gebruikt reportlab (optionele dependency, extra ``pdf``) en dezelfde opmaak
als het SSO-rapport (``auditstat.sso.rapport_pdf``).
"""

from __future__ import annotations

import datetime
import io
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from auditstat._formatting import nl_getal
from auditstat.geldsteek_gestratificeerd.evalueer_geldsteek_gestratificeerd import (
    evalueer_geldsteek_gestratificeerd,
)
from auditstat.sso.rapport_pdf import (
    _LETTER,
    _auditstat_versie,
    _figuur_als_afbeelding,
    _registreer_lettertypen,
    _stijlen,
    _tabel,
)

_VEREISTE_KOLOMMEN = [
    "naam",
    "waarde_laag",
    "verwachte_foutfractie",
    "ihr",
    "ibr",
    "car",
    "waarde_hoog",
    "fout_hoog",
    "materialiteit",
    "kosten",
    "n_basis",
    "n_laag",
]


def _nl(x: float, decimalen: int = 0) -> str:
    return nl_getal(x, decimalen)


def _paginanummer(canvas, doc) -> None:
    from reportlab.lib import colors

    canvas.saveState()
    canvas.setFont(_LETTER, 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Pagina {doc.page}")
    canvas.drawString(2 * cm, 1.2 * cm, "auditstat \u2014 planningsrapport")
    canvas.restoreState()


def maak_plan_rapport_pdf(
    strata: pd.DataFrame,
    instellingen: dict,
    status: str | None = None,
    tijdstip: datetime.datetime | None = None,
) -> bytes:
    """Maak een PDF-rapport van een steekproefplanning.

    Parameters
    ----------
    strata : pandas.DataFrame
        Het planningsresultaat: de strata zoals de planning ze oplevert, met
        de kolommen ``naam``, ``waarde_laag``, ``verwachte_foutfractie``,
        ``ihr``, ``ibr``, ``car``, ``waarde_hoog``, ``fout_hoog``,
        ``materialiteit``, ``kosten``, ``n_basis`` (basissteekproefomvang),
        ``n_laag`` (totale steekproefomvang na de klimoptimalisatie) en
        ``k_laag``.
    instellingen : dict
        Sleutels ``materialiteit`` (totale materialiteit als fractie van de
        totale waarde), ``zekerheid``, ``model`` ("binomiaal" of "poisson")
        en ``granulariteit``.
    status : str, optional
        Statusregel van de planning (bijv. "Optimalisatie voltooid ...").
    tijdstip : datetime.datetime, optional
        Datum en tijd van maken (standaard nu).

    Returns
    -------
    bytes
        De inhoud van het PDF-bestand.

    Raises
    ------
    ValueError
        Bij ontbrekende kolommen of sleutels, of een lege planning.
    """
    ontbreekt = [k for k in _VEREISTE_KOLOMMEN + ["k_laag"] if k not in strata.columns]
    if ontbreekt:
        raise ValueError(
            f"Ontbrekende kolommen in de planning: {', '.join(ontbreekt)}."
        )
    if strata.empty:
        raise ValueError("Er is geen planning om in een rapport op te nemen.")
    for sleutel in ("materialiteit", "zekerheid", "model", "granulariteit"):
        if sleutel not in instellingen:
            raise ValueError(f"Instelling ontbreekt: {sleutel}.")

    zekerheid = float(instellingen["zekerheid"])
    model = str(instellingen["model"])
    granulariteit = int(instellingen["granulariteit"])
    materialiteit = float(instellingen["materialiteit"])

    # Evaluatie van het eindplan bij het verwachte aantal fouten (k_laag).
    res = evalueer_geldsteek_gestratificeerd(
        strata.reset_index(drop=True),
        model=model,
        zekerheid=zekerheid,
        methode="FFT samen",
        granulariteit=granulariteit,
        vergelijk=False,
    )

    _registreer_lettertypen()
    stijlen = _stijlen()
    tijdstip = tijdstip or datetime.datetime.now()
    breedte = A4[0] - 4 * cm

    populatie = float((strata["waarde_laag"] + strata["waarde_hoog"]).sum())
    materialiteit_geld = materialiteit * populatie
    max_fout = float(res["max_fout_convolutie"])
    max_fout_geld = float(res["max_fout_convolutie_geld"])
    bereikt = max_fout <= materialiteit
    n_tot = float(strata["n_laag"].sum())
    kosten_tot = float((strata["n_laag"] * strata["kosten"]).sum())

    onderdelen: list = [
        Paragraph("Planningsrapport geldsteek gestratificeerd", stijlen["titel"]),
        Paragraph(
            f"Gemaakt op {tijdstip.day}-{tijdstip.month}-{tijdstip.year}.",
            stijlen["klein"],
        ),
        Paragraph("Instellingen", stijlen["kop1"]),
        _tabel(
            ["Instelling", "Waarde"],
            [
                [
                    "Totale materialiteit",
                    f"{_nl(materialiteit, 4)} van de totale waarde "
                    f"({_nl(materialiteit_geld, 2)} euro)",
                ],
                ["Zekerheid", _nl(zekerheid, 4)],
                ["Model", model],
                ["Granulariteit", _nl(granulariteit, 0)],
                ["Totale waarde populatie (euro)", _nl(populatie, 2)],
            ],
            [breedte * 0.5, breedte * 0.5],
            stijlen,
            rechts={1},
        ),
        Paragraph("Resultaat", stijlen["kop1"]),
        _tabel(
            ["Onderdeel", "Waarde"],
            [
                ["Totale steekproefomvang (n)", _nl(n_tot, 0)],
                ["Totale kosten (n \u00d7 kosten per steek)", _nl(kosten_tot, 2)],
                [
                    "Maximale fout bij verwacht aantal fouten",
                    f"{_nl(max_fout, 4)} ({_nl(max_fout_geld, 2)} euro)",
                ],
                [
                    "Doel (materialiteit)",
                    f"{_nl(materialiteit, 4)} ({_nl(materialiteit_geld, 2)} euro)",
                ],
                ["Doel bereikt", "ja" if bereikt else "nee"],
            ],
            [breedte * 0.5, breedte * 0.5],
            stijlen,
            rechts={1},
        ),
    ]
    if status:
        onderdelen.append(Spacer(1, 4))
        onderdelen.append(Paragraph(escape(status), stijlen["klein"]))

    onderdelen.append(Paragraph("Invoer laagstratum", stijlen["kop1"]))
    onderdelen.append(
        _tabel(
            [
                "Stratum",
                "Waarde laag (euro)",
                "Verwachte foutfractie",
                "IHR",
                "IBR",
                "CAR",
                "Materialiteit",
                "Kosten per steek",
            ],
            [
                [
                    str(r.naam),
                    _nl(r.waarde_laag, 2),
                    _nl(r.verwachte_foutfractie, 4),
                    str(r.ihr),
                    str(r.ibr),
                    str(r.car),
                    _nl(r.materialiteit, 4),
                    _nl(r.kosten, 2),
                ]
                for r in strata.itertuples()
            ],
            [breedte * f for f in (0.14, 0.17, 0.16, 0.08, 0.08, 0.08, 0.15, 0.14)],
            stijlen,
            rechts={1, 2, 6, 7},
        )
    )
    onderdelen.append(Paragraph("Invoer hoogstratum", stijlen["kop1"]))
    onderdelen.append(
        _tabel(
            ["Stratum", "Waarde hoog (euro)", "Fout hoog (euro)"],
            [
                [str(r.naam), _nl(r.waarde_hoog, 2), _nl(r.fout_hoog, 2)]
                for r in strata.itertuples()
            ],
            [breedte * f for f in (0.3, 0.35, 0.35)],
            stijlen,
            rechts={1, 2},
        )
    )

    onderdelen.append(
        Paragraph("Geplande steekproefomvang per stratum", stijlen["kop1"])
    )
    onderdelen.append(
        _tabel(
            ["Stratum", "n basis", "n extra (optimalisatie)", "n totaal", "Kosten"],
            [
                [
                    str(r.naam),
                    _nl(r.n_basis, 0),
                    _nl(r.n_laag - r.n_basis, 0),
                    _nl(r.n_laag, 0),
                    _nl(r.n_laag * r.kosten, 2),
                ]
                for r in strata.itertuples()
            ],
            [breedte * f for f in (0.3, 0.15, 0.25, 0.15, 0.15)],
            stijlen,
            rechts={1, 2, 3, 4},
        )
    )
    onderdelen.append(
        Paragraph(
            "n basis volgt uit verwachte foutfractie, materialiteit, IHR, IBR en "
            "CAR per stratum. n extra is toegevoegd door de klimoptimalisatie, "
            "zodat de maximale fout van alle strata samen onder de totale "
            "materialiteit komt.",
            stijlen["klein"],
        )
    )

    onderdelen.append(
        KeepTogether([
            Paragraph("Kanskromme van het plan", stijlen["kop1"]),
            Paragraph(
                "De kromme hoort bij de geplande steekproefomvang, met per stratum "
                "het verwachte aantal fouten (n \u00d7 verwachte foutfractie). Het is "
                "een verwachting vooraf, geen uitkomst van een steekproef.",
                stijlen["klein"],
            ),
            _figuur_als_afbeelding(res, breedte),
        ])
    )

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
        title="Planningsrapport geldsteek gestratificeerd",
        author="auditstat",
    )
    doc.build(onderdelen, onFirstPage=_paginanummer, onLaterPages=_paginanummer)
    return uit.getvalue()
