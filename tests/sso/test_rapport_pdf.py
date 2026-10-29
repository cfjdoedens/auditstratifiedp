import datetime
import io

import pandas as pd
import pytest

pytest.importorskip("reportlab")

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from auditstat.sso.evalueer_SSO_klant_gestratificeerd import (  # noqa: E402
    evalueer_SSO_klant_gestratificeerd,
)
from auditstat.sso.rapport_pdf import maak_sso_rapport_pdf  # noqa: E402


def _pdf_tekst(pdf: bytes) -> str:
    """Probeer tekst uit de PDF te halen (alleen als pypdf beschikbaar is)."""
    pypdf = pytest.importorskip("pypdf")
    lezer = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join(p.extract_text() for p in lezer.pages)


@pytest.fixture(scope="module")
def resultaten():
    post_typen = [
        dict(
            naam="Emolumenten",
            n=120,
            k=1,
            N_klant=1800,
            waarde_laag=900_000.0,
            materialiteit=0.01,
        ),
        dict(
            naam="Inkoopfacturen",
            n=80,
            k=3,
            N_klant=1200,
            waarde_laag=600_000.0,
            materialiteit=0.01,
        ),
    ]
    return {
        "Klant A": evalueer_SSO_klant_gestratificeerd(post_typen, zekerheid=0.95),
        "Klant B": evalueer_SSO_klant_gestratificeerd(post_typen, zekerheid=0.95),
    }


@pytest.fixture
def invoer():
    return {
        "instellingen": {
            "model": "binomiaal",
            "zekerheid": "0,95",
            "berekeningsmethode": "momentmatching",
            "onderscheid": "ja",
        },
        "totaal": {
            "n": "200",
            "k": "4",
            "N_totaal": "5.000",
            "massa": "2.500.000,00",
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "materialiteit": "0,01",
        },
        "klanten": pd.DataFrame({
            "klant": ["Klant A", "Klant B"],
            "N_klant": ["3.000", "2.000"],
            "waarde_laag": ["1.500.000,00", "1.000.000,00"],
        }),
        "typen_posten": pd.DataFrame({
            "naam": ["Emolumenten", "Inkoopfacturen"],
            "n": ["120", "80"],
            "k": ["1", "3"],
            "ihr": ["H", "H"],
            "ibr": ["H", "H"],
            "car": ["H", "H"],
            "materialiteit": ["0,01", "0,01"],
        }),
        "klanten_typen": pd.DataFrame({
            "klant": ["Klant A", "Klant A"],
            "type_post": ["Emolumenten", "Inkoopfacturen"],
            "N_klant": ["1.800", "1.200"],
            "waarde_laag": ["900.000,00", "600.000,00"],
        }),
    }


def test_geeft_geldige_pdf_terug(invoer, resultaten):
    pdf = maak_sso_rapport_pdf(invoer, resultaten, datum=datetime.date(2026, 10, 29))
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")


def test_bevat_klanten_en_nl_getallen(invoer, resultaten):
    tekst = _pdf_tekst(maak_sso_rapport_pdf(invoer, resultaten))
    assert "Klant A" in tekst and "Klant B" in tekst
    assert "Momentmatching" in tekst
    fractie = f"{resultaten['Klant A']['max_fout_convolutie']:.4f}".replace(".", ",")
    assert fractie in tekst


def test_zonder_onderscheid_toont_klantentabel(invoer, resultaten):
    invoer["instellingen"]["onderscheid"] = "nee"
    tekst = _pdf_tekst(maak_sso_rapport_pdf(invoer, resultaten))
    assert "Typen posten (SSO-breed)" not in tekst
    assert "Klant A" in tekst


def test_waarschuwingen_komen_in_rapport(invoer, resultaten):
    tekst = _pdf_tekst(
        maak_sso_rapport_pdf(
            invoer,
            resultaten,
            waarschuwingen={"Klant A": ["Let op: N_klant ≥ 1 klein"]},
        )
    )
    assert "Waarschuwingen" in tekst
    assert "Let op" in tekst


def test_ontbrekende_tabellen_geven_geen_fout(invoer, resultaten):
    invoer["typen_posten"] = None
    invoer["klanten_typen"] = None
    assert maak_sso_rapport_pdf(invoer, resultaten).startswith(b"%PDF-")


def test_lege_resultaten_geven_value_error(invoer):
    with pytest.raises(ValueError, match="geen resultaten"):
        maak_sso_rapport_pdf(invoer, {})


def test_speciale_tekens_in_namen_breken_niet(invoer, resultaten):
    resultaten = {"A&B <café>": resultaten["Klant A"]}
    assert maak_sso_rapport_pdf(invoer, resultaten).startswith(b"%PDF-")


def test_methodebeschrijving_standaard_uit(invoer, resultaten):
    tekst = _pdf_tekst(maak_sso_rapport_pdf(invoer, resultaten))
    assert "Methodebeschrijving" not in tekst


def test_methodebeschrijving_momentmatching(invoer, resultaten):
    tekst = _pdf_tekst(
        maak_sso_rapport_pdf(invoer, resultaten, methodebeschrijving=True)
    )
    assert "Methodebeschrijving" in tekst
    assert "momentmatching" in tekst
    assert "Aannames" in tekst
    assert "beta-binomiale" in tekst


def test_methodebeschrijving_naief_en_poisson(invoer, resultaten):
    invoer["instellingen"]["berekeningsmethode"] = "naief"
    invoer["instellingen"]["model"] = "poisson"
    tekst = _pdf_tekst(
        maak_sso_rapport_pdf(invoer, resultaten, methodebeschrijving=True)
    )
    assert "poolingformule" in tekst
    assert "negatief-binomiale" in tekst
    assert "momentmatching" not in tekst.split("Methodebeschrijving", 1)[1]
