import inspect
import math
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import streamlit as st

# Een langlopend proces (bijv. Streamlit Cloud na een nieuwe push) kan oudere
# versies van de auditstat-modules in het geheugen houden dan deze app
# verwacht, wat een ImportError geeft. Bij een eerste mislukking worden de
# auditstat-modules uit het geheugen gehaald en opnieuw geladen; lukt het dan
# nog niet, dan volgt een duidelijke herstartmelding.
for _poging in (1, 2):
    try:
        from auditstat.sso.evalueer_SSO_klant_gestratificeerd import (  # pyrefly: ignore[missing-import]
            evalueer_SSO_klant_gestratificeerd,
        )
        from auditstat.sso.evalueer_SSO_totaal import (  # pyrefly: ignore[missing-import]
            HELE_SSO_NAAM,
            KLANTEN_SAMEN_NAAM,
            evalueer_SSO_totaal,
            is_gereserveerde_klantnaam,
            klanten_samen,
        )
        from auditstat.sso.invoer_csv import (  # pyrefly: ignore[missing-import]
            lees_sso_invoer_csv,
            maak_sso_invoer_csv,
        )
        from auditstat.sso.schema_figuren import (  # pyrefly: ignore[missing-import]
            THEORIE_FIGUREN,
        )
        from auditstat.sso.theorie_qmd import (  # pyrefly: ignore[missing-import]
            lees_theorie_qmd,
        )
        from auditstat.stratified.eval_stratified import (  # pyrefly: ignore[missing-import]
            eval_stratified,
        )
        from auditstat.stratified.plan_stratified import (  # pyrefly: ignore[missing-import]
            plan_stratified_basis,
            vind_beste_strata_groep,
        )
        from auditstat.stratified.plot_kanskromme import (  # pyrefly: ignore[missing-import]
            plot_kanskromme,
        )
        from auditstat.stratified.utils import (  # pyrefly: ignore[missing-import]
            foutloze_posten_equivalent,
            haro_nog_nodige_zekerheid,
        )

        try:
            from auditstat.sso.rapport_pdf import (  # pyrefly: ignore[missing-import]
                maak_sso_rapport_pdf,
            )
        except ImportError as _fout:
            # reportlab is optioneel: pip install auditstat[pdf]. Een andere
            # ImportError (bijv. een verouderde module) mag niet worden
            # verborgen en gaat naar de herstartlogica hieronder.
            if (_fout.name or "").split(".")[0] != "reportlab":
                raise
            maak_sso_rapport_pdf = None
        break
    except ImportError as _fout:
        if _poging == 2:
            st.set_page_config(page_title="auditstat", layout="wide")
            st.error(
                "De app kan een deel van het auditstat-pakket niet laden, "
                "waarschijnlijk omdat het draaiende proces nog een oudere "
                "versie van het pakket in het geheugen heeft. Herstart de "
                "app (lokaal: stop en start Streamlit opnieuw; op Streamlit "
                "Cloud: Manage app \u2192 Reboot app) en probeer het opnieuw."
            )
            st.caption(f"Technische melding: {_fout}")
            st.stop()
        for _naam in [
            m for m in sys.modules if m == "auditstat" or m.startswith("auditstat.")
        ]:
            del sys.modules[_naam]

# Configureer de pagina lay-out en titel van de Streamlit webapplicatie.
st.set_page_config(page_title="auditstat", layout="wide")

# Definieer de risicocategorieën en de bijbehorende gebruikerslabels voor de selectievelden.
RISK_OPTIES = ["H", "M", "L"]
RISK_LABELS = {"H": "hoog (H)", "M": "midden (M)", "L": "laag (L)"}

# Bereid een leeg sjabloon-dataframe voor om de invoertabel voor de evaluatie te initialiseren.
LEGE_EVAL_DF = pd.DataFrame({
    "naam": [""] * 8,
    "waarde_laag": [""] * 8,
    "n_laag": [""] * 8,
    "k_laag": [""] * 8,
    "ihr": ["H"] * 8,
    "ibr": ["H"] * 8,
    "car": ["H"] * 8,
    "waarde_hoog": ["0"] * 8,
    "fout_hoog": ["0"] * 8,
    "materialiteit": ["0,01"] * 8,
})

# Bereid een leeg sjabloon-dataframe voor om de invoertabel voor de planning te initialiseren.
LEGE_PLAN_DF = pd.DataFrame({
    "naam": [""] * 8,
    "waarde_laag": [""] * 8,
    "verwachte_foutfractie": ["0,001"] * 8,
    "ihr": ["H"] * 8,
    "ibr": ["H"] * 8,
    "car": ["H"] * 8,
    "kosten": ["1,0"] * 8,
    "waarde_hoog": ["0"] * 8,
    "fout_hoog": ["0"] * 8,
    "materialiteit": ["0,01"] * 8,
    "n_laag": [None] * 8,
    "n_laag_extra": [None] * 8,
    "n_laag_tot": [None] * 8,
})

# Bereid lege sjabloon-dataframes voor om de invoertabellen voor de
# gestratificeerde SSO-evaluatie te initialiseren. De SSO-brede typen posten
# (n, k, risico-inschatting, materialiteit) worden één keer ingevuld en
# gelden voor alle klanten; de klantentabel koppelt daar per klant alleen
# nog N_klant en waarde_laag aan (lang/tidy-formaat: één rij per
# klant×type-post-combinatie).
LEGE_SSO_TYPEN_POSTEN_DF = pd.DataFrame({
    "naam": ["Emolumenten", "Inkoopfacturen"],
    "n": ["120", "80"],
    "k": ["1", "3"],
    "ihr": ["H", "H"],
    "ibr": ["H", "H"],
    "car": ["H", "H"],
    "materialiteit": ["0,01", "0,01"],
})

LEGE_SSO_KLANTEN_DF = pd.DataFrame({
    "klant": ["Klant A", "Klant A", "Klant B", "Klant B"],
    "type_post": ["Emolumenten", "Inkoopfacturen", "Emolumenten", "Inkoopfacturen"],
    "N_klant": ["1.800", "1.200", "1.200", "800"],
    "waarde_laag": ["900.000,00", "600.000,00", "600.000,00", "400.000,00"],
})

# Vereenvoudigde klantentabel (stap 5.2 in de geleide flow): alleen gebruikt
# als de gebruiker ervoor kiest om géén onderscheid te maken naar typen
# posten. De voorbeeldcijfers tellen bewust op tot de voorbeeldtotalen van
# LEGE_SSO_TOTALEN hieronder, én tot de som van LEGE_SSO_KLANTEN_DF per
# klant, zodat de consistentiechecks bij de voorbeelddata al kloppen.
LEGE_SSO_KLANTEN_TOTAAL_DF = pd.DataFrame({
    "klant": ["Klant A", "Klant B"],
    "N_klant": ["3.000", "2.000"],
    "waarde_laag": ["1.500.000,00", "1.000.000,00"],
})

# Voorbeeldwaarden voor de SSO-brede totalen (stap 5.1). Som van n/k over de
# typen posten in LEGE_SSO_TYPEN_POSTEN_DF komt hiermee overeen (120+80=200,
# 1+3=4), evenals de som van N_klant/waarde_laag in LEGE_SSO_KLANTEN_TOTAAL_DF
# (3.000+2.000=5.000, 1.500.000+1.000.000=2.500.000).
SSO_TOTAAL_VOORBEELD = {
    "n": "200",
    "k": "4",
    "N_totaal": "5.000",
    "massa": "2.500.000,00",
    "materialiteit": "0,01",
}

# Initialiseer de sessiestatus met standaardwaarden voor de plannings- en evaluatieberekening.
for key, standaard in {
    "plan_tabel": LEGE_PLAN_DF.copy(),
    "plan_berekening_actief": False,
    "plan_strata": None,
    "plan_iteratie": 0,
    "plan_huidige_fout": 1.0,
    "plan_reken_mat": 0.0,
    "plan_status": "Systeem is gereed voor berekening.",
    "plan_conf": 0.95,
    "plan_model": "binomiaal",
    "plan_granulariteit": 10000,
    "plan_vertraging": 0.3,
    "eval_df_saved": LEGE_EVAL_DF.copy(),
    "eval_subtab_index": 0,
    "eval_res": None,
    "eval_error": None,
    "eval_tabel_key": 0,
    "plan_error": None,
    "plan_tabel_key": 0,
    "sso_typen_posten_tabel": LEGE_SSO_TYPEN_POSTEN_DF.copy(),
    "sso_typen_posten_tabel_key": 0,
    "sso_klanten_tabel": LEGE_SSO_KLANTEN_DF.copy(),
    "sso_klanten_tabel_key": 0,
    "sso_klanten_totaal_tabel": LEGE_SSO_KLANTEN_TOTAAL_DF.copy(),
    "sso_klanten_totaal_tabel_key": 0,
    "sso_csv_upload_key": 0,
    "sso_rapport_invoer": None,
    "sso_rapport_pdf": None,
    "sso_rapport_methode": False,
    "sso_zekerheid_text": "0,95",
    "sso_totaal_n_text": SSO_TOTAAL_VOORBEELD["n"],
    "sso_totaal_k_text": SSO_TOTAAL_VOORBEELD["k"],
    "sso_totaal_N_text": SSO_TOTAAL_VOORBEELD["N_totaal"],
    "sso_totaal_massa_text": SSO_TOTAAL_VOORBEELD["massa"],
    "sso_totaal_materialiteit_text": SSO_TOTAAL_VOORBEELD["materialiteit"],
    "sso_klanten_res": {},
    "sso_klanten_waarschuwingen": {},
    "sso_totaal_res": None,
    "sso_error": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = standaard


_GERESERVEERDE_KLANTNAAM_FOUT = (
    f'De naam "{HELE_SSO_NAAM}" is gereserveerd voor de evaluatie van de hele '
    "SSO en mag niet als naam van een klant worden gebruikt."
)


def _nl(getal: float, decimalen: int = 4) -> str:
    """Formatteer een getal met Nederlandse notatie (komma als decimaalteken)."""
    if getal is None or pd.isna(getal):
        return ""
    fmt = f"{getal:,.{decimalen}f}"
    return fmt.replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_nl(waarde) -> float | None:
    """Parseer een Nederlandstalige getalstring naar een float voor berekeningen."""
    if waarde is None:
        return None
    if isinstance(waarde, (int, float)):
        return float(waarde) if not pd.isna(waarde) else None
    tekst = str(waarde).strip()
    if tekst == "":
        return None
    if tekst.startswith("€"):
        tekst = tekst.lstrip("€").strip()
    tekst = tekst.replace(".", "").replace(",", ".")
    try:
        return float(tekst)
    except ValueError:
        return None


def _parse_nl_kolom(series: pd.Series) -> pd.Series:
    """Pas de Nederlandstalige parsing toe op een pandas Series kolom."""
    return series.apply(_parse_nl)


def _format_nl_auto(waarde, min_decimalen: int = 0) -> str:
    """Herformatteer een getalswaarde automatisch naar de Nederlandse notatie."""
    getal = _parse_nl(waarde)
    if getal is None:
        return ""
    tekst = str(waarde).strip()
    if "," in tekst:
        decimalen = max(len(tekst.split(",")[1]), min_decimalen)
    else:
        decimalen = 0
    return _nl(getal, decimalen)


def _sso_ongeveer_gelijk(
    a: float | None, b: float | None, rel_tol: float = 1e-6
) -> bool:
    """Vergelijk twee sommen met een kleine tolerantie (afrondingsverschillen)."""
    if a is None or b is None:
        return (
            True  # Onvergelijkbaar (ontbrekende/onparseerbare waarde) -> geen melding.
        )
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=1e-6)


def on_eval_tabel_change():
    """Verwerk wijzigingen in de evaluatietabel, inclusief harde rollback bij foute invoer."""
    state = st.session_state[f"eval_tabel_{st.session_state.eval_tabel_key}"]
    df = st.session_state.eval_df_saved.copy()
    oude_df = (
        st.session_state.eval_df_saved.copy()
    )  # De ongewijzigde staat als veilige haven

    weggepoetste_fouten = []

    # 1. Pas directe bewerkingen op bestaande rijen toe als ruwe tekst.
    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                # Vertaal een leeggemaakte cel (None) direct naar een lege string.
                df.at[row_idx, col] = "" if val is None else str(val).strip()

    # 2. Voeg de nieuwe rijen vast onderaan toe (inclusief referentie in oude_df)
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row.update({
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "waarde_hoog": "0",
            "fout_hoog": "0",
            "materialiteit": "0,01",
        })
        for col, val in row.items():
            if val is not None:
                new_row[col] = str(val).strip()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        base_row = {col: "" for col in df.columns}
        base_row.update({
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "waarde_hoog": "0",
            "fout_hoog": "0",
            "materialiteit": "0,01",
        })
        oude_df = pd.concat([oude_df, pd.DataFrame([base_row])], ignore_index=True)

    # 3. Voer één uniforme, waterdichte validatielus uit over álle rijen
    for idx in range(len(df)):
        rij_data = df.iloc[idx]
        naam_cel = str(rij_data.get("naam", "")).strip()
        rij_naam = naam_cel if naam_cel else f"Stratum {idx + 1}"

        # Helpertje om foute invoer direct terug te draaien naar de oude waarde
        def revert_cel(kolom, foutmelding, current_idx, current_rij_naam):
            weggepoetste_fouten.append(f"{foutmelding} bij {current_rij_naam}.")
            st.session_state.eval_tabel_key += 1
            df.at[current_idx, kolom] = oude_df.at[current_idx, kolom]

        # Veld-voor-veld validatie
        for col in [
            "waarde_laag",
            "n_laag",
            "k_laag",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        ]:
            val_str = str(df.at[idx, col]).strip()
            val_num = _parse_nl(val_str)

            if val_str == "":
                continue

            if val_num is None:
                revert_cel(
                    col, f'"{val_str}" is geen geldig getal voor {col}', idx, rij_naam
                )
                continue

            if col in ["waarde_laag", "n_laag", "k_laag", "waarde_hoog", "fout_hoog"]:
                if val_num < 0:
                    revert_cel(col, f"{col} mag niet negatief zijn", idx, rij_naam)
                else:
                    df.at[idx, col] = _format_nl_auto(
                        val_str, 0 if col == "n_laag" else 2
                    )
            elif col == "materialiteit":
                if val_num <= 0:
                    revert_cel(
                        col, "materialiteit moet groter zijn dan 0", idx, rij_naam
                    )
                elif val_num > 1:
                    df.at[idx, col] = "€ " + _format_nl_auto(val_str, 2)
                else:
                    df.at[idx, col] = _format_nl_auto(val_str, 2)

        # Relatieve controles ná correctie van individuele velden
        n_val = _parse_nl(df.at[idx, "n_laag"])
        k_val = _parse_nl(df.at[idx, "k_laag"])
        if n_val is not None and k_val is not None and k_val > n_val:
            edited_row_cols = state.get("edited_rows", {}).get(
                idx, state.get("edited_rows", {}).get(str(idx), {})
            )
            col_weg = "k_laag" if "k_laag" in edited_row_cols else "n_laag"
            revert_cel(col_weg, "k_laag mag niet groter zijn dan n_laag", idx, rij_naam)

        wh_val = _parse_nl(df.at[idx, "waarde_hoog"])
        fh_val = _parse_nl(df.at[idx, "fout_hoog"])
        if wh_val is not None and fh_val is not None and fh_val > wh_val:
            edited_row_cols = state.get("edited_rows", {}).get(
                idx, state.get("edited_rows", {}).get(str(idx), {})
            )
            col_weg = "fout_hoog" if "fout_hoog" in edited_row_cols else "waarde_hoog"
            revert_cel(
                col_weg, "fout_hoog mag niet groter zijn dan waarde_hoog", idx, rij_naam
            )

    # 4. Verwijder rijen nu de index-afhankelijke lussen klaar zijn
    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)

    if weggepoetste_fouten:
        st.session_state.eval_error = "Invoerfout: " + " ".join(weggepoetste_fouten)
    else:
        st.session_state.eval_error = None

    st.session_state.eval_df_saved = df


