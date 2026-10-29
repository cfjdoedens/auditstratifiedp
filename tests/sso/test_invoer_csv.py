import pandas as pd
import pytest

from auditstat.sso.invoer_csv import lees_sso_invoer_csv, maak_sso_invoer_csv

INSTELLINGEN = {
    "model": "binomiaal",
    "zekerheid": "0,95",
    "berekeningsmethode": "momentmatching",
    "onderscheid": "ja",
}
TOTAAL = {
    "n": "200",
    "k": "4",
    "N_totaal": "5.000",
    "massa": "2.500.000,00",
    "ihr": "H",
    "ibr": "M",
    "car": "L",
    "materialiteit": "0,01",
}


@pytest.fixture
def klanten():
    return pd.DataFrame({
        "klant": ["Klant A", "Klant B"],
        "N_klant": ["3.000", "2.000"],
        "waarde_laag": ["1.500.000,00", "1.000.000,00"],
    })


@pytest.fixture
def typen_posten():
    return pd.DataFrame({
        "naam": ["Emolumenten", "Inkoopfacturen"],
        "n": ["120", "80"],
        "k": ["1", "3"],
        "ihr": ["H", "H"],
        "ibr": ["H", "M"],
        "car": ["H", "L"],
        "materialiteit": ["0,01", ""],
    })


@pytest.fixture
def klanten_typen():
    return pd.DataFrame({
        "klant": ["Klant A", "Klant A", "Klant B", "Klant B"],
        "type_post": ["Emolumenten", "Inkoopfacturen"] * 2,
        "N_klant": ["1.800", "1.200", "1.200", "800"],
        "waarde_laag": [
            "900.000,00",
            "600.000,00",
            "600.000,00",
            "400.000,00",
        ],
    })


@pytest.fixture
def csv_tekst(klanten, typen_posten, klanten_typen):
    return maak_sso_invoer_csv(
        INSTELLINGEN, TOTAAL, klanten, typen_posten, klanten_typen
    )


def _vervang(tekst, oud, nieuw):
    assert oud in tekst
    return tekst.replace(oud, nieuw)


def test_export_gebruikt_puntkomma_en_nl_getallen(csv_tekst):
    regels = csv_tekst.splitlines()
    assert regels[0] == "onderdeel;klant;type_post;veld;waarde"
    assert "totaal;;;massa;2.500.000,00" in regels
    assert "klant;Klant A;;N_klant;3.000" in regels
    assert "klant_type_post;Klant B;Inkoopfacturen;waarde_laag;400.000,00" in regels


def test_roundtrip_geeft_dezelfde_invoer(
    csv_tekst, klanten, typen_posten, klanten_typen
):
    res = lees_sso_invoer_csv(csv_tekst)
    assert res["instellingen"] == INSTELLINGEN
    assert res["totaal"] == TOTAAL
    pd.testing.assert_frame_equal(res["klanten"], klanten)
    pd.testing.assert_frame_equal(res["typen_posten"], typen_posten)
    pd.testing.assert_frame_equal(res["klanten_typen"], klanten_typen)


def test_inlezen_van_bytes_met_bom_zoals_excel_ze_schrijft(csv_tekst):
    res = lees_sso_invoer_csv(csv_tekst.encode("utf-8-sig"))
    assert res["totaal"]["n"] == "200"


def test_inlezen_met_komma_als_scheidingsteken_en_windows_regeleinden():
    tekst = "onderdeel,klant,type_post,veld,waarde\r\ninstelling,,,model,poisson\r\n"
    res = lees_sso_invoer_csv(tekst)
    assert res["instellingen"] == {"model": "poisson"}
    assert res["klanten"] is None


def test_lege_tabelrijen_worden_niet_geexporteerd(klanten, typen_posten):
    klanten = pd.concat([
        klanten,
        pd.DataFrame({"klant": [""], "N_klant": [""], "waarde_laag": [""]}),
    ])
    lege_klanten_typen = pd.DataFrame(
        columns=["klant", "type_post", "N_klant", "waarde_laag"]
    )
    tekst = maak_sso_invoer_csv(
        {**INSTELLINGEN, "onderscheid": "nee"},
        TOTAAL,
        klanten,
        typen_posten,
        lege_klanten_typen,
    )
    klantregels = [r for r in tekst.splitlines() if r.startswith("klant;")]
    assert len(klantregels) == 4  # 2 klanten x 2 velden
    assert "klant_type_post" not in tekst


