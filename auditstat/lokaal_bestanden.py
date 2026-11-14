"""Lokale bestanden voor de Streamlit-app: alleen als de app lokaal draait.

Als de app op de eigen computer draait, kan de gebruiker bestanden van het
lokale bestandssysteem kiezen (inlezen) en wegschrijven (opslaan), naast de
gewone up- en download via de browser. Op een server (bijvoorbeeld Streamlit
Cloud) mag dit nooit beschikbaar zijn: een pad is daar een pad op de server.

De herkenning van "lokaal" staat los van Streamlit in :func:`is_lokaal_verzoek`
zodat ze testbaar is. Streamlit geeft ``st.context.ip_address`` als ``None``
voor een verbinding via localhost; elk ander adres betekent een andere
computer. Daarnaast moet de ``Host``-header naar localhost wijzen.
"""

from __future__ import annotations

import importlib.util
import ipaddress
import os
import subprocess
import sys
from pathlib import Path

# Ruime bovengrens voor het inlezen van een lokaal bestand; de functie die
# het bestand verwerkt heeft meestal een strengere eigen grens.
MAX_LEES_BYTES = 500_000_000

_DIALOOG_CODE = """
import sys
import tkinter
from tkinter import filedialog

modus, titel, naam, map_, typen = sys.argv[1:6]
wortel = tkinter.Tk()
wortel.withdraw()
try:
    wortel.attributes("-topmost", True)
except Exception:
    pass
bestandstypen = [
    (t.upper() + "-bestand", "*." + t) for t in typen.split(",") if t
] + [("Alle bestanden", "*")]
opties = dict(title=titel, initialdir=map_ or None, filetypes=bestandstypen)
if modus == "open":
    pad = filedialog.askopenfilename(**opties)
else:
    pad = filedialog.asksaveasfilename(
        initialfile=naam,
        defaultextension="." + typen.split(",")[0] if typen else "",
        **opties,
    )
wortel.destroy()
sys.stdout.write(str(pad or ""))
"""


def _is_loopback_host(host: str) -> bool:
    """Is de hostnaam (zonder poort) localhost of een loopbackadres?"""
    naam = host.strip().lower()
    if naam.startswith("["):  # IPv6 met poort: [::1]:8501
        naam = naam[1:].split("]")[0]
    elif naam.count(":") == 1:  # naam:poort
        naam = naam.split(":")[0]
    if naam == "localhost":
        return True
    try:
        adres = ipaddress.ip_address(naam)
    except ValueError:
        return False
    return adres.is_loopback


def is_lokaal_verzoek(ip: str | None, host: str | None) -> bool:
    """Komt het verzoek van de eigen computer?

    ``ip`` is ``st.context.ip_address`` (``None`` bij localhost), ``host`` de
    ``Host``-header. Beide moeten op lokaal gebruik wijzen.
    """
    if not host or not _is_loopback_host(host):
        return False
    if ip is None:
        return True
    try:
        adres = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(adres, ipaddress.IPv6Address) and adres.ipv4_mapped:
        adres = adres.ipv4_mapped
    return adres.is_loopback


def dialoog_beschikbaar() -> bool:
    """Is een systeem-bestandsvenster (tkinter) bruikbaar op deze computer?"""
    if importlib.util.find_spec("tkinter") is None:
        return False
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def _toon_dialoog(
    modus: str, titel: str, naam: str, map_: str, typen: tuple[str, ...]
) -> str | None:
    """Open het systeemvenster in een los proces; ``None`` bij annuleren."""
    if not dialoog_beschikbaar():
        raise RuntimeError("Het bestandsvenster is op deze computer niet beschikbaar.")
    resultaat = subprocess.run(
        [
            sys.executable,
            "-c",
            _DIALOOG_CODE,
            modus,
            titel,
            naam,
            map_,
            ",".join(typen),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if resultaat.returncode != 0:
        raise RuntimeError(
            "Het bestandsvenster kon niet worden geopend: "
            + (resultaat.stderr.strip().splitlines() or ["onbekende fout"])[-1]
        )
    pad = resultaat.stdout.strip()
    return pad or None


def kies_bestand_dialoog(
    titel: str = "Kies een bestand", typen: tuple[str, ...] = ("csv",)
) -> str | None:
    """Laat de gebruiker een bestaand bestand kiezen; ``None`` bij annuleren."""
    return _toon_dialoog("open", titel, "", str(Path.home()), typen)


def kies_opslaan_dialoog(
    titel: str = "Opslaan als",
    standaardnaam: str = "",
    typen: tuple[str, ...] = ("csv",),
) -> str | None:
    """Laat de gebruiker een opslagplek kiezen; ``None`` bij annuleren.

    Het systeemvenster vraagt zelf om bevestiging bij een bestaand bestand.
    """
    return _toon_dialoog("opslaan", titel, standaardnaam, str(Path.home()), typen)


def lees_lokaal_bestand(pad: str, max_bytes: int = MAX_LEES_BYTES) -> tuple[str, bytes]:
    """Lees een lokaal bestand; geeft ``(bestandsnaam, inhoud)``.

    Gooit ``ValueError`` met een begrijpelijke melding als het pad leeg is,
    niet bestaat, geen bestand is, te groot is of niet te lezen is.
    """
    if not pad or not pad.strip():
        raise ValueError("Geen pad ingevuld.")
    bestand = Path(pad.strip().strip('"')).expanduser()
    if not bestand.exists():
        raise ValueError(f"Bestand niet gevonden: {bestand}")
    if not bestand.is_file():
        raise ValueError(f"Dit pad is geen bestand: {bestand}")
    grootte = bestand.stat().st_size
    if grootte > max_bytes:
        raise ValueError(
            f"Het bestand is {grootte / 1_000_000:.0f} MB; "
            f"maximaal {max_bytes // 1_000_000} MB."
        )
    try:
        return bestand.name, bestand.read_bytes()
    except OSError as fout:
        raise ValueError(f"Het bestand kon niet worden gelezen: {fout}") from fout


def schrijf_lokaal_bestand(pad: str, data: bytes, overschrijven: bool = False) -> Path:
    """Schrijf ``data`` naar ``pad``; geeft het volledige pad terug.

    Gooit ``ValueError`` bij een leeg pad, een bestaande map of een bestaand
    bestand (tenzij ``overschrijven``), een ontbrekende map of een
    schrijffout. Een map wordt niet aangemaakt.
    """
    if not pad or not pad.strip():
        raise ValueError("Geen pad ingevuld.")
    bestand = Path(pad.strip().strip('"')).expanduser()
    if bestand.is_dir():
        raise ValueError(f"Dit pad is een map, geen bestand: {bestand}")
    if not bestand.parent.is_dir():
        raise ValueError(f"De map bestaat niet: {bestand.parent}")
    if bestand.exists() and not overschrijven:
        raise ValueError(
            f"Het bestand bestaat al: {bestand}. Kies een andere naam of "
            "gebruik Bladeren\u2026."
        )
    try:
        bestand.write_bytes(data)
    except OSError as fout:
        raise ValueError(f"Het bestand kon niet worden opgeslagen: {fout}") from fout
    return bestand.resolve()