def on_plan_tabel_change():
    """Verwerk wijzigingen in de planningstabel, inclusief harde rollback bij foute invoer."""
    state = st.session_state[f"plan_tabel_{st.session_state.plan_tabel_key}"]
    df = st.session_state.plan_tabel.copy()
    oude_df = (
        st.session_state.plan_tabel.copy()
    )  # De ongewijzigde staat als veilige haven

    weggepoetste_fouten = []

    # 1. Pas directe bewerkingen op bestaande rijen toe als ruwe tekst.
    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                # Vertaal een leeggemaakte cel (None) direct naar een lege string.
                df.at[row_idx, col] = "" if val is None else str(val).strip()

    # 2. Voeg de nieuwe rijen vast onderaan toe (inclusief referentie in oude_df)
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row.update({
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "verwachte_foutfractie": "0,001",
            "kosten": "1,0",
            "waarde_hoog": "0",
            "fout_hoog": "0",
            "materialiteit": "0,01",
        })
        for col, val in row.items():
            if val is not None:
                new_row[col] = str(val).strip()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        base_row = {col: "" for col in df.columns}
        base_row.update({
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "verwachte_foutfractie": "0,001",
            "kosten": "1,0",
            "waarde_hoog": "0",
            "fout_hoog": "0",
            "materialiteit": "0,01",
        })
        oude_df = pd.concat([oude_df, pd.DataFrame([base_row])], ignore_index=True)

    # 3. Voer één uniforme, waterdichte validatielus uit over álle rijen
    for idx in range(len(df)):
        rij_data = df.iloc[idx]
        naam_cel = str(rij_data.get("naam", "")).strip()
        rij_naam = naam_cel if naam_cel else f"Stratum {idx + 1}"

        # Helpertje om foute invoer direct terug te draaien naar de oude waarde
        def revert_cel(kolom, foutmelding, current_idx, current_rij_naam):
            weggepoetste_fouten.append(f"{foutmelding} bij {current_rij_naam}.")
            st.session_state.plan_tabel_key += 1
            df.at[current_idx, kolom] = oude_df.at[current_idx, kolom]

        # Veld-voor-veld validatie
        for col in [
            "waarde_laag",
            "verwachte_foutfractie",
            "kosten",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        ]:
            val_str = str(df.at[idx, col]).strip()
            val_num = _parse_nl(val_str)

            if val_str == "":
                continue

            if val_num is None:
                revert_cel(
                    col, f'"{val_str}" is geen geldig getal voor {col}', idx, rij_naam
                )
                continue

            if col in ["waarde_laag", "waarde_hoog", "fout_hoog"]:
                if val_num < 0:
                    revert_cel(col, f"{col} mag niet negatief zijn", idx, rij_naam)
                else:
                    df.at[idx, col] = _format_nl_auto(val_str, 2)
            elif col == "verwachte_foutfractie":
                if not (0 <= val_num < 1):
                    revert_cel(
                        col,
                        "verwachte_foutfractie moet in [0, 1) liggen",
                        idx,
                        rij_naam,
                    )
                else:
                    df.at[idx, col] = _format_nl_auto(val_str, 3)
            elif col == "kosten":
                if val_num <= 0:
                    revert_cel(col, f"{col} moet groter zijn dan 0", idx, rij_naam)
                else:
                    df.at[idx, col] = _format_nl_auto(val_str, 2)
            elif col == "materialiteit":
                if val_num <= 0:
                    revert_cel(col, f"{col} moet groter zijn dan 0", idx, rij_naam)
                elif val_num > 1:
                    df.at[idx, col] = "€ " + _format_nl_auto(val_str, 2)
                else:
                    df.at[idx, col] = _format_nl_auto(val_str, 2)

        # Relatieve controles ná correctie van individuele velden
        wh_val = _parse_nl(df.at[idx, "waarde_hoog"])
        fh_val = _parse_nl(df.at[idx, "fout_hoog"])
        if wh_val is not None and fh_val is not None and fh_val > wh_val:
            edited_row_cols = state.get("edited_rows", {}).get(
                idx, state.get("edited_rows", {}).get(str(idx), {})
            )
            col_weg = "fout_hoog" if "fout_hoog" in edited_row_cols else "waarde_hoog"
            revert_cel(
                col_weg, "fout_hoog mag niet groter zijn dan waarde_hoog", idx, rij_naam
            )

    # 4. Verwijder rijen nu de index-afhankelijke lussen klaar zijn
    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)

    if weggepoetste_fouten:
        st.session_state.plan_error = "Invoerfout: " + " ".join(weggepoetste_fouten)
    else:
        st.session_state.plan_error = None

    # Reset de berekende resultaten zodra de invoer wijzigt:
    # Als de gebruiker iets in de tabel verandert, is de vorige berekening ongeldig.
    # We zetten de status terug naar gereed en maken alle uitvoerkolommen (n_laag etc.) leeg,
    # ongeacht of de rij een naam heeft of niet.
    df["n_laag"] = None
    df["n_laag_extra"] = None
    df["n_laag_tot"] = None

    st.session_state.plan_berekening_actief = False
    st.session_state.plan_status = "Systeem is gereed voor berekening."

    st.session_state.plan_tabel = df


def on_sso_typen_posten_tabel_change():
    """Verwerk wijzigingen in de SSO-brede typen-posten-tabel, met harde rollback.

    Zelfde patroon als on_eval_tabel_change/on_plan_tabel_change: een
    ongeldige waarde wordt direct teruggedraaid naar de vorige geldige
    waarde (met een foutmelding), en geldige waarden worden meteen naar
    NL-notatie geherformatteerd. Deze tabel bevat alleen de SSO-brede
    velden (naam, n, k, ihr, ibr, car, materialiteit) — N_klant en
    waarde_laag zijn per-klant en staan in `sso_klanten_tabel`. De
    submit-validatie bij de "evalueer alle klanten"-knop (met specifieke,
    veld-voor-veld foutmeldingen) blijft daarnaast bestaan als vangnet,
    bijv. voor geplakte data.
    """
    state = st.session_state[
        f"sso_typen_posten_tabel_editor_{st.session_state.sso_typen_posten_tabel_key}"
    ]
    df = st.session_state.sso_typen_posten_tabel.copy()
    oude_df = (
        st.session_state.sso_typen_posten_tabel.copy()
    )  # De ongewijzigde staat als veilige haven

    weggepoetste_fouten = []

    # 1. Pas directe bewerkingen op bestaande rijen toe als ruwe tekst.
    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                df.at[row_idx, col] = "" if val is None else str(val).strip()

    # 2. Voeg de nieuwe rijen vast onderaan toe (inclusief referentie in oude_df).
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row.update({"ihr": "H", "ibr": "H", "car": "H", "materialiteit": "0,01"})
        for col, val in row.items():
            if val is not None:
                new_row[col] = str(val).strip()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        base_row = {col: "" for col in df.columns}
        base_row.update({"ihr": "H", "ibr": "H", "car": "H", "materialiteit": "0,01"})
        oude_df = pd.concat([oude_df, pd.DataFrame([base_row])], ignore_index=True)

    # 3. Voer één uniforme, waterdichte validatielus uit over álle rijen.
    for idx in range(len(df)):
        rij_data = df.iloc[idx]
        naam_cel = str(rij_data.get("naam", "")).strip()
        rij_naam = naam_cel if naam_cel else f"Type post {idx + 1}"

        # Helpertje om foute invoer direct terug te draaien naar de oude waarde.
        def revert_cel(kolom, foutmelding, current_idx=idx, current_rij_naam=rij_naam):
            weggepoetste_fouten.append(f"{foutmelding} bij {current_rij_naam}.")
            df.at[current_idx, kolom] = oude_df.at[current_idx, kolom]

        # Veld-voor-veld validatie van de verplichte numerieke velden.
        for col in ("n", "k"):
            val_str = str(df.at[idx, col]).strip()
            if val_str == "":
                continue

            val_num = _parse_nl(val_str)
            if val_num is None:
                revert_cel(col, f'"{val_str}" is geen geldig getal voor {col}')
                continue

            if col == "n" and val_num <= 0:
                revert_cel(col, f"{col} moet groter zijn dan 0")
            elif col == "k" and val_num < 0:
                revert_cel(col, "k mag niet negatief zijn")
            else:
                df.at[idx, col] = _format_nl_auto(val_str, 0)

        # materialiteit is optioneel: een lege waarde is geldig (gebruikt het
        # standaardtarief bij submit), maar een ingevulde, onparseerbare of
        # niet-positieve waarde wordt weggepoetst.
        mat_str = str(df.at[idx, "materialiteit"]).strip()
        if mat_str != "":
            mat_num = _parse_nl(mat_str)
            if mat_num is None:
                revert_cel(
                    "materialiteit",
                    f'"{mat_str}" is geen geldig getal voor materialiteit',
                )
            elif mat_num <= 0:
                revert_cel("materialiteit", "materialiteit moet groter zijn dan 0")
            else:
                df.at[idx, "materialiteit"] = _format_nl_auto(mat_str, 2)

        # Relatieve controle ná correctie van de individuele velden.
        n_val = _parse_nl(df.at[idx, "n"])
        k_val = _parse_nl(df.at[idx, "k"])
        if n_val is not None and k_val is not None and k_val > n_val:
            edited_row_cols = state.get("edited_rows", {}).get(
                idx, state.get("edited_rows", {}).get(str(idx), {})
            )
            col_weg = "k" if "k" in edited_row_cols else "n"
            revert_cel(col_weg, "k mag niet groter zijn dan n")

    # 4. Verwijder rijen nu de index-afhankelijke lussen klaar zijn.
    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)

    if weggepoetste_fouten:
        st.session_state.sso_error = "Invoerfout: " + " ".join(weggepoetste_fouten)
    else:
        st.session_state.sso_error = None

    st.session_state.sso_typen_posten_tabel = df
    st.session_state.sso_typen_posten_tabel_key += 1


def on_sso_klanten_tabel_change():
    """Verwerk wijzigingen in de klantentabel, met dezelfde harde-rollback-stijl.

    Deze tabel koppelt per klant × type post alleen nog N_klant en
    waarde_laag (lang/tidy-formaat: één rij per combinatie). `type_post`
    wordt hier alleen op "niet leeg" gecontroleerd — of de waarde ook
    daadwerkelijk overeenkomt met een naam uit `sso_typen_posten_tabel`
    wordt pas bij de submit-validatie gecontroleerd, omdat die tabel kan
    wijzigen nadat een rij hier al is ingevuld.
    """
    state = st.session_state[
        f"sso_klanten_tabel_editor_{st.session_state.sso_klanten_tabel_key}"
    ]
    df = st.session_state.sso_klanten_tabel.copy()
    oude_df = st.session_state.sso_klanten_tabel.copy()

    weggepoetste_fouten = []

    # 1. Pas directe bewerkingen op bestaande rijen toe als ruwe tekst.
    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                df.at[row_idx, col] = "" if val is None else str(val).strip()

    # 2. Voeg de nieuwe rijen vast onderaan toe (inclusief referentie in oude_df).
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        for col, val in row.items():
            if val is not None:
                new_row[col] = str(val).strip()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        base_row = {col: "" for col in df.columns}
        oude_df = pd.concat([oude_df, pd.DataFrame([base_row])], ignore_index=True)

    # 3. Voer één uniforme, waterdichte validatielus uit over álle rijen.
    for idx in range(len(df)):
        rij_data = df.iloc[idx]
        klant_cel = str(rij_data.get("klant", "")).strip()
        type_post_cel = str(rij_data.get("type_post", "")).strip()
        rij_naam = (
            f"klant '{klant_cel}', type post '{type_post_cel}'"
            if klant_cel or type_post_cel
            else f"rij {idx + 1}"
        )

        def revert_cel(kolom, foutmelding, current_idx=idx, current_rij_naam=rij_naam):
            weggepoetste_fouten.append(f"{foutmelding} bij {current_rij_naam}.")
            df.at[current_idx, kolom] = oude_df.at[current_idx, kolom]

        if klant_cel and is_gereserveerde_klantnaam(klant_cel):
            revert_cel(
                "klant",
                f'De naam "{HELE_SSO_NAAM}" is gereserveerd voor de hele SSO '
                "en mag niet als klantnaam worden gebruikt",
            )

        for col in ("N_klant", "waarde_laag"):
            val_str = str(df.at[idx, col]).strip()
            if val_str == "":
                continue

            val_num = _parse_nl(val_str)
            if val_num is None:
                revert_cel(col, f'"{val_str}" is geen geldig getal voor {col}')
                continue

            if col == "N_klant" and val_num <= 0:
                revert_cel(col, "N_klant moet groter zijn dan 0")
            elif col == "waarde_laag" and val_num < 0:
                revert_cel(col, "waarde_laag mag niet negatief zijn")
            else:
                df.at[idx, col] = _format_nl_auto(val_str, 0 if col == "N_klant" else 2)

    # 4. Verwijder rijen nu de index-afhankelijke lussen klaar zijn.
    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)

    if weggepoetste_fouten:
        st.session_state.sso_error = "Invoerfout: " + " ".join(weggepoetste_fouten)
    else:
        st.session_state.sso_error = None

    st.session_state.sso_klanten_tabel = df
    st.session_state.sso_klanten_tabel_key += 1


