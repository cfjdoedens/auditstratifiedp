"""Postenbestanden met de posten van één klant: genereren, inlezen en samenvatten.

Een postenbestand bevat voorbeeldposten (of een echte postadministratie) om de
grootten van de posten te bekijken. Het is niet het SSO-invoerformaat uit
``invoer_csv``. Kolommen, in deze volgorde: ``klant;post_id;type_post;bedrag``.
Het scheidingsteken is een puntkomma; bedragen staan in euro's met maximaal
twee decimalen (komma of punt als decimaalteken, geen duizendtalscheiding).

Bedragen worden bij het inlezen exact omgezet naar gehele eurocenten
(kolom ``bedrag_cent``), zodat sommen geen afrondingsverlies hebben.
"""

import csv
import io
import re
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd

POSTEN_KOLOMMEN = ("klant", "post_id", "type_post", "bedrag")
MAX_BYTES = 20_000_000
MAX_POSTEN = 100_000

_BEDRAG = re.compile(r"\d+(?:[,.]\d{1,2})?")


def maak_voorbeeld_postenbestand(
    klant: str,
    aantal: int,
    typen: list[str],
    seed: int = 2026,
) -> pd.DataFrame:
    """Reproduceerbare fictieve posten met bedragen op twee decimalen.

    De (lognormale) bedragen zijn verzonnen en dienen alleen als voorbeeld; ze
    vormen geen statistische aanname.
    """
    if not klant.strip() or not typen or aantal < 1:
        raise ValueError("Geef een klant, posttype en positief aantal op.")
    rng = np.random.default_rng(seed)
    type_idx = rng.integers(0, len(typen), size=aantal)
    centen = np.maximum(
        1, np.rint(rng.lognormal(np.log(500), 0.9, aantal) * 100)
    ).astype("int64")
    return pd.DataFrame({
        "klant": klant.strip(),
        "post_id": [f"P{i:06d}" for i in range(1, aantal + 1)],
        "type_post": [typen[i] for i in type_idx],
        "bedrag": [f"{c / 100:.2f}".replace(".", ",") for c in centen],
    })


def maak_voorbeeld_sso_postenbestand(
    regels: list[tuple[str, str, int, float]],
    sigma: float = 0.9,
    seed: int = 2026,
) -> pd.DataFrame:
    """Reproduceerbaar fictief postenbestand van de hele SSO (meerdere klanten).

    ``regels`` bevat per (klant, type post) het aantal posten en het
    gewenste gemiddelde bedrag; de bedragen zijn lognormaal met
    log-standaardafwijking ``sigma`` en verwachting gelijk aan dat
    gemiddelde. Alleen bedoeld als voorbeeld, geen statistische aanname.
    """
    if not regels or sigma <= 0:
        raise ValueError("Geef minstens één regel en een positieve sigma op.")
    rng = np.random.default_rng(seed)
    delen = []
    for klant, type_post, aantal, gemiddelde in regels:
        if not klant.strip() or not type_post.strip() or aantal < 1 or gemiddelde <= 0:
            raise ValueError(
                "Elke regel heeft een klant, type post, positief aantal en gemiddelde nodig."
            )
        mu = np.log(gemiddelde) - sigma**2 / 2
        centen = np.maximum(
            1, np.rint(rng.lognormal(mu, sigma, int(aantal)) * 100)
        ).astype("int64")
        delen.append(
            pd.DataFrame({
                "klant": klant.strip(),
                "type_post": type_post.strip(),
                "bedrag": [f"{c / 100:.2f}".replace(".", ",") for c in centen],
            })
        )
    df = pd.concat(delen, ignore_index=True)
    df.insert(1, "post_id", [f"P{i:06d}" for i in range(1, len(df) + 1)])
    return df[list(POSTEN_KOLOMMEN)]


