import pytest

from auditstat.lokaal_bestanden import (
    is_lokaal_verzoek,
    lees_lokaal_bestand,
    schrijf_lokaal_bestand,
)


@pytest.mark.parametrize(
    ("ip", "host", "verwacht"),
    [
        (None, "localhost:8501", True),
        (None, "127.0.0.1:8501", True),
        (None, "[::1]:8501", True),
        (None, "LOCALHOST", True),
        ("127.0.0.1", "localhost:8501", True),
        ("::ffff:127.0.0.1", "localhost", True),
        # Andere computer in hetzelfde netwerk.
        ("192.168.1.20", "localhost:8501", False),
        ("192.168.1.20", "192.168.1.5:8501", False),
        # Cloud: echt adres en eigen domein.
        ("84.12.3.4", "app.streamlit.app", False),
        # Achter een proxy die lokaal verbindt, maar met een publiek domein.
        (None, "app.streamlit.app", False),
        (None, "localhost.evil.com", False),
        (None, None, False),
        (None, "", False),
        ("onzin", "localhost", False),
    ],
)
def test_is_lokaal_verzoek(ip, host, verwacht):
    assert is_lokaal_verzoek(ip, host) is verwacht


def test_lees_lokaal_bestand(tmp_path):
    f = tmp_path / "posten.csv"
    f.write_bytes(b"a;b\n1;2\n")
    assert lees_lokaal_bestand(str(f)) == ("posten.csv", b"a;b\n1;2\n")
    # Aanhalingstekens (kopiëren als pad in Windows) en spaties worden genegeerd.
    assert lees_lokaal_bestand(f'  "{f}"  ')[0] == "posten.csv"


@pytest.mark.parametrize("pad", ["", "   "])
def test_lees_leeg_pad(pad):
    with pytest.raises(ValueError, match="Geen pad"):
        lees_lokaal_bestand(pad)


def test_lees_ontbrekend_en_map(tmp_path):
    with pytest.raises(ValueError, match="niet gevonden"):
        lees_lokaal_bestand(str(tmp_path / "bestaat_niet.csv"))
    with pytest.raises(ValueError, match="geen bestand"):
        lees_lokaal_bestand(str(tmp_path))


def test_lees_te_groot(tmp_path):
    f = tmp_path / "x.csv"
    f.write_bytes(b"x" * 11)
    with pytest.raises(ValueError, match="maximaal"):
        lees_lokaal_bestand(str(f), max_bytes=10)


def test_schrijf_en_weiger_overschrijven(tmp_path):
    pad = tmp_path / "uit.csv"
    resultaat = schrijf_lokaal_bestand(str(pad), b"abc")
    assert resultaat == pad.resolve()
    assert pad.read_bytes() == b"abc"
    with pytest.raises(ValueError, match="bestaat al"):
        schrijf_lokaal_bestand(str(pad), b"nieuw")
    assert pad.read_bytes() == b"abc"
    schrijf_lokaal_bestand(str(pad), b"nieuw", overschrijven=True)
    assert pad.read_bytes() == b"nieuw"


def test_schrijf_fouten(tmp_path):
    with pytest.raises(ValueError, match="Geen pad"):
        schrijf_lokaal_bestand("", b"")
    with pytest.raises(ValueError, match="map, geen bestand"):
        schrijf_lokaal_bestand(str(tmp_path), b"")
    with pytest.raises(ValueError, match="map bestaat niet"):
        schrijf_lokaal_bestand(str(tmp_path / "nep" / "x.csv"), b"")