def on_sso_klanten_totaal_tabel_change():
    """Verwerk wijzigingen in de vereenvoudigde klantentabel (stap 5.2).

    Zelfde harde-rollback-patroon als de andere SSO-tabellen, maar dan
    voor de vereenvoudigde tabel zonder `type_post`-kolom (klant, N_klant,
    waarde_laag) — gebruikt wanneer de gebruiker geen onderscheid naar
    typen posten maakt.
    """
    state = st.session_state[
        "sso_klanten_totaal_tabel_editor_"
        f"{st.session_state.sso_klanten_totaal_tabel_key}"
    ]
    df = st.session_state.sso_klanten_totaal_tabel.copy()
    oude_df = st.session_state.sso_klanten_totaal_tabel.copy()

    weggepoetste_fouten = []

    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                df.at[row_idx, col] = "" if val is None else str(val).strip()

    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        for col, val in row.items():
            if val is not None:
                new_row[col] = str(val).strip()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        base_row = {col: "" for col in df.columns}
        oude_df = pd.concat([oude_df, pd.DataFrame([base_row])], ignore_index=True)

    for idx in range(len(df)):
        rij_data = df.iloc[idx]
        klant_cel = str(rij_data.get("klant", "")).strip()
        rij_naam = f"klant '{klant_cel}'" if klant_cel else f"rij {idx + 1}"

        def revert_cel(kolom, foutmelding, current_idx=idx, current_rij_naam=rij_naam):
            weggepoetste_fouten.append(f"{foutmelding} bij {current_rij_naam}.")
            df.at[current_idx, kolom] = oude_df.at[current_idx, kolom]

        if klant_cel and is_gereserveerde_klantnaam(klant_cel):
            revert_cel(
                "klant",
                f'De naam "{HELE_SSO_NAAM}" is gereserveerd voor de hele SSO '
                "en mag niet als klantnaam worden gebruikt",
            )

        for col in ("N_klant", "waarde_laag"):
            val_str = str(df.at[idx, col]).strip()
            if val_str == "":
                continue

            val_num = _parse_nl(val_str)
            if val_num is None:
                revert_cel(col, f'"{val_str}" is geen geldig getal voor {col}')
                continue

            if col == "N_klant" and val_num <= 0:
                revert_cel(col, "N_klant moet groter zijn dan 0")
            elif col == "waarde_laag" and val_num < 0:
                revert_cel(col, "waarde_laag mag niet negatief zijn")
            else:
                df.at[idx, col] = _format_nl_auto(val_str, 0 if col == "N_klant" else 2)

    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)

    if weggepoetste_fouten:
        st.session_state.sso_error = "Invoerfout: " + " ".join(weggepoetste_fouten)
    else:
        st.session_state.sso_error = None

    st.session_state.sso_klanten_totaal_tabel = df
    st.session_state.sso_klanten_totaal_tabel_key += 1


# Koppeling tussen de widget-sleutels van de SSO-tab en de sleutels in een
# SSO-invoer-CSV (zie auditstat.sso.invoer_csv).
SSO_CSV_INSTELLING_SLEUTELS = {
    "model": "sso_model",
    "zekerheid": "sso_zekerheid_text",
    "berekeningsmethode": "sso_kalibratiemethode",
    "onderscheid": "sso_onderscheid",
}
SSO_CSV_TOTAAL_SLEUTELS = {
    "n": "sso_totaal_n_text",
    "k": "sso_totaal_k_text",
    "N_totaal": "sso_totaal_N_text",
    "massa": "sso_totaal_massa_text",
    "ihr": "sso_totaal_ihr",
    "ibr": "sso_totaal_ibr",
    "car": "sso_totaal_car",
    "materialiteit": "sso_totaal_materialiteit_text",
}


def _formatteer_nl_kolommen(df: pd.DataFrame, min_decimalen: dict) -> pd.DataFrame:
    """Herformatteer getalkolommen naar NL-notatie, zoals de tabelcallbacks."""
    df = df.copy()
    for kolom, minimaal in min_decimalen.items():
        df[kolom] = df[kolom].apply(lambda w, m=minimaal: _format_nl_auto(w, m))
    return df


def on_sso_csv_upload():
    """Lees een geüploade SSO-invoer-CSV in en zet de invoer van de SSO-tab.

    Draait als `on_change`-callback, dus vóór de rerun: widget-sleutels
    mogen hier nog worden gezet. Alles-of-niets: bij een ongeldig bestand
    blijft de huidige invoer volledig ongewijzigd en krijgt de gebruiker de
    foutmeldingen te zien. De uploader krijgt een nieuwe sleutel, zodat
    hetzelfde bestand na een wijziging opnieuw kan worden geüpload.
    """
    sleutel = f"sso_csv_upload_{st.session_state.sso_csv_upload_key}"
    bestand = st.session_state.get(sleutel)
    st.session_state.sso_csv_upload_key += 1
    if bestand is None:
        return

    try:
        invoer = lees_sso_invoer_csv(bestand.getvalue())
    except ValueError as fout:
        st.session_state.sso_csv_melding = (
            "error",
            f"CSV niet ingelezen; de huidige invoer is ongewijzigd.\n\n{fout}",
        )
        return

    for csv_veld, widget_sleutel in SSO_CSV_INSTELLING_SLEUTELS.items():
        if csv_veld in invoer["instellingen"]:
            st.session_state[widget_sleutel] = invoer["instellingen"][csv_veld]
    for csv_veld, widget_sleutel in SSO_CSV_TOTAAL_SLEUTELS.items():
        if csv_veld in invoer["totaal"]:
            st.session_state[widget_sleutel] = invoer["totaal"][csv_veld]

    tabellen = [
        (
            "klanten",
            "sso_klanten_totaal_tabel",
            {"N_klant": 0, "waarde_laag": 2},
        ),
        (
            "typen_posten",
            "sso_typen_posten_tabel",
            {"n": 0, "k": 0, "materialiteit": 2},
        ),
        (
            "klanten_typen",
            "sso_klanten_tabel",
            {"N_klant": 0, "waarde_laag": 2},
        ),
    ]
    ingelezen = []
    for csv_naam, state_naam, decimalen in tabellen:
        df = invoer[csv_naam]
        if df is None:
            continue
        st.session_state[state_naam] = _formatteer_nl_kolommen(df, decimalen)
        st.session_state[f"{state_naam}_key"] += 1
        ingelezen.append(f"{len(df)} rijen {csv_naam.replace('_', ' ')}")

    # Oude resultaten horen niet meer bij de nieuwe invoer.
    st.session_state.sso_klanten_res = {}
    st.session_state.sso_klanten_waarschuwingen = {}
    st.session_state.sso_totaal_res = None
    st.session_state.sso_error = None
    st.session_state.sso_csv_melding = (
        "success",
        "CSV ingelezen: "
        f"{len(invoer['instellingen'])} instellingen, "
        f"{len(invoer['totaal'])} totaalvelden"
        + "".join(f", {tekst}" for tekst in ingelezen)
        + ". Klik op \u2018evalueer alle klanten\u2019 om te rekenen.",
    )


# Bouw de hoofdnavigatie van de applicatie op met vier functionele tabbladen.
st.title("auditstat")

tab_nnz, tab_fpe, tab_eval, tab_plan, tab_sso, tab_theorie = st.tabs([
    "nog nodige zekerheid",
    "foutlozepostenequivalent",
    "evaluatie gestratificeerd",
    "planning gestratificeerd",
    "SSO",
    "Theorie",
])

# Configureer het eerste tabblad voor de berekening van de nog nodige zekerheid.
with tab_nnz:
    col_links, col_rechts = st.columns([1, 3])

    with col_links:
        st.subheader("risico-inschatting")
        haro_ihr = st.selectbox(
            "IHR (InHerent Risico)",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="haro_ihr",
        )
        haro_ibr = st.selectbox(
            "IBR (Interne BeheersingsRisico)",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="haro_ibr",
        )
        haro_car = st.selectbox(
            "CAR (CijferAnalyseRisico)",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="haro_car",
        )

    with col_rechts:
        st.subheader("Resultaat")
        val = haro_nog_nodige_zekerheid(haro_ihr, haro_ibr, haro_car)
        st.metric("nog nodige zekerheid", f"{_nl(val, 4)}")

# Configureer het tweede tabblad voor de berekening van het foutlozepostenequivalent.
with tab_fpe:
    col_links, col_rechts = st.columns([1, 3])

    with col_links:
        st.subheader("risico-inschatting")
        fpe_ihr = st.selectbox(
            "IHR (InHerent Risico)",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="fpe_ihr",
        )
        fpe_ibr = st.selectbox(
            "IBR (Interne BeheersingsRisico)",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="fpe_ibr",
        )
        fpe_car = st.selectbox(
            "CAR (CijferAnalyseRisico)",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="fpe_car",
        )

        # Gebruik een tekstveld om de materialiteit in Europese notatie in te voeren.
        fpe_mat_text = st.text_input(
            "Materialiteit",
            value="0,01",
            help="De materialiteitsgrens als fractie (bijv. 0,01).",
            key="fpe_mat_text",
        )
        fpe_mat = _parse_nl(fpe_mat_text)

    with col_rechts:
        st.subheader("Resultaat")

        # Controleer of de materialiteit wiskundig valide is alvorens te berekenen.
        if fpe_mat is None or fpe_mat <= 0.0 or fpe_mat > 1.0:
            st.error("Voer een geldige materialiteit in tussen 0 en 1 (bijv. 0,01).")
        else:
            fpe_val = foutloze_posten_equivalent(fpe_ihr, fpe_ibr, fpe_car, fpe_mat)
            st.metric("foutlozepostenequivalent", _nl(fpe_val, 0))
            st.caption("Aantal posten dat overeenkomt met de verlaagde risico\u2019s.")

