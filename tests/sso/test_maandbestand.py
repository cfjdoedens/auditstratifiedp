import pandas as pd
import pytest

from auditstat.sso.maandbestand import (
    MAAND_KOLOMMEN,
    lees_maandbestand,
    maak_voorbeeld_maandbestand,
    maandbestand_csv,
    maandtotalen_per_type_post,
)

KOP = ";".join(MAAND_KOLOMMEN) + "\n"


def _lees(tekst: str) -> pd.DataFrame:
    return lees_maandbestand(tekst.encode("utf-8"))


def _rij(post_id="1", datum="2026-10-01", klant="A", typ="T", bedrag="5,00") -> str:
    return f"{klant};{datum};{post_id};{typ};{bedrag}\n"


def test_voorbeeld_is_reproduceerbaar_en_heeft_juiste_vorm():
    a = maak_voorbeeld_maandbestand("Klant A", 2026, 10, 50, ["E", "I"])
    b = maak_voorbeeld_maandbestand("Klant A", 2026, 10, 50, ["E", "I"])
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == list(MAAND_KOLOMMEN)
    assert len(a) == 50
    assert a["post_id"].is_unique
    assert set(a["type_post"]) <= {"E", "I"}
    assert a["datum"].str.startswith("2026-10-").all()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"klant": " "},
        {"typen": []},
        {"maand": 0},
        {"maand": 13},
        {"aantal": 0},
    ],
)
def test_voorbeeld_weigert_ongeldige_argumenten(kwargs):
    args = {"klant": "A", "jaar": 2026, "maand": 10, "aantal": 5, "typen": ["T"]}
    args.update(kwargs)
    with pytest.raises(ValueError):
        maak_voorbeeld_maandbestand(**args)


def test_heen_en_terug_behoudt_bedragen_exact():
    df = maak_voorbeeld_maandbestand("Klant A", 2026, 2, 500, ["E", "I", "O"])
    terug = lees_maandbestand(maandbestand_csv(df))
    verwacht = (
        df["bedrag"].str.replace(",", ".").astype(float).mul(100).round().astype(int)
    )
    assert terug["bedrag_cent"].tolist() == verwacht.tolist()
    assert terug["post_id"].tolist() == df["post_id"].tolist()


@pytest.mark.parametrize(
    ("bedrag", "centen"),
    [("5", 500), ("5,5", 550), ("5.50", 550), ("0,01", 1), ("1234,56", 123456)],
)
def test_geldige_bedragen(bedrag, centen):
    assert _lees(KOP + _rij(bedrag=bedrag))["bedrag_cent"].tolist() == [centen]


@pytest.mark.parametrize(
    "bedrag", ["1.234,56", "12,345", "-5", "abc", "5,", "0,00", "0", "1e3"]
)
def test_ongeldige_bedragen(bedrag):
    with pytest.raises(ValueError, match="bedrag|Bedrag"):
        _lees(KOP + _rij(bedrag=bedrag))


def test_bom_en_windows_regeleinden_worden_geaccepteerd():
    data = ("\ufeff" + KOP + _rij()).replace("\n", "\r\n").encode("utf-8")
    assert len(lees_maandbestand(data)) == 1


@pytest.mark.parametrize(
    ("tekst", "melding"),
    [
        ("klant;datum;post_id;bedrag;type_post\n", "kolommen"),
        (KOP, "geen posten"),
        (KOP + _rij() + _rij(), "dubbele"),
        (KOP + _rij(klant=""), "Lege waarden"),
        (KOP + _rij() + _rij(post_id="2", klant="B"), "één klant"),
        (KOP + _rij() + _rij(post_id="2", datum="2026-11-01"), "kalendermaand"),
        (KOP + _rij(datum="2026-02-30"), "datum"),
        (KOP + _rij(datum="1-10-2026"), "datum"),
        (KOP + _rij(datum="2026-1-01"), "datum"),
    ],
)
def test_ongeldig_bestand_geeft_value_error(tekst, melding):
    with pytest.raises(ValueError, match=melding):
        _lees(tekst)


def test_te_groot_bestand_wordt_geweigerd(monkeypatch):
    import auditstat.sso.maandbestand as mod

    monkeypatch.setattr(mod, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="20 MB"):
        _lees(KOP + _rij())


def test_te_veel_posten_wordt_geweigerd(monkeypatch):
    import auditstat.sso.maandbestand as mod

    monkeypatch.setattr(mod, "MAX_POSTEN", 1)
    with pytest.raises(ValueError, match="100.000"):
        _lees(KOP + _rij() + _rij(post_id="2"))


def test_maandtotalen_per_type_post():
    df = _lees(
        KOP
        + _rij(post_id="1", typ="E", bedrag="10,10")
        + _rij(post_id="2", typ="E", bedrag="0,05")
        + _rij(post_id="3", typ="I", bedrag="7")
    )
    t = maandtotalen_per_type_post(df).set_index("type_post")
    assert t.loc["E", "N_klant"] == 2
    assert t.loc["E", "bedrag_cent"] == 1015
    assert t.loc["E", "waarde_laag"] == pytest.approx(10.15)
    assert t.loc["I", "N_klant"] == 1
    assert t["bedrag_cent"].sum() == 1715
