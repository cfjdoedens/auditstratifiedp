import datetime
import io

import pandas as pd
import pytest

pytest.importorskip("reportlab")

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from auditstat.geldsteek_gestratificeerd.plan_geldsteek_gestratificeerd import (  # noqa: E402
    plan_geldsteek_gestratificeerd_basis,
)
from auditstat.geldsteek_gestratificeerd.rapport_plan_pdf import (  # noqa: E402
    maak_plan_rapport_pdf,
)


def _pdf_tekst(pdf: bytes) -> str:
    pypdf = pytest.importorskip("pypdf")
    lezer = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join(p.extract_text() for p in lezer.pages)


@pytest.fixture(scope="module")
def strata() -> pd.DataFrame:
    invoer = pd.DataFrame({
        "naam": ["Alfa", "Beta"],
        "waarde_laag": [1_000_000.0, 5_000_000.0],
        "verwachte_foutfractie": [0.001, 0.002],
        "ihr": ["M", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "waarde_hoog": [0.0, 100_000.0],
        "fout_hoog": [0.0, 1_000.0],
        "materialiteit": [0.02, 0.02],
        "kosten": [1.0, 2.0],
    })
    s = plan_geldsteek_gestratificeerd_basis(invoer, model="binomiaal")
    s.loc[0, "n_laag"] += 20
    s["k_laag"] = s["n_laag"] * s["verwachte_foutfractie"]
    return s


@pytest.fixture(scope="module")
def instellingen() -> dict:
    return {
        "materialiteit": 0.02,
        "zekerheid": 0.95,
        "model": "binomiaal",
        "granulariteit": 10_000,
    }


def test_rapport_is_een_pdf_met_de_hoofdonderdelen(strata, instellingen):
    pdf = maak_plan_rapport_pdf(
        strata,
        instellingen,
        status="Optimalisatie voltooid!",
        tijdstip=datetime.datetime(2026, 11, 28, 12, 0, 0),
    )
    assert pdf.startswith(b"%PDF")
    tekst = _pdf_tekst(pdf)
    for deel in (
        "Planningsrapport",
        "Alfa",
        "Beta",
        "Geplande steekproefomvang",
        "Kanskromme",
        "Optimalisatie voltooid!",
        "28-11-2026",
    ):
        assert deel in tekst


def test_rapport_vermeldt_of_het_doel_is_bereikt(strata, instellingen):
    streng = dict(instellingen, materialiteit=0.0005)
    tekst = " ".join(_pdf_tekst(maak_plan_rapport_pdf(strata, streng)).split())
    assert "Doel bereikt nee" in tekst
    goed = " ".join(_pdf_tekst(maak_plan_rapport_pdf(strata, instellingen)).split())
    assert "Doel bereikt ja" in goed


def test_ontbrekende_kolom_geeft_value_error(strata, instellingen):
    with pytest.raises(ValueError, match="kosten"):
        maak_plan_rapport_pdf(strata.drop(columns=["kosten"]), instellingen)


def test_ontbrekende_instelling_geeft_value_error(strata, instellingen):
    zonder = {k: v for k, v in instellingen.items() if k != "model"}
    with pytest.raises(ValueError, match="model"):
        maak_plan_rapport_pdf(strata, zonder)


def test_lege_planning_geeft_value_error(strata, instellingen):
    with pytest.raises(ValueError, match="geen planning"):
        maak_plan_rapport_pdf(strata.iloc[0:0], instellingen)