# Configureer het tredje tabblad voor de evaluatie van getrokken gestratificeerde steekproeven.
with tab_eval:
    col_inst, col_hoofd = st.columns([1, 3])

    with col_inst:
        st.subheader("instellingen")

        # Gebruik een tekstveld om de statistische zekerheid in Europese notatie op te vragen.
        strat_conf_text = st.text_input(
            "zekerheid",
            value="0,95",
            help="De gewenste statistische zekerheid (bijv. 0,95 = 95%).",
            key="strat_conf_text",
        )
        strat_conf = _parse_nl(strat_conf_text)

        strat_model = st.radio(
            "model", ["binomiaal", "poisson"], horizontal=True, key="strat_model"
        )

        # Gebruik een tekstveld om de granulariteit in Europese notatie op te vragen.
        strat_gran_text = st.text_input(
            "granulariteit",
            value="10.000",
            help="Aantal stappen voor de FFT-berekening. Meer is nauwkeuriger maar trager.",
            key="strat_gran_text",
        )
        strat_gran_raw = _parse_nl(strat_gran_text)
        strat_gran = int(strat_gran_raw) if strat_gran_raw is not None else 10000

        strat_knop = st.button("bereken evaluatie", type="primary", key="run_strat")

    with col_hoofd:
        # Gebruik een horizontale keuzerondjes-widget om subtabs te simuleren die we programmatisch kunnen aansturen.
        eval_subtab = st.radio(
            "Subtab",
            ["1. invoertabel", "2. resultaten"],
            index=st.session_state.eval_subtab_index,
            horizontal=True,
            label_visibility="collapsed",
        )

        # Synchroniseer de subtab-index wanneer de gebruiker handmatig een keuze maakt.
        if eval_subtab == "1. invoertabel":
            st.session_state.eval_subtab_index = 0
        else:
            st.session_state.eval_subtab_index = 1

        if st.session_state.eval_subtab_index == 0:
            # Toon een foutmelding direct boven de tabel zodra een invoerfout is opgetreden in de callback.
            if st.session_state.eval_error:
                st.error(st.session_state.eval_error)

            st.caption(
                "Vul de strata in. Rijen zonder naam worden genegeerd. "
                "Kolommen ihr, ibr, car: H = hoog, M = midden, L = laag."
            )

            # Toon de invoertabel gekoppeld aan de stabiele gespaarde sessiestructuur en de callback.
            st.data_editor(
                st.session_state.eval_df_saved,
                width="stretch",
                num_rows="dynamic",
                key=f"eval_tabel_{st.session_state.eval_tabel_key}",
                on_change=on_eval_tabel_change,
                column_config={
                    "naam": st.column_config.TextColumn(
                        "naam", help="Unieke naam van het stratum."
                    ),
                    "waarde_laag": st.column_config.TextColumn(
                        "waarde laag (€)",
                        help="Totale geldswaarde van het laagstratum.",
                    ),
                    "n_laag": st.column_config.TextColumn(
                        "n_laag",
                        help="Aantal posten getrokken uit het laagstratum; met andere woorden aantal gedane waarnemingen per toeval getrokken uit het laagstratum.",
                    ),
                    "k_laag": st.column_config.TextColumn(
                        "k_laag",
                        help="Som van de geconstateerde foutfracties (fracties: dus >= 0 en <= 1) van de getrokken posten.",
                    ),
                    "waarde_hoog": st.column_config.TextColumn(
                        "waarde hoog (€)",
                        help="Totale boekwaarde van het hoogstratum (= foutbedrag + goedbedrag, beide van het hoogstratum).",
                    ),
                    "fout_hoog": st.column_config.TextColumn(
                        "fout hoog (€)", help="Totaal foutbedrag van het hoogstratum."
                    ),
                    "ihr": st.column_config.SelectboxColumn(
                        "ihr",
                        help="Inherent risico van het laagstratum (H/M/L).",
                        options=RISK_OPTIES,
                        required=True,
                    ),
                    "ibr": st.column_config.SelectboxColumn(
                        "ibr",
                        help="Intern beheersingsrisico van het laagstratum (H/M/L).",
                        options=RISK_OPTIES,
                        required=True,
                    ),
                    "car": st.column_config.SelectboxColumn(
                        "car",
                        help="Cijferanalyserisico van het laagstratum (H/M/L).",
                        options=RISK_OPTIES,
                        required=True,
                    ),
                    "materialiteit": st.column_config.TextColumn(
                        "materialiteit totaal",
                        help="Totale materialiteit voor dit hele stratum (dus laagstratum en hoogstratum samen). Opgevat als fractie als <= 1 (bijv. 0,01) anders als bedrag in euro's (bijv. 75.000).",
                    ),
                },
            )

        else:
            # Presenteer de foutmeldingen of de berekende resultaten op het scherm.
            if st.session_state.eval_error:
                st.error(st.session_state.eval_error)
            elif st.session_state.eval_res is not None:
                res = st.session_state.eval_res
                try:
                    fig = plot_kanskromme(res)

                    # Haal de weergavetitel op uit de figuur als deze bestaat, en wis deze daarna uit de figuur om overlapping te voorkomen.
                    plot_titel = "Kanskromme van de geprojecteerde fout"
                    if fig._suptitle is not None and fig._suptitle.get_text():
                        plot_titel = fig._suptitle.get_text()
                        fig.suptitle("")

                    for ax in fig.axes:
                        if ax.get_title():
                            plot_titel = ax.get_title()
                            ax.set_title("")

                        # Zorg dat de legenda netjes binnen de grafiekranden valt zonder de curves te snijden.
                        legend = ax.get_legend()
                        if legend is not None:
                            legend.set_bbox_to_anchor((1.0, 1.0))

                        # Geef de y-as iets meer ruimte aan de bovenkant zodat interne annotatieteksten niet buiten de grafiek vallen.
                        y_min, y_max = ax.get_ylim()
                        ax.set_ylim(y_min, y_max * 1.15)

                    # Pas de lay-out van de overgebleven elementen in de figuur aan.
                    fig.tight_layout()

                    # Toon de titel keurig gecentreerd boven de grafiek via Streamlit.
                    st.markdown(
                        f"<h3 style='text-align: center; margin-bottom: 15px;'>{plot_titel}</h3>",
                        unsafe_allow_html=True,
                    )
                    st.pyplot(fig)

                    st.table(
                        pd.DataFrame({
                            "metriek": ["mw fout", "max fout"],
                            "waarde": [
                                f"\u20ac {_nl(res['mw_fout_convolutie_geld'], 2)}",
                                f"\u20ac {_nl(res['max_fout_convolutie_geld'], 2)}",
                            ],
                        })
                    )
                except Exception as e:
                    st.error(f"Fout bij het weergeven van de resultaten: {e}")
            else:
                st.info(
                    "Vul de invoertabel in en klik op \u2018bereken evaluatie\u2019."
                )

    # Verwerk de berekeningsactie zodra de gebruiker op de knop drukt.
    if strat_knop:
        # Controleer de invoervelden in het linkermenu op wiskundige validiteit.
        if strat_conf is None or strat_conf < 0.5 or strat_conf >= 1.0:
            st.error("Voer een geldige zekerheid in tussen 0,50 en 0,999 (bijv. 0,95).")
        elif strat_gran < 100:
            st.error(
                "Voer een geldige granulariteit in van minimaal 100 (bijv. 10.000)."
            )
        else:
            # Filter de lege rijen uit de opgeslagen tabel en bereken de populatiewaarden.
            # Parseer de Nederlandse tekstkolommen naar numerieke waarden voor de berekening.
            _EVAL_NL_KOLOMREN = [
                "waarde_laag",
                "n_laag",
                "k_laag",
                "waarde_hoog",
                "fout_hoog",
                "materialiteit",
            ]
            eval_num = st.session_state.eval_df_saved.copy()
            for _kol in _EVAL_NL_KOLOMREN:
                eval_num[_kol] = _parse_nl_kolom(eval_num[_kol])

            # Selecteer eerst alle rijen waar de auditor bewust een naam heeft ingevuld.
            df_met_naam = eval_num.dropna(subset=["naam"]).loc[
                lambda d: d["naam"].str.strip() != ""
            ]

            # Controleer of er bij deze benoemde strata verplichte velden missen.
            mask_ontbrekend = (
                df_met_naam[["waarde_laag", "n_laag", "k_laag"]].isna().any(axis=1)
            )

            if df_met_naam.empty:
                st.session_state.eval_error = "Vul minimaal één stratum in met een naam en de bijbehorende waarden."
            elif mask_ontbrekend.any():
                namen_fout = ", ".join(df_met_naam.loc[mask_ontbrekend, "naam"])
                st.session_state.eval_error = f"Ontbrekende waarden (waarde laag, n_laag of k_laag) bij stratum: {namen_fout}."
            else:
                # Alles is aanwezig, nu kunnen we veilig de afgeleide kolommen toewijzen.
                df_clean = df_met_naam.reset_index(drop=True).assign(
                    waarde_hoog=lambda d: d["waarde_hoog"].fillna(0),
                    waarde_populatie=lambda d: (
                        d["waarde_laag"] + d["waarde_hoog"].fillna(0)
                    ),
                    ihr=lambda d: d["ihr"].str.upper(),
                    ibr=lambda d: d["ibr"].str.upper(),
                    car=lambda d: d["car"].str.upper(),
                    # --- Nieuw in tab_eval: reken absoluut bedrag om naar totale fractie ---
                    materialiteit=lambda d: d.apply(
                        lambda row: (
                            row["materialiteit"] / row["waarde_populatie"]
                            if row["materialiteit"] > 1 and row["waarde_populatie"] > 0
                            else row["materialiteit"]
                        ),
                        axis=1,
                    ),
                )

                # Valideer kolominvoer: negatieve waarden en andere grenzen.
                if (df_clean["waarde_laag"] < 0).any():
                    namen = ", ".join(df_clean.loc[df_clean["waarde_laag"] < 0, "naam"])
                    st.error(f"waarde_laag is negatief bij: {namen}.")
                    st.stop()
                if (df_clean["n_laag"] < 0).any():
                    namen = ", ".join(df_clean.loc[df_clean["n_laag"] < 0, "naam"])
                    st.error(f"n_laag is negatief bij: {namen}.")
                    st.stop()
                if (df_clean["k_laag"] < 0).any():
                    namen = ", ".join(df_clean.loc[df_clean["k_laag"] < 0, "naam"])
                    st.error(f"k_laag is negatief bij: {namen}.")
                    st.stop()
                if (df_clean["k_laag"] > df_clean["n_laag"]).any():
                    mask = df_clean["k_laag"] > df_clean["n_laag"]
                    namen = ", ".join(df_clean.loc[mask, "naam"])
                    st.error(f"k_laag mag niet groter zijn dan n_laag bij: {namen}.")
                    st.stop()
                _mat = df_clean["materialiteit"].fillna(0)
                if ((_mat <= 0) | (_mat >= 1)).any():
                    mask = (_mat <= 0) | (_mat >= 1)
                    namen = ", ".join(df_clean.loc[mask, "naam"])
                    st.error(
                        f"materialiteit moet een fractie in (0, 1) zijn bij: {namen}."
                    )
                    st.stop()
                if (df_clean["waarde_hoog"] < 0).any():
                    namen = ", ".join(df_clean.loc[df_clean["waarde_hoog"] < 0, "naam"])
                    st.error(f"waarde_hoog is negatief bij: {namen}.")
                    st.stop()
                _fout_hoog = df_clean["fout_hoog"].fillna(0)
                if (_fout_hoog < 0).any():
                    namen = ", ".join(df_clean.loc[_fout_hoog < 0, "naam"])
                    st.error(f"fout_hoog is negatief bij: {namen}.")
                    st.stop()
                if (_fout_hoog > df_clean["waarde_hoog"]).any():
                    mask = _fout_hoog > df_clean["waarde_hoog"]
                    namen = ", ".join(df_clean.loc[mask, "naam"])
                    st.error(f"fout_hoog is groter dan waarde_hoog bij: {namen}.")
                    st.stop()
                try:
                    # Bereken de geconvolueerde resultaten via de rekenmotor.
                    res = eval_stratified(
                        df_clean,
                        model=strat_model,
                        zekerheid=strat_conf,
                        methode="FFT samen",
                        granulariteit=strat_gran,
                    )
                    st.session_state.eval_res = res
                    st.session_state.eval_error = None

                    # Schakel de actieve subtab-index over naar het resultatenvenster.
                    st.session_state.eval_subtab_index = 1
                except Exception as e:
                    st.session_state.eval_error = f"Fout bij de berekening: {e}"

        # Herstart de scriptuitvoering om de tab-wissel visueel door te voeren.
        st.rerun()