def postenbestand_csv(df: pd.DataFrame) -> bytes:
    """Schrijf een postenbestand als CSV (puntkomma, UTF-8 met BOM voor Excel)."""
    return (
        df[list(POSTEN_KOLOMMEN)]
        .to_csv(index=False, sep=";", quoting=csv.QUOTE_MINIMAL)
        .encode("utf-8-sig")
    )


MAX_BYTES_SSO = 50_000_000
MAX_POSTEN_SSO = 1_000_000


def lees_postenbestand(data: bytes, meerdere_klanten: bool = False) -> pd.DataFrame:
    """Lees en valideer een postenbestand; gooit ``ValueError`` bij de eerste fout.

    Het resultaat heeft de kolommen van ``POSTEN_KOLOMMEN`` (als tekst) plus
    ``bedrag_cent`` (geheel aantal eurocenten).

    Met ``meerdere_klanten=True`` (postenbestand van de hele SSO) mag het
    bestand meerdere klanten bevatten en gelden ruimere limieten
    (``MAX_BYTES_SSO``, ``MAX_POSTEN_SSO``).
    """
    max_bytes = MAX_BYTES_SSO if meerdere_klanten else MAX_BYTES
    max_posten = MAX_POSTEN_SSO if meerdere_klanten else MAX_POSTEN
    if len(data) > max_bytes:
        raise ValueError(
            f"Het postenbestand mag maximaal {max_bytes // 1_000_000} MB groot zijn."
        )
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
    if tuple(df.columns) != POSTEN_KOLOMMEN:
        raise ValueError(
            "Verwachte kolommen (in deze volgorde): " + ";".join(POSTEN_KOLOMMEN)
        )
    if df.empty:
        raise ValueError("Het postenbestand bevat geen posten.")
    if len(df) > max_posten:
        raise ValueError(
            f"Het postenbestand mag maximaal {max_posten:,} posten bevatten.".replace(
                ",", "."
            )
        )
    for kolom in POSTEN_KOLOMMEN:
        df[kolom] = df[kolom].str.strip()
        if df[kolom].eq("").any():
            raise ValueError(f"Lege waarden in kolom '{kolom}'.")
    if df["post_id"].duplicated().any():
        raise ValueError("De kolom post_id bevat dubbele identificaties.")
    if not meerdere_klanten and df["klant"].nunique() != 1:
        raise ValueError("Een postenbestand mag slechts één klant bevatten.")
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


def totalen_per_type_post(df: pd.DataFrame) -> pd.DataFrame:
    """Aantal posten en totaal bedrag (eurocenten en euro's) per type post.

    Kolommen: ``type_post``, ``N_klant``, ``bedrag_cent``, ``waarde_laag``.
    Het zijn totalen van dit bestand, niet noodzakelijk de populatietotalen.
    """
    totalen = df.groupby("type_post", as_index=False).agg(
        N_klant=("post_id", "size"), bedrag_cent=("bedrag_cent", "sum")
    )
    totalen["waarde_laag"] = totalen["bedrag_cent"] / 100
    return totalen


def postgroottes_per_type_post(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Postbedragen (euro's) per type post, uit een postenbestand.

    Voor niveau 3 van de SSO-evaluatie: de empirische verdeling van de
    postgroottes per type post.
    """
    return {
        type_post: groep["bedrag_cent"].to_numpy(dtype=float) / 100
        for type_post, groep in df.groupby("type_post")
    }


def variatiecoefficient(waarden) -> float:
    """Variatiecoëfficiënt (standaardafwijking / gemiddelde) van postbedragen.

    Gebruikt de populatiestandaardafwijking (``ddof=0``): het bestand wordt
    opgevat als de populatie van posten.
    """
    waarden = np.asarray(waarden, dtype=float)
    if waarden.size == 0 or not np.all(waarden > 0):
        raise ValueError(
            "Postbedragen moeten een niet-lege rij positieve getallen zijn."
        )
    return float(waarden.std() / waarden.mean())
