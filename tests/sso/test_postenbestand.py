import pandas as pd
import pytest

from auditstat.sso.postenbestand import (
    POSTEN_KOLOMMEN,
    lees_postenbestand,
    maak_voorbeeld_postenbestand,
    maak_voorbeeld_sso_postenbestand,
    postenbestand_csv,
    postgroottes_per_type_post,
    totalen_per_type_post,
    variatiecoefficient,
)

KOP = ";".join(POSTEN_KOLOMMEN) + "\n"


def _lees(tekst: str) -> pd.DataFrame:
    return lees_postenbestand(tekst.encode("utf-8"))


def _rij(post_id="1", klant="A", typ="T", bedrag="5,00") -> str:
    return f"{klant};{post_id};{typ};{bedrag}\n"


def test_voorbeeld_is_reproduceerbaar_en_heeft_juiste_vorm():
    a = maak_voorbeeld_postenbestand("Klant A", 50, ["E", "I"])
    b = maak_voorbeeld_postenbestand("Klant A", 50, ["E", "I"])
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == list(POSTEN_KOLOMMEN)
    assert len(a) == 50
    assert a["post_id"].is_unique
    assert set(a["type_post"]) <= {"E", "I"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"klant": " "},
        {"typen": []},
        {"aantal": 0},
    ],
)
def test_voorbeeld_weigert_ongeldige_argumenten(kwargs):
    args = {"klant": "A", "aantal": 5, "typen": ["T"]}
    args.update(kwargs)
    with pytest.raises(ValueError):
        maak_voorbeeld_postenbestand(**args)


def test_heen_en_terug_behoudt_bedragen_exact():
    df = maak_voorbeeld_postenbestand("Klant A", 500, ["E", "I", "O"])
    terug = lees_postenbestand(postenbestand_csv(df))
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
    assert len(lees_postenbestand(data)) == 1


@pytest.mark.parametrize(
    ("tekst", "melding"),
    [
        ("klant;post_id;bedrag;type_post\n", "kolommen"),
        (KOP, "geen posten"),
        (KOP + _rij() + _rij(), "dubbele"),
        (KOP + _rij(klant=""), "Lege waarden"),
        (KOP + _rij() + _rij(post_id="2", klant="B"), "één klant"),
    ],
)
def test_ongeldig_bestand_geeft_value_error(tekst, melding):
    with pytest.raises(ValueError, match=melding):
        _lees(tekst)


def test_te_groot_bestand_wordt_geweigerd(monkeypatch):
    import auditstat.sso.postenbestand as mod

    monkeypatch.setattr(mod, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="MB groot"):
        _lees(KOP + _rij())


def test_te_veel_posten_wordt_geweigerd(monkeypatch):
    import auditstat.sso.postenbestand as mod

    monkeypatch.setattr(mod, "MAX_POSTEN", 1)
    with pytest.raises(ValueError, match="maximaal 1 posten"):
        _lees(KOP + _rij() + _rij(post_id="2"))


def test_totalen_per_type_post():
    df = _lees(
        KOP
        + _rij(post_id="1", typ="E", bedrag="10,10")
        + _rij(post_id="2", typ="E", bedrag="0,05")
        + _rij(post_id="3", typ="I", bedrag="7")
    )
    t = totalen_per_type_post(df).set_index("type_post")
    assert t.loc["E", "N_klant"] == 2
    assert t.loc["E", "bedrag_cent"] == 1015
    assert t.loc["E", "waarde_laag"] == pytest.approx(10.15)
    assert t.loc["I", "N_klant"] == 1
    assert t["bedrag_cent"].sum() == 1715


def test_meerdere_klanten_alleen_toegestaan_voor_sso_bestand():
    tekst = KOP + _rij("1", "A") + _rij("2", "B")
    with pytest.raises(ValueError, match="één klant"):
        lees_postenbestand(tekst.encode())
    df = lees_postenbestand(tekst.encode(), meerdere_klanten=True)
    assert df["klant"].nunique() == 2


def test_sso_bestand_heeft_ruimere_limieten(monkeypatch):
    from auditstat.sso import postenbestand as mod

    monkeypatch.setattr(mod, "MAX_POSTEN_SSO", 1)
    tekst = KOP + _rij("1", "A") + _rij("2", "B")
    with pytest.raises(ValueError, match="maximaal 1 posten"):
        lees_postenbestand(tekst.encode(), meerdere_klanten=True)


def test_postgroottes_per_type_post_en_variatiecoefficient():
    tekst = KOP + _rij("1", "A", "X", "2,00") + _rij("2", "B", "X", "4,00")
    tekst += _rij("3", "B", "Y", "10,00")
    df = lees_postenbestand(tekst.encode(), meerdere_klanten=True)
    waarden = postgroottes_per_type_post(df)
    assert sorted(waarden["X"]) == [2.0, 4.0]
    assert list(waarden["Y"]) == [10.0]
    assert variatiecoefficient(waarden["X"]) == pytest.approx(1 / 3)
    assert variatiecoefficient(waarden["Y"]) == 0.0


def test_variatiecoefficient_weigert_lege_of_niet_positieve_rij():
    with pytest.raises(ValueError):
        variatiecoefficient([])
    with pytest.raises(ValueError):
        variatiecoefficient([1.0, 0.0])


def test_voorbeeld_sso_postenbestand_is_geldig_en_reproduceerbaar():
    regels = [("A", "E", 400, 500.0), ("B", "E", 300, 500.0), ("B", "I", 200, 800.0)]
    a = maak_voorbeeld_sso_postenbestand(regels)
    b = maak_voorbeeld_sso_postenbestand(regels)
    pd.testing.assert_frame_equal(a, b)
    gelezen = lees_postenbestand(postenbestand_csv(a), meerdere_klanten=True)
    assert len(gelezen) == 900
    assert gelezen["klant"].nunique() == 2
    gem = gelezen[gelezen["type_post"] == "E"]["bedrag_cent"].mean() / 100
    assert gem == pytest.approx(500, rel=0.2)


def test_voorbeeld_sso_postenbestand_weigert_lege_invoer():
    with pytest.raises(ValueError):
        maak_voorbeeld_sso_postenbestand([])