# Configureer het vierde tabblad voor het plannen en live optimaliseren van gestratificeerde steekproeven.
with tab_plan:
    col_inst, col_hoofd = st.columns([1, 3])

    with col_inst:
        st.subheader("instellingen")

        # Gebruik een tekstveld om de materialiteit in Europese notatie in te voeren.
        plan_mat_text = st.text_input(
            "materialiteit",
            value="0,01",
            help="De totale materialiteitsgrens opgevat als fractie als <= 1 (bijv. 0,01), anders als bedrag in euro’s (bijv. 73.600.000).",
            key="plan_mat_text",
        )
        plan_mat = _parse_nl(plan_mat_text)

        # Gebruik een tekstveld om de gewenste zekerheid in Europese notatie in te voeren.
        plan_conf_text = st.text_input(
            "zekerheid",
            value="0,95",
            help="De gewenste statistische zekerheid (bijv. 0,95 = 95%).",
            key="plan_conf_text",
        )
        plan_conf = _parse_nl(plan_conf_text)

        plan_model = st.radio(
            "model", ["binomiaal", "poisson"], horizontal=True, key="plan_model_input"
        )

        # Gebruik een tekstveld om de granulariteit in Europese notatie in te voeren.
        plan_gran_text = st.text_input(
            "granulariteit",
            value="10.000",
            help="Aantal stappen voor de FFT-berekeningen. Meer is nauwkeuriger maar trager.",
            key="plan_gran_text",
        )
        plan_gran_raw = _parse_nl(plan_gran_text)
        plan_gran = int(plan_gran_raw) if plan_gran_raw is not None else 10000

        # Gebruik een selectie-schuifbalk om de live-vertraging direct te tonen met komma-notatie.
        plan_vertraging = st.select_slider(
            "live-vertraging (sec per optimalisatie- ofwel klimstap)",
            options=[
                0.0,
                0.05,
                0.1,
                0.15,
                0.2,
                0.25,
                0.3,
                0.4,
                0.5,
                0.6,
                0.7,
                0.8,
                0.9,
                1.0,
                1.2,
                1.5,
                2.0,
            ],
            value=0.3,
            format_func=lambda x: _nl(x, 2),
            key="plan_vertraging_input",
        )

        knop_col1, knop_col2 = st.columns(2)
        with knop_col1:
            start_knop = st.button(
                "bereken planning",
                type="primary",
                disabled=st.session_state.plan_berekening_actief,
                key="run_plan",
            )
        with knop_col2:
            stop_knop = st.button(
                "afbreken",
                type="secondary",
                disabled=not st.session_state.plan_berekening_actief,
                key="stop_plan",
            )

    with col_hoofd:
        # Presenteer de actuele status van de planningsberekening in een informatieve statusbalk.
        if st.session_state.plan_berekening_actief:
            st.info(st.session_state.plan_status)
        elif (
            "voltooid" in st.session_state.plan_status.lower()
            or "afgebroken" in st.session_state.plan_status.lower()
        ):
            st.success(st.session_state.plan_status)
        else:
            st.info(st.session_state.plan_status)

        st.caption(
            "Vul de witte velden (links) in en klik op \u2018bereken planning\u2019. "
            "De grijze velden (rechts) worden live ingevuld."
        )

        if st.session_state.plan_error:
            st.error(st.session_state.plan_error)

        # Toon de planningstabel gekoppeld aan de stabiele opgeslagen planningstructuur en de callback.
        st.data_editor(
            st.session_state.plan_tabel,
            width="stretch",
            num_rows="dynamic",
            key=f"plan_tabel_{st.session_state.plan_tabel_key}",
            on_change=on_plan_tabel_change,
            disabled=["n_laag", "n_laag_extra", "n_laag_tot"],
            column_config={
                "naam": st.column_config.TextColumn(
                    "naam", help="Unieke naam van het stratum."
                ),
                "waarde_laag": st.column_config.TextColumn(
                    "waarde laag (€)",
                    help="Totale geldswaarde van het laagstratum.",
                ),
                "verwachte_foutfractie": st.column_config.TextColumn(
                    "verwachte foutfractie laag",
                    help="De verwachte foutfractie binnen het laagstratum.",
                ),
                "ihr": st.column_config.SelectboxColumn(
                    "ihr",
                    help="Inherent risico van het laagstratum (H/M/L).",
                    options=RISK_OPTIES,
                    required=True,
                ),
                "ibr": st.column_config.SelectboxColumn(
                    "ibr",
                    help="Intern beheersingsrisico van het laagstratum (H/M/L).",
                    options=RISK_OPTIES,
                    required=True,
                ),
                "car": st.column_config.SelectboxColumn(
                    "car",
                    help="Cijferanalyserisico van het laagstratum (H/M/L).",
                    options=RISK_OPTIES,
                    required=True,
                ),
                "kosten": st.column_config.TextColumn(
                    "kosten per steek",
                    help="Relatieve kosten per steek (bijv. 1,0 voor standaard, 10,0 voor duur).",
                ),
                "waarde_hoog": st.column_config.TextColumn(
                    "waarde hoog (€)",
                    help="Totale boekwaarde van het hoogstratum (= foutbedrag + goedbedrag, beide van het hoogstratum).",
                ),
                "fout_hoog": st.column_config.TextColumn(
                    "fout hoog (€)",
                    help="Totaal foutbedrag van het hoogstratum.",
                ),
                "materialiteit": st.column_config.TextColumn(
                    "materialiteit totaal",
                    help="Totale materialiteit voor dit stratum. Opgevat als fractie als <= 1 (bijv. 0,01) anders als bedrag in euro's (bijv. 75.000).",
                ),
                "n_laag": st.column_config.NumberColumn(
                    "n_laag",
                    help="Basissteekproefomvang per stratum: het aantal steekproefwaarnemingen, alleen gebaseerd op verwachte foutfractie, materialiteit, IHR, IBR en CAR per stratum; en betreft alleen het laagstratum.",
                    disabled=True,
                ),
                "n_laag_extra": st.column_config.NumberColumn(
                    "n_laag_extra",
                    help="Extra uit te voeren waarnemingen, dus te trekken posten, in het laagstratum, toegevoegd door de klimoptimalisatie, om te zorgen dat de convolutie van de strata onder de algehele materialiteit zakt.",
                    disabled=True,
                ),
                "n_laag_tot": st.column_config.NumberColumn(
                    "n_laag_tot",
                    help="n_laag + n_laag_extra.",
                    disabled=True,
                ),
            },
        )

    # Initialiseer de live-optimalisatie wanneer de gebruiker op de startknop klikt.
    if start_knop:
        # Maak een kopie van de opgeslagen invoertabel om de oorspronkelijke strings te bewaren voor het terugschrijven.
        invoer_df = st.session_state.plan_tabel.copy()

        # Valideer of de handmatige invoervelden in het linkermenu correct en logisch zijn ingevuld.
        if plan_mat is None or plan_mat <= 0.0:
            st.error(
                "Voer een geldige materialiteit in groter dan 0 (bijv. 0,01 of 75.000)."
            )
            st.stop()
        if plan_conf is None or plan_conf < 0.5 or plan_conf >= 1.0:
            st.error("Voer een geldige zekerheid in tussen 0,50 en 0,999 (bijv. 0,95).")
            st.stop()
        if plan_gran < 100:
            st.error(
                "Voer een geldige granulariteit in van minimaal 100 (bijv. 10.000)."
            )
            st.stop()

        # Parseer Nederlandstalige tekstkolommen naar float voor berekeningen.
        _NL_KOLOMMEN = [
            "waarde_laag",
            "verwachte_foutfractie",
            "kosten",
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
        ]
        invoer_num = invoer_df.copy()
        for _kol in _NL_KOLOMMEN:
            invoer_num[_kol] = _parse_nl_kolom(invoer_num[_kol])

        # Zorg dat de kostenkolom gevuld is (fallback naar 1.0 als leeg):
        invoer_num["kosten"] = invoer_num["kosten"].fillna(1.0)

        # Selecteer eerst alle rijen waar de auditor bewust een naam heeft ingevuld.
        df_met_naam = invoer_num.dropna(subset=["naam"]).loc[
            lambda d: d["naam"].str.strip() != ""
        ]

        if df_met_naam.empty:
            st.error(
                "Vul minimaal één stratum in met een naam en de bijbehorende waarde_laag."
            )
            st.stop()

        # Protesteer hard als een benoemd stratum geen geldige waarde_laag heeft.
        if df_met_naam["waarde_laag"].isna().any():
            namen_fout = ", ".join(
                df_met_naam.loc[df_met_naam["waarde_laag"].isna(), "naam"]
            )
            st.error(f"Ontbrekende 'waarde laag' bij stratum: {namen_fout}.")
            st.stop()

        # Alles is aanwezig, nu kunnen we veilig de afgeleide kolommen toewijzen.
        df_clean = df_met_naam.reset_index(drop=True).assign(
            waarde_hoog=lambda d: d["waarde_hoog"].fillna(0),
            waarde_populatie=lambda d: d["waarde_laag"] + d["waarde_hoog"].fillna(0),
            ihr=lambda d: d["ihr"].str.upper(),
            ibr=lambda d: d["ibr"].str.upper(),
            car=lambda d: d["car"].str.upper(),
            kosten=lambda d: d["kosten"].fillna(1.0),
            # Reken absoluut bedrag om naar totale fractie.
            materialiteit=lambda d: d.apply(
                lambda row: (
                    row["materialiteit"] / row["waarde_populatie"]
                    if row["materialiteit"] > 1 and row["waarde_populatie"] > 0
                    else row["materialiteit"]
                ),
                axis=1,
            ),
        )

        # Bereken de effectieve rekenmaterialiteit.
        totale_pop_waarde = df_clean["waarde_populatie"].sum()
        reken_mat = (
            plan_mat / totale_pop_waarde
            if plan_mat > 1 and totale_pop_waarde > 0
            else plan_mat
        )

        # Valideer cross-constraint: materialiteit * waarde_populatie > fout_hoog per stratum.
        # Zonder positief budget resteert er niets voor het laagstratum.
        _fout_hoog_cc = df_clean["fout_hoog"].fillna(0)
        _budget_laag = (
            df_clean["materialiteit"] * df_clean["waarde_populatie"] - _fout_hoog_cc
        )
        _mask_cc = (df_clean["waarde_laag"] > 0) & (_budget_laag <= 0)
        if _mask_cc.any():
            namen = ", ".join(df_clean.loc[_mask_cc, "naam"])
            st.error(
                f"De bekende fout in het hoogstratum overschrijdt (of evenaart) de stratum-materialiteit bij: {namen}. "
                "Verhoog de materialiteit of verlaag de bekende fout."
            )
            st.stop()

        # Valideer: verwachte foutfractie < omgerekende materialiteit laagstratum per stratum.
        # materialiteit_laag = (materialiteit × waarde_populatie − fout_hoog) / waarde_laag.
        _mat_laag_per_rij = _budget_laag / df_clean["waarde_laag"].replace(
            0, float("nan")
        )
        probleem = df_clean[
            (df_clean["waarde_laag"] > 0)
            & (df_clean["verwachte_foutfractie"] >= _mat_laag_per_rij)
        ]
        if not probleem.empty:
            namen = ", ".join(probleem["naam"].tolist())
            st.error(
                f"Verwachte foutfractie \u2265 omgerekende materialiteit van het laagstratum bij: {namen}. Pas de invoer aan."
            )
            st.stop()

        # Valideer kolominvoer: negatieve waarden en andere grenzen.
        _mask_neg_wl = df_clean["waarde_laag"] < 0
        if _mask_neg_wl.any():
            st.error(
                f"waarde_laag is negatief bij: {', '.join(df_clean.loc[_mask_neg_wl, 'naam'])}."
            )
            st.stop()
        _mask_vff = (df_clean["verwachte_foutfractie"] < 0) | (
            df_clean["verwachte_foutfractie"] >= 1
        )
        if _mask_vff.any():
            st.error(
                f"verwachte_foutfractie moet in [0, 1) liggen bij: {', '.join(df_clean.loc[_mask_vff, 'naam'])}."
            )
            st.stop()
        _mask_kosten = df_clean["kosten"] <= 0
        if _mask_kosten.any():
            st.error(
                f"kosten moet groter zijn dan 0 bij: {', '.join(df_clean.loc[_mask_kosten, 'naam'])}."
            )
            st.stop()
        _mask_neg_wh = df_clean["waarde_hoog"] < 0
        if _mask_neg_wh.any():
            st.error(
                f"waarde_hoog is negatief bij: {', '.join(df_clean.loc[_mask_neg_wh, 'naam'])}."
            )
            st.stop()
        _fout_hoog_plan = df_clean["fout_hoog"].fillna(0)
        if (_fout_hoog_plan < 0).any():
            st.error(
                f"fout_hoog is negatief bij: {', '.join(df_clean.loc[_fout_hoog_plan < 0, 'naam'])}."
            )
            st.stop()
        if (_fout_hoog_plan > df_clean["waarde_hoog"]).any():
            st.error(
                f"fout_hoog is groter dan waarde_hoog bij: {', '.join(df_clean.loc[_fout_hoog_plan > df_clean['waarde_hoog'], 'naam'])}."
            )
            st.stop()
        _mask_mat = (df_clean["materialiteit"] <= 0) | (df_clean["materialiteit"] >= 1)
        if _mask_mat.any():
            st.error(
                f"materialiteit moet na omrekening een fractie in (0, 1) zijn bij: {', '.join(df_clean.loc[_mask_mat, 'naam'])}."
            )
            st.stop()

        # Bereken de basisplanning op basis van de risico's en de invoerparameters.
        try:
            strata_init = plan_stratified_basis(df_clean, model=plan_model)
        except Exception as e:
            st.error(f"Fout bij basisplanning: {e}")
            st.stop()

        try:
            init_fout = eval_stratified(
                strata_init,
                model=plan_model,
                zekerheid=plan_conf,
                methode="FFT samen",
                granulariteit=plan_gran,
                vergelijk=False,
            )["max_fout_convolutie"]
        except ValueError as e:
            st.error(f"Fout bij initiële evaluatie: {e}")
            st.stop()

        # Vul de weergavetabel met de berekende basiswaarden.
        # Reset de outputkolommen eerst voor alle rijen zodat naamloze of
        # niet-berekende rijen geen oude waarden tonen.
        tabel_update = invoer_df.copy()
        tabel_update["n_laag"] = None
        tabel_update["n_laag_extra"] = None
        tabel_update["n_laag_tot"] = None
        for _, rij in strata_init.iterrows():
            idx = tabel_update.index[tabel_update["naam"] == rij["naam"]]
            if len(idx) > 0:
                tabel_update.loc[idx, "n_laag"] = int(rij["n_basis"])
                tabel_update.loc[idx, "n_laag_extra"] = 0
                tabel_update.loc[idx, "n_laag_tot"] = int(rij["n_basis"])

        st.session_state.plan_tabel = tabel_update
        st.session_state.plan_strata = strata_init
        st.session_state.plan_iteratie = 0
        st.session_state.plan_huidige_fout = init_fout
        st.session_state.plan_reken_mat = reken_mat
        st.session_state.plan_conf = plan_conf
        st.session_state.plan_model = plan_model
        st.session_state.plan_granulariteit = plan_gran
        st.session_state.plan_vertraging = plan_vertraging
        st.session_state.plan_berekening_actief = True
        st.session_state.plan_status = (
            f"Basisplanning berekend. Initiële algehele fout: {_nl(init_fout)}. "
            "Live optimalisatie start\u2026"
        )
        st.rerun()

    # Breek de actieve live-berekening af wanneer de gebruiker op de stopknop klikt.
    if stop_knop:
        st.session_state.plan_berekening_actief = False
        st.session_state.plan_status += " \u2014 Afgebroken door gebruiker."
        st.rerun()

    # Voer de live-optimalisatiestappen uit zolang de berekening actief is.
    if st.session_state.plan_berekening_actief:
        strata = st.session_state.plan_strata
        huidige_fout = st.session_state.plan_huidige_fout
        reken_mat = st.session_state.plan_reken_mat
        iteratie = st.session_state.plan_iteratie
        conf = st.session_state.plan_conf
        model = st.session_state.plan_model
        gran = st.session_state.plan_granulariteit
        vertraging = st.session_state.plan_vertraging

        if huidige_fout > reken_mat and iteratie < 1000:
            iteratie += 1

            # Bepaal de beste strata om op te hogen via het klimalgoritme.
            beste_indices = vind_beste_strata_groep(
                strata, model=model, klim_granulariteit=gran, totale_zekerheid=conf
            )

            # Formatteer de verhoogde strata-informatie met Nederlandse getalnotatie.
            info_strata = ", ".join(
                f"{strata.iloc[i]['naam']}; n = {_nl(int(strata.iloc[i]['n_laag']) + 1, 0)}"
                for i in beste_indices
            )

            # Hoog de geselecteerde strata robuust op via de indexlabels.
            for i in beste_indices:
                idx = strata.index[i]
                strata.at[idx, "n_laag"] += 1
                strata.at[idx, "k_laag"] = (
                    strata.at[idx, "n_laag"] * strata.at[idx, "verwachte_foutfractie"]
                )

            huidige_fout = eval_stratified(
                strata,
                model=model,
                zekerheid=conf,
                methode="FFT samen",
                granulariteit=gran,
                vergelijk=False,
            )["max_fout_convolutie"]

            # Werk de weergavetabel bij met de nieuwe steekproefomvangen.
            tabel = st.session_state.plan_tabel.copy()
            for _, rij in strata.iterrows():
                idx = tabel.index[tabel["naam"] == rij["naam"]]
                if len(idx) > 0:
                    n_b = int(rij["n_basis"])
                    n_t = int(rij["n_laag"])
                    tabel.loc[idx, "n_laag"] = n_b
                    tabel.loc[idx, "n_laag_extra"] = n_t - n_b
                    tabel.loc[idx, "n_laag_tot"] = n_t

            st.session_state.plan_tabel = tabel
            st.session_state.plan_strata = strata
            st.session_state.plan_iteratie = iteratie
            st.session_state.plan_huidige_fout = huidige_fout
            st.session_state.plan_status = (
                f"Stap {iteratie} | Opgehoogd naar: {info_strata} | "
                f"Resterende fout: {_nl(huidige_fout)} (doel: {_nl(reken_mat)})"
            )

            # Slaap alleen als de ingestelde live-vertraging groter is dan nul.
            if vertraging > 0.0:
                time.sleep(vertraging)

            # Herstart de scriptuitvoering direct voor de volgende optimalisatiestap.
            st.rerun()

        else:
            # Rond de berekening succesvol af en rapporteer de definitieve resultaten.
            st.session_state.plan_berekening_actief = False
            fmt_fout = _nl(huidige_fout)
            if iteratie >= 1000:
                st.session_state.plan_status = (
                    f"Maximum iteraties bereikt. Eindfout: {fmt_fout}."
                )
            else:
                st.session_state.plan_status = (
                    f"Optimalisatie voltooid! Eindfout: {fmt_fout} <= materialiteit."
                )
            st.rerun()