def test_materialiteit_mag_leeg_blijven(csv_tekst):
    res = lees_sso_invoer_csv(csv_tekst)
    assert res["typen_posten"].loc[1, "materialiteit"] == ""


def test_punt_decimaal_wordt_geweigerd(csv_tekst):
    tekst = _vervang(
        csv_tekst, "totaal;;;massa;2.500.000,00", "totaal;;;massa;2500000.50"
    )
    with pytest.raises(ValueError, match="Nederlandse notatie"):
        lees_sso_invoer_csv(tekst)


def test_ongeldig_risico_en_model_geven_elk_een_melding(csv_tekst):
    tekst = _vervang(csv_tekst, "totaal;;;ihr;H", "totaal;;;ihr;X")
    tekst = _vervang(
        tekst, "instelling;;;model;binomiaal", "instelling;;;model;normaal"
    )
    with pytest.raises(ValueError) as exc:
        lees_sso_invoer_csv(tekst)
    assert "ihr" in str(exc.value) and "model" in str(exc.value)
    assert str(exc.value).count("Regel") == 2


def test_onbekend_onderdeel_en_veld(csv_tekst):
    with pytest.raises(ValueError, match="onbekend onderdeel"):
        lees_sso_invoer_csv(csv_tekst + "bonus;;;x;1\n")
    with pytest.raises(ValueError, match="onbekend veld"):
        lees_sso_invoer_csv(csv_tekst + "totaal;;;kleur;rood\n")


def test_verkeerde_kop(csv_tekst):
    tekst = _vervang(csv_tekst, "onderdeel;klant;type_post;veld;waarde", "a;b;c;d;e")
    with pytest.raises(ValueError, match="Ongeldige kop"):
        lees_sso_invoer_csv(tekst)


def test_leeg_bestand():
    with pytest.raises(ValueError, match="leeg"):
        lees_sso_invoer_csv("")


def test_dubbele_regel(csv_tekst):
    with pytest.raises(ValueError, match="dubbele regel"):
        lees_sso_invoer_csv(csv_tekst + "totaal;;;n;200\n")


def test_klant_of_type_post_verkeerd_ingevuld(csv_tekst):
    with pytest.raises(ValueError, match='kolom "klant" moet'):
        lees_sso_invoer_csv(csv_tekst + "totaal;Klant A;;n;5\n")
    with pytest.raises(ValueError, match='kolom "type_post" moet'):
        lees_sso_invoer_csv(csv_tekst + "klant;Klant C;Emolumenten;N_klant;5\n")


def test_ontbrekend_verplicht_veld_bij_klant(csv_tekst):
    tekst = _vervang(csv_tekst, "klant;Klant B;;waarde_laag;1.000.000,00\n", "")
    with pytest.raises(ValueError, match="veld waarde_laag ontbreekt"):
        lees_sso_invoer_csv(tekst)


def test_lege_verplichte_waarde(csv_tekst):
    tekst = _vervang(csv_tekst, "totaal;;;n;200", "totaal;;;n;")
    with pytest.raises(ValueError, match="waarde ontbreekt"):
        lees_sso_invoer_csv(tekst)


def test_klant_type_post_verwijst_naar_onbekend_type_post(csv_tekst):
    tekst = csv_tekst + (
        "klant_type_post;Klant A;Onbekend;N_klant;1\n"
        "klant_type_post;Klant A;Onbekend;waarde_laag;1\n"
    )
    with pytest.raises(ValueError, match='type post "Onbekend"'):
        lees_sso_invoer_csv(tekst)


def test_onderscheid_ja_vereist_de_detailtabellen(klanten, typen_posten):
    leeg = pd.DataFrame(columns=["klant", "type_post", "N_klant", "waarde_laag"])
    tekst = maak_sso_invoer_csv(INSTELLINGEN, TOTAAL, klanten, typen_posten, leeg)
    with pytest.raises(ValueError, match="onderscheid"):
        lees_sso_invoer_csv(tekst)


def test_onderscheid_nee_zonder_detailtabellen_is_toegestaan(klanten):
    leeg_t = pd.DataFrame(
        columns=["naam", "n", "k", "ihr", "ibr", "car", "materialiteit"]
    )
    leeg_k = pd.DataFrame(columns=["klant", "type_post", "N_klant", "waarde_laag"])
    tekst = maak_sso_invoer_csv(
        {**INSTELLINGEN, "onderscheid": "nee"}, TOTAAL, klanten, leeg_t, leeg_k
    )
    res = lees_sso_invoer_csv(tekst)
    assert res["typen_posten"] is None and res["klanten_typen"] is None
    assert len(res["klanten"]) == 2
