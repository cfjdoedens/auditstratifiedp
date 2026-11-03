"""Maandbestanden met de posten van één klant: genereren, inlezen en samenvatten.

Een maandbestand is een afzonderlijke postadministratie (één klant, één
kalendermaand), niet het SSO-invoerformaat uit ``invoer_csv``. Kolommen, in
deze volgorde: ``klant;datum;post_id;type_post;bedrag``. Het scheidingsteken is
een puntkomma; datums zijn JJJJ-MM-DD; bedragen staan in euro's met maximaal
twee decimalen (komma of punt als decimaalteken, geen duizendtalscheiding).

Bedragen worden bij het inlezen exact omgezet naar gehele eurocenten
(kolom ``bedrag_cent``), zodat sommen geen afrondingsverlies hebben.
"""

import calendar
import csv
import io
import re
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd

MAAND_KOLOMMEN = ("klant", "datum", "post_id", "type_post", "bedrag")
MAX_BYTES = 20_000_000
MAX_POSTEN = 100_000

_BEDRAG = re.compile(r"\d+(?:[,.]\d{1,2})?")
_DATUM = re.compile(r"\d{4}-\d{2}-\d{2}")


def maak_voorbeeld_maandbestand(
    klant: str,
    jaar: int,
    maand: int,
    aantal: int,
    typen: list[str],
    seed: int = 2026,
) -> pd.DataFrame:
    """Reproduceerbare fictieve posten met bedragen op twee decimalen.

    De (lognormale) bedragen zijn verzonnen en dienen alleen als voorbeeld; ze
    vormen geen statistische aanname.
    """
    if not klant.strip() or not typen or not 1 <= maand <= 12 or aantal < 1:
        raise ValueError(
            "Geef een klant, posttype, geldige maand en positief aantal op."
        )
    rng = np.random.default_rng(seed)
    dagen = calendar.monthrange(jaar, maand)[1]
    datums = rng.integers(1, dagen + 1, size=aantal)
    type_idx = rng.integers(0, len(typen), size=aantal)
    centen = np.maximum(
        1, np.rint(rng.lognormal(np.log(500), 0.9, aantal) * 100)
    ).astype("int64")
    df = pd.DataFrame({
        "klant": klant.strip(),
        "datum": [f"{jaar:04d}-{maand:02d}-{d:02d}" for d in datums],
        "post_id": [f"{jaar:04d}{maand:02d}-{i:06d}" for i in range(1, aantal + 1)],
        "type_post": [typen[i] for i in type_idx],
        "bedrag": [f"{c / 100:.2f}".replace(".", ",") for c in centen],
    })
    return df.sort_values(["datum", "post_id"]).reset_index(drop=True)


def maandbestand_csv(df: pd.DataFrame) -> bytes:
    """Schrijf een maandbestand als CSV (puntkomma, UTF-8 met BOM voor Excel)."""
    return (
        df[list(MAAND_KOLOMMEN)]
        .to_csv(index=False, sep=";", quoting=csv.QUOTE_MINIMAL)
        .encode("utf-8-sig")
    )


def lees_maandbestand(data: bytes) -> pd.DataFrame:
    """Lees en valideer een maandbestand; gooit ``ValueError`` bij de eerste fout.

    Het resultaat heeft de kolommen van ``MAAND_KOLOMMEN`` (als tekst) plus
    ``bedrag_cent`` (geheel aantal eurocenten).
    """
    if len(data) > MAX_BYTES:
        raise ValueError("Het maandbestand mag maximaal 20 MB groot zijn.")
    try:
        df = pd.read_csv(
            io.BytesIO(data),
            sep=";",
            dtype=str,
            encoding="utf-8-sig",
            keep_default_na=False,
        )
    except (UnicodeError, pd.errors.ParserError, ValueError) as exc:
        raise ValueError(f"CSV kan niet worden gelezen: {exc}") from exc
    if tuple(df.columns) != MAAND_KOLOMMEN:
        raise ValueError(
            "Verwachte kolommen (in deze volgorde): " + ";".join(MAAND_KOLOMMEN)
        )
    if df.empty:
        raise ValueError("Het maandbestand bevat geen posten.")
    if len(df) > MAX_POSTEN:
        raise ValueError("Het maandbestand mag maximaal 100.000 posten bevatten.")
    for kolom in MAAND_KOLOMMEN:
        df[kolom] = df[kolom].str.strip()
        if df[kolom].eq("").any():
            raise ValueError(f"Lege waarden in kolom '{kolom}'.")
    if df["post_id"].duplicated().any():
        raise ValueError("De kolom post_id bevat dubbele identificaties.")
    datums = pd.to_datetime(df["datum"], format="%Y-%m-%d", errors="coerce")
    if datums.isna().any() or not df["datum"].str.fullmatch(_DATUM.pattern).all():
        raise ValueError("Ongeldige datum; gebruik JJJJ-MM-DD.")
    if df["klant"].nunique() != 1:
        raise ValueError("Een maandbestand mag slechts één klant bevatten.")
    if datums.dt.to_period("M").nunique() != 1:
        raise ValueError("Een maandbestand mag slechts één kalendermaand bevatten.")
    centen = []
    for i, waarde in enumerate(df["bedrag"], 1):
        if not _BEDRAG.fullmatch(waarde):
            raise ValueError(f"Ongeldig bedrag op rij {i}: '{waarde}'.")
        try:
            cents = Decimal(waarde.replace(",", ".")) * 100
        except InvalidOperation as exc:
            raise ValueError(f"Ongeldig bedrag op rij {i}.") from exc
        if cents <= 0:
            raise ValueError(f"Bedrag op rij {i} moet positief zijn.")
        centen.append(int(cents))
    df["bedrag_cent"] = centen
    return df


def maandtotalen_per_type_post(df: pd.DataFrame) -> pd.DataFrame:
    """Aantal posten en totaal bedrag (eurocenten en euro's) per type post.

    Kolommen: ``type_post``, ``N_klant``, ``bedrag_cent``, ``waarde_laag``.
    Het zijn maandtotalen, geen jaar- of SSO-populatietotalen.
    """
    totalen = df.groupby("type_post", as_index=False).agg(
        N_klant=("post_id", "size"), bedrag_cent=("bedrag_cent", "sum")
    )
    totalen["waarde_laag"] = totalen["bedrag_cent"] / 100
    return totalen