# Configureer het vijfde tabblad voor de maximale foutfractie bij een SSO-klant.
with tab_sso:
    st.subheader("Gestratificeerde evaluatie van meerdere SSO-klanten")
    st.caption(
        "Vul eerst de totalen voor de SSO als geheel in (stap 1), "
        "vervolgens de klanten (stap 2). Kies daarna of je per klant nog "
        "onderscheid wilt maken naar verschillende typen posten (bijv. "
        "emolumenten, inkoopfacturen), of dat de totalen volstaan (stap "
        "3). Alle klanten worden in één keer berekend. Zie tabblad "
        "\u2018Theorie\u2019 voor de onderbouwing van de gebruikte methoden."
    )

    # Geen st.form: alle data_editors gebruiken on_change om elke
    # celbewerking direct (bij focusverlies) te herformatteren naar
    # NL-notatie, zodat de gebruiker meteen ziet wat hij heeft ingevoerd —
    # ook vóórdat op "evalueer alle klanten" wordt geklikt.
    col_sso_inst, col_sso_hoofd = st.columns([1, 3])

    with col_sso_inst:
        st.subheader("instellingen")
        sso_model = st.radio(
            "model",
            ["binomiaal", "poisson"],
            horizontal=True,
            key="sso_model",
        )
        sso_zekerheid_text = st.text_input("zekerheid", key="sso_zekerheid_text")
        sso_kalibratiemethode = st.radio(
            "berekeningsmethode",
            ["naief", "momentmatching"],
            format_func=lambda m: {
                "naief": "gebruik afgeleide n_klant en k_klant, meestal conservatief",
                "momentmatching": "idem, maar scherper en complexer",
            }[m],
            key="sso_kalibratiemethode",
        )
        st.caption(
            "Een exacte FFT-gebaseerde methode is in ontwikkeling \u2014 "
            "zie tabblad \u2018Theorie\u2019."
        )
        sso_bereken = st.button(
            "evalueer alle klanten", type="primary", key="sso_bereken"
        )

    with col_sso_hoofd:
        st.subheader("1. Totalen voor de SSO als geheel")
        with st.expander("Hoe werkt dit?"):
            st.markdown(
                "`n` en `k` zijn de omvang en het aantal fouten van de "
                "ene, gezamenlijke SSO-brede steekproef; `N totaal` is het "
                "totaal aantal posten in de hele SSO-populatie en `totale "
                "massa` de bijbehorende geldwaarde. Zie tabblad "
                "\u2018Theorie\u2019, sectie 1 voor de achtergrond."
            )
        st.caption(
            "Onderstaande gegevens zijn als voorbeeld ingevuld \u2014 "
            "pas deze (indien nodig) aan."
        )
        c_n, c_k, c_N, c_massa = st.columns(4)
        sso_totaal_n_text = c_n.text_input(
            "n (steekproefomvang)",
            key="sso_totaal_n_text",
        )
        sso_totaal_k_text = c_k.text_input(
            "k (fouten in steekproef)",
            key="sso_totaal_k_text",
        )
        sso_totaal_N_text = c_N.text_input(
            "N totaal (aantal posten)",
            key="sso_totaal_N_text",
        )
        sso_totaal_massa_text = c_massa.text_input(
            "totale massa (euro\u2019s)",
            key="sso_totaal_massa_text",
        )
        c_ihr, c_ibr, c_car, c_mat = st.columns(4)
        sso_totaal_ihr = c_ihr.selectbox(
            "ihr",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="sso_totaal_ihr",
        )
        sso_totaal_ibr = c_ibr.selectbox(
            "ibr",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="sso_totaal_ibr",
        )
        sso_totaal_car = c_car.selectbox(
            "car",
            RISK_OPTIES,
            format_func=lambda k: RISK_LABELS.get(k, k),
            key="sso_totaal_car",
        )
        sso_totaal_materialiteit_text = c_mat.text_input(
            "materialiteit",
            key="sso_totaal_materialiteit_text",
        )

        st.subheader("2. Klanten")
        st.caption(
            "Onderstaande gegevens zijn als voorbeeld ingevuld \u2014 "
            "overschrijf of verwijder de rijen."
        )
        sso_klanten_totaal_tabel = st.data_editor(
            st.session_state.sso_klanten_totaal_tabel,
            width="stretch",
            num_rows="dynamic",
            key=(
                "sso_klanten_totaal_tabel_editor_"
                f"{st.session_state.sso_klanten_totaal_tabel_key}"
            ),
            on_change=on_sso_klanten_totaal_tabel_change,
            column_config={
                "klant": st.column_config.TextColumn(
                    "klant", help="Naam van de klant."
                ),
                "N_klant": st.column_config.TextColumn(
                    "N_klant", help="Totaal aantal posten bij de klant."
                ),
                "waarde_laag": st.column_config.TextColumn(
                    "waarde_laag",
                    help="Totale geldwaarde van de posten bij de klant.",
                ),
            },
        )
        st.session_state.sso_klanten_totaal_tabel = sso_klanten_totaal_tabel

        st.subheader("3. Onderscheid naar typen posten?")
        sso_onderscheid = st.radio(
            "Wil je per klant onderscheid maken naar verschillende typen "
            "posten (bijv. emolumenten, inkoopfacturen)?",
            ["nee", "ja"],
            format_func=lambda v: {
                "nee": "Nee \u2014 reken met de totalen hierboven",
                "ja": "Ja \u2014 ik vul per type post aparte gegevens in",
            }[v],
            key="sso_onderscheid",
        )

        sso_typen_posten_tabel = None
        sso_klanten_tabel = None
        if sso_onderscheid == "ja":
            st.subheader("typen posten bij de SSO")
            st.caption(
                "Onderstaande gegevens zijn als voorbeeld ingevuld \u2014 "
                "overschrijf of verwijder de rijen. De som van n en k over "
                "de typen posten moet overeenkomen met de SSO-brede "
                "totalen hierboven."
            )
            sso_typen_posten_tabel = st.data_editor(
                st.session_state.sso_typen_posten_tabel,
                width="stretch",
                num_rows="dynamic",
                key=(
                    "sso_typen_posten_tabel_editor_"
                    f"{st.session_state.sso_typen_posten_tabel_key}"
                ),
                on_change=on_sso_typen_posten_tabel_change,
                column_config={
                    "naam": st.column_config.TextColumn(
                        "naam", help="Naam van het type post, bijv. Emolumenten."
                    ),
                    "n": st.column_config.TextColumn(
                        "n", help="Steekproefomvang bij de SSO voor dit type post."
                    ),
                    "k": st.column_config.TextColumn(
                        "k",
                        help="Aantal fouten in de SSO-steekproef voor dit type post.",
                    ),
                    "ihr": st.column_config.SelectboxColumn(
                        "ihr", options=RISK_OPTIES, help="InHerent Risico."
                    ),
                    "ibr": st.column_config.SelectboxColumn(
                        "ibr", options=RISK_OPTIES, help="Interne BeheersingsRisico."
                    ),
                    "car": st.column_config.SelectboxColumn(
                        "car", options=RISK_OPTIES, help="CijferAnalyseRisico."
                    ),
                    "materialiteit": st.column_config.TextColumn(
                        "materialiteit",
                        help=(
                            "Materialiteit voor dit type post. Opgevat als "
                            "fractie als \u2264 1 (bijv. 0,01) anders als "
                            "bedrag in euro\u2019s."
                        ),
                    ),
                },
            )
            st.session_state.sso_typen_posten_tabel = sso_typen_posten_tabel

            st.subheader("klanten \u00d7 typen posten")
            st.caption(
                "Onderstaande gegevens zijn als voorbeeld ingevuld \u2014 "
                "overschrijf of verwijder de rijen. Voor elke klant moet de "
                "som van N_klant en waarde_laag over de typen posten "
                "overeenkomen met de klanttotalen hierboven."
            )
            sso_typen_posten_namen = [
                str(n).strip()
                for n in sso_typen_posten_tabel.get("naam", [])
                if n is not None and not pd.isna(n) and str(n).strip()
            ]
            sso_klanten_tabel = st.data_editor(
                st.session_state.sso_klanten_tabel,
                width="stretch",
                num_rows="dynamic",
                key=f"sso_klanten_tabel_editor_{st.session_state.sso_klanten_tabel_key}",
                on_change=on_sso_klanten_tabel_change,
                column_config={
                    "klant": st.column_config.TextColumn(
                        "klant", help="Naam van de klant."
                    ),
                    "type_post": st.column_config.SelectboxColumn(
                        "type_post",
                        options=sso_typen_posten_namen,
                        help="Type post (moet overeenkomen met een naam hierboven).",
                    ),
                    "N_klant": st.column_config.TextColumn(
                        "N_klant", help="Aantal posten van dit type bij de klant."
                    ),
                    "waarde_laag": st.column_config.TextColumn(
                        "waarde_laag",
                        help="Totale geldwaarde van dit type post bij de klant.",
                    ),
                },
            )
            st.session_state.sso_klanten_tabel = sso_klanten_tabel

        # --- Consistentiecontrole (niet-blokkerend, puur informatief) ---
        sso_consistentie_meldingen = []
        sso_totaal_n_chk = _parse_nl(sso_totaal_n_text)
        sso_totaal_k_chk = _parse_nl(sso_totaal_k_text)
        sso_totaal_N_chk = _parse_nl(sso_totaal_N_text)
        sso_totaal_massa_chk = _parse_nl(sso_totaal_massa_text)

        sso_klanten_totaal_rijen_chk = [
            r
            for r in sso_klanten_totaal_tabel.dropna(how="all").to_dict("records")
            if r.get("klant") is not None
            and not pd.isna(r.get("klant"))
            and str(r.get("klant")).strip()
        ]
        som_N_klanten = sum(
            v
            for v in (_parse_nl(r.get("N_klant")) for r in sso_klanten_totaal_rijen_chk)
            if v is not None
        )
        som_waarde_klanten = sum(
            v
            for v in (
                _parse_nl(r.get("waarde_laag")) for r in sso_klanten_totaal_rijen_chk
            )
            if v is not None
        )
        if not _sso_ongeveer_gelijk(som_N_klanten, sso_totaal_N_chk):
            sso_consistentie_meldingen.append(
                f"Som van N_klant over klanten ({_nl(som_N_klanten, 0)}) komt "
                "niet overeen met het SSO-brede totaal N "
                f"({_nl(sso_totaal_N_chk, 0) if sso_totaal_N_chk is not None else '?'})."
            )
        if not _sso_ongeveer_gelijk(som_waarde_klanten, sso_totaal_massa_chk):
            sso_consistentie_meldingen.append(
                f"Som van waarde_laag over klanten ({_nl(som_waarde_klanten, 2)}) "
                "komt niet overeen met de SSO-brede totale massa "
                f"({_nl(sso_totaal_massa_chk, 2) if sso_totaal_massa_chk is not None else '?'})."
            )

        if sso_onderscheid == "ja":
            typen_posten_rijen_chk = [
                r
                for r in sso_typen_posten_tabel.dropna(how="all").to_dict("records")
                if r.get("naam") is not None
                and not pd.isna(r.get("naam"))
                and str(r.get("naam")).strip()
            ]
            som_n_typen = sum(
                v
                for v in (_parse_nl(r.get("n")) for r in typen_posten_rijen_chk)
                if v is not None
            )
            som_k_typen = sum(
                v
                for v in (_parse_nl(r.get("k")) for r in typen_posten_rijen_chk)
                if v is not None
            )
            if not _sso_ongeveer_gelijk(som_n_typen, sso_totaal_n_chk):
                sso_consistentie_meldingen.append(
                    f"Som van n over typen posten ({_nl(som_n_typen, 0)}) komt "
                    "niet overeen met het SSO-brede totaal n "
                    f"({_nl(sso_totaal_n_chk, 0) if sso_totaal_n_chk is not None else '?'})."
                )
            if not _sso_ongeveer_gelijk(som_k_typen, sso_totaal_k_chk):
                sso_consistentie_meldingen.append(
                    f"Som van k over typen posten ({_nl(som_k_typen, 0)}) komt "
                    "niet overeen met het SSO-brede totaal k "
                    f"({_nl(sso_totaal_k_chk, 0) if sso_totaal_k_chk is not None else '?'})."
                )

            som_per_klant = {}
            for r in sso_klanten_tabel.dropna(how="all").to_dict("records"):
                klant_cel = r.get("klant")
                if (
                    klant_cel is None
                    or pd.isna(klant_cel)
                    or not str(klant_cel).strip()
                ):
                    continue
                klant = str(klant_cel).strip()
                sommen = som_per_klant.setdefault(
                    klant, {"N_klant": 0.0, "waarde_laag": 0.0}
                )
                n_klant_val = _parse_nl(r.get("N_klant"))
                waarde_val = _parse_nl(r.get("waarde_laag"))
                if n_klant_val is not None:
                    sommen["N_klant"] += n_klant_val
                if waarde_val is not None:
                    sommen["waarde_laag"] += waarde_val

            totaal_per_klant = {
                str(r.get("klant", "")).strip(): r for r in sso_klanten_totaal_rijen_chk
            }
            for klant, sommen in som_per_klant.items():
                totaal_rij = totaal_per_klant.get(klant)
                if totaal_rij is None:
                    continue  # Geen klanttotaalregel om tegen te vergelijken.
                totaal_N = _parse_nl(totaal_rij.get("N_klant"))
                totaal_waarde = _parse_nl(totaal_rij.get("waarde_laag"))
                if not _sso_ongeveer_gelijk(sommen["N_klant"], totaal_N):
                    sso_consistentie_meldingen.append(
                        f"Klant '{klant}': som van N_klant over typen posten "
                        f"({_nl(sommen['N_klant'], 0)}) komt niet overeen met "
                        "de klanttotaalregel "
                        f"({_nl(totaal_N, 0) if totaal_N is not None else '?'})."
                    )
                if not _sso_ongeveer_gelijk(sommen["waarde_laag"], totaal_waarde):
                    sso_consistentie_meldingen.append(
                        f"Klant '{klant}': som van waarde_laag over typen "
                        f"posten ({_nl(sommen['waarde_laag'], 2)}) komt niet "
                        "overeen met de klanttotaalregel "
                        f"({_nl(totaal_waarde, 2) if totaal_waarde is not None else '?'})."
                    )

        if sso_consistentie_meldingen:
            st.info(
                "Consistentiecontrole \u2014 dit blokkeert de berekening niet, "
                "maar controleer of dit klopt:\n\n"
                + "\n\n".join(sso_consistentie_meldingen)
            )

    # Invoer als CSV: pas hier (na alle invoerwidgets) opgebouwd, zodat de
    # downloadknop de actuele waarden kent; de kolom wordt opnieuw
    # betreden, waardoor deze blokken onder de berekenknop terechtkomen.
    with col_sso_inst:
        st.divider()
        st.subheader("invoer als CSV")
        sso_csv_melding = st.session_state.pop("sso_csv_melding", None)
        if sso_csv_melding is not None:
            soort, tekst = sso_csv_melding
            (st.success if soort == "success" else st.error)(tekst)
        st.file_uploader(
            "CSV met SSO-invoer inlezen",
            type=["csv"],
            key=f"sso_csv_upload_{st.session_state.sso_csv_upload_key}",
            on_change=on_sso_csv_upload,
            help=(
                "Een eerder gedownload bestand (kolommen onderdeel;klant;"
                "type_post;veld;waarde, scheidingsteken ';', getallen in "
                "Nederlandse notatie). Overschrijft de huidige invoer; bij "
                "een fout blijft de invoer ongewijzigd."
            ),
        )
        st.download_button(
            "SSO-invoer downloaden (CSV)",
            data=maak_sso_invoer_csv(
                instellingen={
                    "model": sso_model,
                    "zekerheid": sso_zekerheid_text,
                    "berekeningsmethode": sso_kalibratiemethode,
                    "onderscheid": sso_onderscheid,
                },
                totaal={
                    "n": sso_totaal_n_text,
                    "k": sso_totaal_k_text,
                    "N_totaal": sso_totaal_N_text,
                    "massa": sso_totaal_massa_text,
                    "ihr": sso_totaal_ihr,
                    "ibr": sso_totaal_ibr,
                    "car": sso_totaal_car,
                    "materialiteit": sso_totaal_materialiteit_text,
                },
                klanten=st.session_state.sso_klanten_totaal_tabel,
                typen_posten=st.session_state.sso_typen_posten_tabel,
                klanten_typen=st.session_state.sso_klanten_tabel,
            ).encode("utf-8-sig"),
            file_name="sso_invoer.csv",
            mime="text/csv",
            help=(
                "Bevat de huidige invoer, inclusief de typen-posten-tabellen "
                "ook als onderscheid op \u2018nee\u2019 staat."
            ),
        )
        st.download_button(
            "Voorbeeldbestand downloaden (CSV)",
            data=maak_sso_invoer_csv(
                instellingen={
                    "model": "binomiaal",
                    "zekerheid": "0,95",
                    "berekeningsmethode": "momentmatching",
                    "onderscheid": "ja",
                },
                totaal={
                    **SSO_TOTAAL_VOORBEELD,
                    "ihr": "H",
                    "ibr": "H",
                    "car": "H",
                },
                klanten=LEGE_SSO_KLANTEN_TOTAAL_DF,
                typen_posten=LEGE_SSO_TYPEN_POSTEN_DF,
                klanten_typen=LEGE_SSO_KLANTEN_DF,
            ).encode("utf-8-sig"),
            file_name="sso_invoer_voorbeeld.csv",
            mime="text/csv",
            help=(
                "Een ingevuld voorbeeld in het juiste formaat, om te openen "
                "in Excel en als uitgangspunt voor een eigen bestand."
            ),
        )
        with st.expander("Uitleg van het CSV-formaat"):
            st.markdown(
                "Eén bestand, lang formaat: elke regel is één waarde, in de "
                "kolommen `onderdeel;klant;type_post;veld;waarde` "
                "(scheidingsteken `;`, UTF-8).\n\n"
                "| onderdeel | klant | type_post | velden |\n"
                "|---|---|---|---|\n"
                "| `instelling` | leeg | leeg | `model` (binomiaal/poisson), "
                "`zekerheid`, `berekeningsmethode` (momentmatching/naief), "
                "`onderscheid` (nee/ja) |\n"
                "| `totaal` | leeg | leeg | `n`, `k`, `N_totaal`, `massa`, "
                "`ihr`, `ibr`, `car`, `materialiteit` |\n"
                "| `klant` | naam | leeg | `N_klant`, `waarde_laag` |\n"
                "| `type_post` | leeg | naam | `n`, `k`, `ihr`, `ibr`, `car`, "
                "`materialiteit` |\n"
                "| `klant_type_post` | naam | naam | `N_klant`, "
                "`waarde_laag` |\n\n"
                "Regels voor het inlezen:\n"
                "- Getallen in Nederlandse notatie: punt als "
                "duizendtalscheiding, komma als decimaalteken "
                "(`1.500.000,00`). `1234.56` wordt geweigerd, omdat het "
                "dubbelzinnig is.\n"
                "- `ihr`, `ibr`, `car` zijn `H`, `M` of `L`; `materialiteit` "
                "mag leeg zijn (standaard 0,01).\n"
                "- Alle velden van een klant, type post of het totaal zijn "
                "verplicht; dubbele regels worden geweigerd.\n"
                "- Bij `onderscheid = ja` zijn zowel `type_post`- als "
                "`klant_type_post`-regels nodig.\n"
                "- Onderdelen die ontbreken laten de huidige invoer "
                "ongemoeid.\n"
                "- Alles-of-niets: bij een fout wordt niets overgenomen en "
                "toont de app alle gevonden fouten met regelnummer."
            )

    if sso_bereken:
        st.session_state.sso_rapport_pdf = None
        sso_zekerheid = _parse_nl(sso_zekerheid_text)
        klanten_fouten = []
        klanten_rijen_per_klant = {}

        if sso_onderscheid == "nee":
            sso_totaal_n_val = _parse_nl(sso_totaal_n_text)
            sso_totaal_k_val = _parse_nl(sso_totaal_k_text)
            sso_totaal_materialiteit_val = _parse_nl(sso_totaal_materialiteit_text)

            for veld_naam, veld_waarde, veld_ruw in (
                ("n", sso_totaal_n_val, sso_totaal_n_text),
                ("k", sso_totaal_k_val, sso_totaal_k_text),
            ):
                if veld_waarde is None:
                    klanten_fouten.append(
                        f"SSO-totalen: veld '{veld_naam}' (\"{veld_ruw}\") is "
                        "geen geldig getal."
                    )
            materialiteit_tekst_totaal = str(sso_totaal_materialiteit_text).strip()
            if (
                materialiteit_tekst_totaal != ""
                and sso_totaal_materialiteit_val is None
            ):
                klanten_fouten.append(
                    "SSO-totalen: veld 'materialiteit' "
                    f'("{sso_totaal_materialiteit_text}") is geen geldig getal.'
                )

            sso_klanten_totaal_rijen = [
                r
                for r in sso_klanten_totaal_tabel.dropna(how="all").to_dict("records")
                if r.get("klant") is not None
                and not pd.isna(r.get("klant"))
                and str(r.get("klant")).strip()
            ]
            for rij in sso_klanten_totaal_rijen:
                klant = str(rij.get("klant", "")).strip()
                if is_gereserveerde_klantnaam(klant):
                    klanten_fouten.append(_GERESERVEERDE_KLANTNAAM_FOUT)
                    continue
                N_klant_val = _parse_nl(rij.get("N_klant"))
                waarde_laag_val = _parse_nl(rij.get("waarde_laag"))
                for veld_naam, veld_waarde in (
                    ("N_klant", N_klant_val),
                    ("waarde_laag", waarde_laag_val),
                ):
                    if veld_waarde is None:
                        klanten_fouten.append(
                            f"Klant '{klant}': veld '{veld_naam}' "
                            f'("{rij.get(veld_naam)}") is geen geldig getal.'
                        )
                if N_klant_val is None or waarde_laag_val is None:
                    continue
                if klant in klanten_rijen_per_klant:
                    klanten_fouten.append(
                        f"Klant '{klant}' komt meerdere keren voor; namen "
                        "moeten uniek zijn."
                    )
                    continue
                if sso_totaal_n_val is None or sso_totaal_k_val is None:
                    continue
                klanten_rijen_per_klant[klant] = {
                    "totaal": dict(
                        naam="totaal",
                        n=sso_totaal_n_val,
                        k=sso_totaal_k_val,
                        ihr=sso_totaal_ihr,
                        ibr=sso_totaal_ibr,
                        car=sso_totaal_car,
                        materialiteit=(
                            sso_totaal_materialiteit_val
                            if sso_totaal_materialiteit_val is not None
                            else 0.01
                        ),
                        N_klant=N_klant_val,
                        waarde_laag=waarde_laag_val,
                    )
                }

            if not sso_klanten_totaal_rijen:
                klanten_fouten.append("Voer tenminste 1 klant (rij) in.")
        else:
            # Typen posten indexeren op naam voor de koppeling met de klantentabel.
            sso_typen_posten_rijen = [
                r
                for r in sso_typen_posten_tabel.dropna(how="all").to_dict("records")
                if r.get("naam") is not None
                and not pd.isna(r.get("naam"))
                and str(r.get("naam")).strip()
            ]
            sso_typen_posten_per_naam = {}
            for rij in sso_typen_posten_rijen:
                naam = str(rij.get("naam", "")).strip()
                n_val = _parse_nl(rij.get("n"))
                k_val = _parse_nl(rij.get("k"))
                materialiteit_ruw = rij.get("materialiteit")
                materialiteit_val = _parse_nl(materialiteit_ruw)

                for veld_naam, veld_waarde in (("n", n_val), ("k", k_val)):
                    if veld_waarde is None:
                        klanten_fouten.append(
                            f"Type post '{naam}': veld '{veld_naam}' "
                            f'("{rij.get(veld_naam)}") is geen geldig getal.'
                        )
                materialiteit_tekst = (
                    "" if materialiteit_ruw is None else str(materialiteit_ruw).strip()
                )
                if materialiteit_tekst != "" and materialiteit_val is None:
                    klanten_fouten.append(
                        f"Type post '{naam}': veld 'materialiteit' "
                        f'("{materialiteit_ruw}") is geen geldig getal.'
                    )

                if naam in sso_typen_posten_per_naam:
                    klanten_fouten.append(
                        f"Type post '{naam}' komt meerdere keren voor; namen "
                        "moeten uniek zijn."
                    )
                elif n_val is not None and k_val is not None:
                    sso_typen_posten_per_naam[naam] = dict(
                        naam=naam,
                        n=n_val,
                        k=k_val,
                        ihr=rij.get("ihr", "H"),
                        ibr=rij.get("ibr", "H"),
                        car=rij.get("car", "H"),
                        materialiteit=(
                            materialiteit_val if materialiteit_val is not None else 0.01
                        ),
                    )

            if not sso_typen_posten_per_naam and not klanten_fouten:
                klanten_fouten.append("Voer tenminste 1 type post (rij) in.")

            # Klantenrijen groeperen per klant.
            sso_klanten_rijen = [
                r
                for r in sso_klanten_tabel.dropna(how="all").to_dict("records")
                if r.get("klant") is not None
                and not pd.isna(r.get("klant"))
                and str(r.get("klant")).strip()
            ]
            if not sso_klanten_rijen:
                klanten_fouten.append("Voer tenminste 1 klant (rij) in.")

            for rij in sso_klanten_rijen:
                klant = str(rij.get("klant", "")).strip()
                if is_gereserveerde_klantnaam(klant):
                    if _GERESERVEERDE_KLANTNAAM_FOUT not in klanten_fouten:
                        klanten_fouten.append(_GERESERVEERDE_KLANTNAAM_FOUT)
                    continue
                type_post = str(rij.get("type_post", "")).strip()
                N_klant_val = _parse_nl(rij.get("N_klant"))
                waarde_laag_val = _parse_nl(rij.get("waarde_laag"))

                if not type_post:
                    klanten_fouten.append(f"Klant '{klant}': veld 'type_post' is leeg.")
                    continue
                if type_post not in sso_typen_posten_per_naam:
                    klanten_fouten.append(
                        f"Klant '{klant}': type post '{type_post}' komt niet "
                        "voor in de typen-posten-tabel hierboven."
                    )
                    continue
                for veld_naam, veld_waarde in (
                    ("N_klant", N_klant_val),
                    ("waarde_laag", waarde_laag_val),
                ):
                    if veld_waarde is None:
                        klanten_fouten.append(
                            f"Klant '{klant}': type post '{type_post}': veld "
                            f"'{veld_naam}' (\"{rij.get(veld_naam)}\") is geen "
                            "geldig getal."
                        )
                if N_klant_val is None or waarde_laag_val is None:
                    continue

                klant_rijen = klanten_rijen_per_klant.setdefault(klant, {})
                if type_post in klant_rijen:
                    klanten_fouten.append(
                        f"Klant '{klant}': type post '{type_post}' komt "
                        "meerdere keren voor voor dezelfde klant."
                    )
                    continue
                klant_rijen[type_post] = dict(
                    sso_typen_posten_per_naam[type_post],
                    N_klant=N_klant_val,
                    waarde_laag=waarde_laag_val,
                )

        if sso_zekerheid is None or not (0.0 < sso_zekerheid < 1.0):
            st.session_state.sso_error = (
                "Voer een geldige zekerheid in tussen 0 en 1 (bijv. 0,95)."
            )
            st.session_state.sso_klanten_res = {}
            st.session_state.sso_klanten_waarschuwingen = {}
            st.session_state.sso_totaal_res = None
        elif klanten_fouten:
            st.session_state.sso_error = "\n".join(klanten_fouten)
            st.session_state.sso_klanten_res = {}
            st.session_state.sso_klanten_waarschuwingen = {}
            st.session_state.sso_totaal_res = None
        else:
            sso_klanten_res = {}
            sso_klanten_waarschuwingen = {}
            berekenings_fouten = []
            for klant, type_post_dict in klanten_rijen_per_klant.items():
                post_typen = list(type_post_dict.values())
                try:
                    with warnings.catch_warnings(record=True) as gevangen:
                        warnings.simplefilter("always", RuntimeWarning)
                        resultaat = evalueer_SSO_klant_gestratificeerd(
                            post_typen,
                            model=sso_model,
                            zekerheid=sso_zekerheid,
                            kalibratiemethode=sso_kalibratiemethode,
                        )
                    sso_klanten_res[klant] = resultaat
                    klant_waarschuwingen = [
                        str(w.message)
                        for w in gevangen
                        if issubclass(w.category, RuntimeWarning)
                    ]
                    if klant_waarschuwingen:
                        sso_klanten_waarschuwingen[klant] = klant_waarschuwingen
                except ValueError as e:
                    berekenings_fouten.append(f"Klant '{klant}': {e}")

            # Evaluatie van de hele SSO: de SSO-brede steekproef direct op
            # de totale massa, zonder klantkalibratie.
            if sso_onderscheid == "nee":
                sso_totaal_massa_val = _parse_nl(sso_totaal_massa_text)
                if sso_totaal_massa_val is None:
                    sso_totaal_posten = []
                    berekenings_fouten.append(
                        "SSO totaal: veld 'totale massa' "
                        f'("{sso_totaal_massa_text}") is geen geldig getal.'
                    )
                else:
                    sso_totaal_posten = [
                        dict(
                            naam="totaal",
                            n=_parse_nl(sso_totaal_n_text),
                            k=_parse_nl(sso_totaal_k_text),
                            ihr=sso_totaal_ihr,
                            ibr=sso_totaal_ibr,
                            car=sso_totaal_car,
                            materialiteit=(
                                _parse_nl(sso_totaal_materialiteit_text)
                                if _parse_nl(sso_totaal_materialiteit_text) is not None
                                else 0.01
                            ),
                            waarde_laag=sso_totaal_massa_val,
                        )
                    ]
            else:
                # Massa per type post = som over alle klanten.
                sso_massa_per_type = {}
                for type_post_dict in klanten_rijen_per_klant.values():
                    for type_post, post in type_post_dict.items():
                        sso_massa_per_type[type_post] = (
                            sso_massa_per_type.get(type_post, 0.0) + post["waarde_laag"]
                        )
                sso_totaal_posten = [
                    {
                        key: waarde
                        for key, waarde in sso_typen_posten_per_naam[naam].items()
                    }
                    | {"waarde_laag": massa}
                    for naam, massa in sso_massa_per_type.items()
                ]
            sso_totaal_res = None
            if sso_totaal_posten:
                try:
                    sso_totaal_res = evalueer_SSO_totaal(
                        sso_totaal_posten,
                        model=sso_model,
                        zekerheid=sso_zekerheid,
                    )
                except ValueError as e:
                    berekenings_fouten.append(f"SSO totaal: {e}")

            st.session_state.sso_klanten_res = sso_klanten_res
            st.session_state.sso_klanten_waarschuwingen = sso_klanten_waarschuwingen
            st.session_state.sso_totaal_res = sso_totaal_res
            st.session_state.sso_error = (
                "\n".join(berekenings_fouten) if berekenings_fouten else None
            )
            # Momentopname van de invoer waarmee is gerekend, zodat het
            # PDF-rapport bij de resultaten blijft passen ook als de invoer
            # daarna nog wordt aangepast.
            st.session_state.sso_rapport_invoer = {
                "instellingen": {
                    "model": sso_model,
                    "zekerheid": sso_zekerheid_text,
                    "berekeningsmethode": sso_kalibratiemethode,
                    "onderscheid": sso_onderscheid,
                },
                "totaal": {
                    "n": sso_totaal_n_text,
                    "k": sso_totaal_k_text,
                    "N_totaal": sso_totaal_N_text,
                    "massa": sso_totaal_massa_text,
                    "ihr": sso_totaal_ihr,
                    "ibr": sso_totaal_ibr,
                    "car": sso_totaal_car,
                    "materialiteit": sso_totaal_materialiteit_text,
                },
                "klanten": st.session_state.sso_klanten_totaal_tabel.copy(),
                "typen_posten": st.session_state.sso_typen_posten_tabel.copy(),
                "klanten_typen": st.session_state.sso_klanten_tabel.copy(),
            }

    if st.session_state.sso_error:
        st.error(st.session_state.sso_error)

    sso_klanten_res = st.session_state.sso_klanten_res
    if sso_klanten_res:
        st.subheader("Resultaat")
        sso_samenvatting = pd.DataFrame([
            {
                "klant": klant,
                "max_fout_fractie": _nl(res["max_fout_convolutie"], 4),
                "max_fout_euro": _nl(res["max_fout_convolutie_geld"], 2),
            }
            for klant, res in sso_klanten_res.items()
        ])
        st.table(sso_samenvatting)

        st.divider()
        sso_samen_fractie, sso_samen_euro, _ = klanten_samen(sso_klanten_res)
        sso_totalen_rijen = [
            {
                "klant": KLANTEN_SAMEN_NAAM,
                "max_fout_fractie": _nl(sso_samen_fractie, 4),
                "max_fout_euro": _nl(sso_samen_euro, 2),
            }
        ]
        if st.session_state.sso_totaal_res is not None:
            sso_totalen_rijen.append({
                "klant": HELE_SSO_NAAM,
                "max_fout_fractie": _nl(
                    st.session_state.sso_totaal_res["max_fout_convolutie"], 4
                ),
                "max_fout_euro": _nl(
                    st.session_state.sso_totaal_res["max_fout_convolutie_geld"], 2
                ),
            })
        st.table(pd.DataFrame(sso_totalen_rijen))
        st.caption(
            "Klanten samen telt de grenzen van de klanten bij elkaar op. "
            "Dat is een voorzichtige schatting: de werkelijke grens voor "
            "alle klanten samen is meestal lager. Hele SSO is een aparte "
            "berekening op de gegevens van de hele SSO."
        )

        if maak_sso_rapport_pdf is None:
            st.caption(
                "Voor een PDF-rapport is het pakket \u2018reportlab\u2019 "
                "nodig (`pip install auditstat[pdf]`)."
            )
        elif st.session_state.sso_rapport_invoer is not None:
            st.checkbox(
                "Methodebeschrijving opnemen in het rapport",
                key="sso_rapport_methode",
                on_change=lambda: st.session_state.update(sso_rapport_pdf=None),
                help=(
                    "Voegt een pagina toe met de gekozen kalibratiemethode "
                    "en de aannames van het model."
                ),
            )
            if st.button("PDF-rapport maken", key="sso_rapport_maken"):
                if not {"methodebeschrijving", "resultaat_totaal", "voortgang"} <= set(
                    inspect.signature(maak_sso_rapport_pdf).parameters
                ):
                    # Een draaiend proces kan een oudere versie van de
                    # module in het geheugen houden dan de app verwacht.
                    st.session_state.sso_rapport_pdf = None
                    st.error(
                        "De geladen rapportmodule is verouderd ten opzichte "
                        "van de app. Herstart de app (lokaal: stop en start "
                        "Streamlit opnieuw; op Streamlit Cloud: Manage app "
                        "\u2192 Reboot app) en probeer het opnieuw."
                    )
                    st.stop()
                sso_rapport_balk = st.progress(
                    0.0, text="Rapport wordt opgebouwd\u2026"
                )
                try:
                    st.session_state.sso_rapport_pdf = maak_sso_rapport_pdf(
                        st.session_state.sso_rapport_invoer,
                        sso_klanten_res,
                        st.session_state.sso_klanten_waarschuwingen,
                        methodebeschrijving=st.session_state.sso_rapport_methode,
                        resultaat_totaal=st.session_state.sso_totaal_res,
                        voortgang=lambda fractie, tekst: sso_rapport_balk.progress(
                            fractie, text=tekst
                        ),
                    )
                except Exception as e:  # noqa: BLE001 - toon elke fout aan de gebruiker
                    st.session_state.sso_rapport_pdf = None
                    st.error(f"Het rapport kon niet worden gemaakt: {e}")
                finally:
                    sso_rapport_balk.empty()
            if st.session_state.sso_rapport_pdf is not None:
                st.download_button(
                    "PDF-rapport downloaden",
                    data=st.session_state.sso_rapport_pdf,
                    file_name="sso_rapport.pdf",
                    mime="application/pdf",
                    key="sso_rapport_download",
                    help=(
                        "Bevat de invoer waarmee is gerekend, de resultaten "
                        "per klant en de kanskrommen."
                    ),
                )

        sso_totaal_res = st.session_state.sso_totaal_res
        if sso_totaal_res is not None:
            st.markdown("#### Hele SSO")
            st.caption(
                "Dit resultaat is niet de optelling van de resultaten van de "
                "afzonderlijke klanten, maar een eigenstandige berekening die "
                "alleen uitgaat van de gegevens van de hele SSO: n, k, de "
                "totale massa, IHR, IBR, CAR en de materialiteit."
            )
            sso_totaal_col1, sso_totaal_col2 = st.columns(2)
            sso_totaal_col1.metric(
                "Maximale fout (fractie)", _nl(sso_totaal_res["max_fout_convolutie"], 4)
            )
            sso_totaal_col2.metric(
                "Maximale fout (euro\u2019s)",
                _nl(sso_totaal_res["max_fout_convolutie_geld"], 2),
            )
            st.table(
                sso_totaal_res["steekproeven"][
                    ["naam", "waarde_laag", "n_laag", "k_laag"]
                ].assign(
                    waarde_laag=lambda d: d["waarde_laag"].apply(lambda x: _nl(x, 2)),
                    n_laag=lambda d: d["n_laag"].apply(lambda x: _nl(x, 0)),
                    k_laag=lambda d: d["k_laag"].apply(lambda x: _nl(x, 0)),
                )
            )
            st.pyplot(plot_kanskromme(sso_totaal_res))

        if st.session_state.sso_klanten_waarschuwingen:
            alle_waarschuwingen = [
                f"Klant '{klant}': {w}"
                for klant, ws in st.session_state.sso_klanten_waarschuwingen.items()
                for w in ws
            ]
            st.warning("\n\n".join(alle_waarschuwingen))

        for sso_klant_getoond, sso_klant_res in sso_klanten_res.items():
            st.markdown(f"#### {sso_klant_getoond}")
            sso_klant_col1, sso_klant_col2 = st.columns(2)
            sso_klant_col1.metric(
                "Maximale fout (fractie)", _nl(sso_klant_res["max_fout_convolutie"], 4)
            )
            sso_klant_col2.metric(
                "Maximale fout (euro\u2019s)",
                _nl(sso_klant_res["max_fout_convolutie_geld"], 2),
            )
            sso_klant_steekproeven_tabel = sso_klant_res["steekproeven"][
                ["naam", "waarde_laag", "n_laag", "k_laag"]
            ].assign(
                waarde_laag=lambda d: d["waarde_laag"].apply(lambda x: _nl(x, 2)),
                n_laag=lambda d: d["n_laag"].apply(lambda x: _nl(x, 2)),
                k_laag=lambda d: d["k_laag"].apply(lambda x: _nl(x, 2)),
            )
            st.table(sso_klant_steekproeven_tabel)
            sso_klant_fig = plot_kanskromme(sso_klant_res)
            st.pyplot(sso_klant_fig)

# Theorie-tabblad: de wiskundige onderbouwing per deelonderwerp, apart van
# de werktabbladen zodat een gebruiker die er niet in geïnteresseerd is er
# niet doorheen hoeft te scrollen. Dit is een eerste versie: alleen de
# gewone wiskundige afleiding/redenering, nog geen formeel Lean-bewijs (dat
# is een apart, toekomstig traject — zie AGENTS.md).
with tab_theorie:
    # De theorietekst staat in theorie.qmd (zie auditstat/sso/theorie_qmd.py).
    try:
        _theorie = lees_theorie_qmd(Path(__file__).parent / "theorie.qmd")
    except (OSError, ValueError) as _fout:
        st.error(f"theorie.qmd kon niet worden gelezen: {_fout}")
    else:
        st.subheader(_theorie.titel or "Theoretische achtergrond")
        if _theorie.inleiding:
            st.caption(_theorie.inleiding)
        for _i, _sectie in enumerate(_theorie.secties):
            with st.expander(_sectie.titel, expanded=(_i == 0)):
                for _blok in _sectie.blokken:
                    if isinstance(_blok, str):
                        st.markdown(_blok)
                    elif _blok.label in THEORIE_FIGUREN:
                        st.pyplot(THEORIE_FIGUREN[_blok.label]())
                        if _blok.bijschrift:
                            st.caption(_blok.bijschrift)
                    else:
                        st.error(f"Onbekende figuur in theorie.qmd: {_blok.label}")
