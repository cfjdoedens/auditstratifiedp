import time

import pandas as pd
import streamlit as st

from auditstratified.eval_stratified import eval_stratified
from auditstratified.plan_stratified import (
    plan_stratified_basis,
    vind_beste_strata_groep,
)
from auditstratified.plot_kanskromme import plot_kanskromme
from auditstratified.utils import foutloze_posten_equivalent, haro_nog_nodige_zekerheid

# Configureer de pagina lay-out en titel van de Streamlit webapplicatie.
st.set_page_config(page_title="auditstratified", layout="wide")

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
    "materialiteit": ["0,01"] * 8,
    "waarde_hoog": ["0"] * 8,
    "fout_hoog": ["0"] * 8,
})

# Bereid een leeg sjabloon-dataframe voor om de invoertabel voor de planning te initialiseren.
LEGE_PLAN_DF = pd.DataFrame({
    "naam": [""] * 8,
    "waarde_laag": [""] * 8,
    "verwachte_foutfractie": ["0,001"] * 8,
    "ihr": ["H"] * 8,
    "ibr": ["H"] * 8,
    "car": ["H"] * 8,
    "materialiteit": ["0,01"] * 8,
    "kosten": ["1,0"] * 8,
    "waarde_hoog": ["0"] * 8,
    "fout_hoog": ["0"] * 8,
    "n_laag": [None] * 8,
    "n_laag_extra": [None] * 8,
    "n_laag_tot": [None] * 8,
})

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
}.items():
    if key not in st.session_state:
        st.session_state[key] = standaard


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


def on_eval_tabel_change():
    """Verwerk wijzigingen in de evaluatietabel, inclusief harde rollback bij foute invoer."""
    state = st.session_state[f"eval_tabel_{st.session_state.eval_tabel_key}"]
    df = st.session_state.eval_df_saved.copy()
    oude_df = (
        st.session_state.eval_df_saved.copy()
    )  # De ongewijzigde staat als veilige haven

    weggepoetste_fouten = []

    # 1. Pas directe bewerkingen op bestaande rijen toe als ruwe tekst
    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                if val is not None:
                    df.at[row_idx, col] = str(val).strip()

    # 2. Voeg de nieuwe rijen vast onderaan toe (inclusief referentie in oude_df)
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row.update({
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "materialiteit": "0,01",
            "waarde_hoog": "0",
            "fout_hoog": "0",
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
            "materialiteit": "0,01",
            "waarde_hoog": "0",
            "fout_hoog": "0",
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
                if not (0 < val_num < 1):
                    revert_cel(
                        col, "materialiteit moet in (0, 1) liggen", idx, rij_naam
                    )
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

    # 1. Pas directe bewerkingen op bestaande rijen toe als ruwe tekst
    for row_idx_raw, changes in state.get("edited_rows", {}).items():
        row_idx = int(row_idx_raw)
        if row_idx < len(df):
            for col, val in changes.items():
                if val is not None:
                    df.at[row_idx, col] = str(val).strip()

    # 2. Voeg de nieuwe rijen vast onderaan toe (inclusief referentie in oude_df)
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row.update({
            "ihr": "H",
            "ibr": "H",
            "car": "H",
            "materialiteit": "0,01",
            "verwachte_foutfractie": "0,001",
            "kosten": "1,0",
            "waarde_hoog": "0",
            "fout_hoog": "0",
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
            "materialiteit": "0,01",
            "verwachte_foutfractie": "0,001",
            "kosten": "1,0",
            "waarde_hoog": "0",
            "fout_hoog": "0",
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
            elif col in ["kosten", "materialiteit"]:
                if val_num <= 0:
                    revert_cel(col, f"{col} moet groter zijn dan 0", idx, rij_naam)
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

    st.session_state.plan_tabel = df


# Bouw de hoofdnavigatie van de applicatie op met vier functionele tabbladen.
st.title("auditstratified")

tab_nnz, tab_fpe, tab_eval, tab_plan = st.tabs([
    "nog nodige zekerheid",
    "foutlozepostenequivalent",
    "evaluatie gestratificeerd",
    "planning gestratificeerd",
])

# Configureer het eerste tabblad voor de berekening van de nog nodige zekerheid.
with tab_nnz:
    col_links, col_rechts = st.columns([1, 3])

    with col_links:
        st.subheader("risico-inschatting")
        haro_ihr = st.selectbox(
            "IHR (InHerent Risico)",
            RISK_OPTIES,
            format_func=RISK_LABELS.get,
            key="haro_ihr",
        )
        haro_ibr = st.selectbox(
            "IBR (Interne BeheersingsRisico)",
            RISK_OPTIES,
            format_func=RISK_LABELS.get,
            key="haro_ibr",
        )
        haro_car = st.selectbox(
            "CAR (CijferAnalyseRisico)",
            RISK_OPTIES,
            format_func=RISK_LABELS.get,
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
            format_func=RISK_LABELS.get,
            key="fpe_ihr",
        )
        fpe_ibr = st.selectbox(
            "IBR (Interne BeheersingsRisico)",
            RISK_OPTIES,
            format_func=RISK_LABELS.get,
            key="fpe_ibr",
        )
        fpe_car = st.selectbox(
            "CAR (CijferAnalyseRisico)",
            RISK_OPTIES,
            format_func=RISK_LABELS.get,
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
                        help="Som van de foutfracties van de getrokken posten; dus van de gedane waarnemingen.",
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
                        "materialiteit laag",
                        help="Materialiteit voor het laagstratum.",
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

            # Filter de lege rijen uit de opgeslagen tabel en bereken de populatiewaarden.
            df_clean = (
                eval_num
                .dropna(subset=["naam"])
                .loc[lambda d: d["naam"].str.strip() != ""]
                .dropna(subset=["waarde_laag", "n_laag", "k_laag"])
                .reset_index(drop=True)
                .assign(
                    waarde_hoog=lambda d: d["waarde_hoog"].fillna(0),
                    waarde_populatie=lambda d: (
                        d["waarde_laag"] + d["waarde_hoog"].fillna(0)
                    ),
                    ihr=lambda d: d["ihr"].str.upper(),
                    ibr=lambda d: d["ibr"].str.upper(),
                    car=lambda d: d["car"].str.upper(),
                )
            )

            if df_clean.empty:
                st.session_state.eval_error = (
                    "Vul minimaal één stratum met waarde_laag, n_laag en k_laag in."
                )
            else:
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
                _mat = df_clean["materialiteit"].fillna(0)
                if ((_mat <= 0) | (_mat >= 1)).any():
                    mask = (_mat <= 0) | (_mat >= 1)
                    namen = ", ".join(df_clean.loc[mask, "naam"])
                    st.error(
                        f"materialiteit moet een fractie in (0, 1) zijn bij: {namen}."
                    )
                    st.stop()
                else:
                    try:
                        # Bereken de geconvolueerde resultaten via de rekenmotor.
                        res = eval_stratified(
                            df_clean,
                            model=strat_model,
                            zekerheid=strat_conf,
                            methode="FFT samen",
                            granulariteit=int(strat_gran),
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
                    "materialiteit laag",
                    help="Materialiteit voor het laagstratum. Opgevat als fractie als <= 1 (bijv. 0,01) anders als bedrag in euro\u2019s (bijv. 736.000.000).",
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
            "waarde_hoog",
            "fout_hoog",
            "materialiteit",
            "kosten",
        ]
        invoer_num = invoer_df.copy()
        for _kol in _NL_KOLOMMEN:
            invoer_num[_kol] = _parse_nl_kolom(invoer_num[_kol])

        # Zorg dat de kostenkolom gevuld is (fallback naar 1.0 als leeg):
        invoer_num["kosten"] = invoer_num["kosten"].fillna(1.0)

        df_clean = (
            invoer_num
            .dropna(subset=["naam"])
            .loc[lambda d: d["naam"].str.strip() != ""]
            .dropna(subset=["waarde_laag"])
            .reset_index(drop=True)
            .assign(
                waarde_hoog=lambda d: d["waarde_hoog"].fillna(0),
                waarde_populatie=lambda d: (
                    d["waarde_laag"] + d["waarde_hoog"].fillna(0)
                ),
                ihr=lambda d: d["ihr"].str.upper(),
                ibr=lambda d: d["ibr"].str.upper(),
                car=lambda d: d["car"].str.upper(),
                kosten=lambda d: d["kosten"].fillna(1.0),  # <--- DEZE REGEL IS CRUCIAAL
                materialiteit=lambda d: d.apply(
                    lambda row: (
                        row["materialiteit"] / row["waarde_populatie"]
                        if row["materialiteit"] > 1 and row["waarde_populatie"] > 0
                        else row["materialiteit"]
                    ),
                    axis=1,
                ),
            )
        )

        if df_clean.empty:
            st.error("Vul minimaal één stratum in met naam en waarde_laag.")
            st.stop()

        # Bereken de effectieve rekenmaterialiteit.
        totale_pop_waarde = df_clean["waarde_populatie"].sum()
        reken_mat = (
            plan_mat / totale_pop_waarde
            if plan_mat > 1 and totale_pop_waarde > 0
            else plan_mat
        )

        # Valideer: verwachte foutfractie < materialiteit per stratum.
        probleem = df_clean[
            df_clean["verwachte_foutfractie"] >= df_clean["materialiteit"]
        ]
        if not probleem.empty:
            namen = ", ".join(probleem["naam"].tolist())
            st.error(
                f"Verwachte foutfractie \u2265 materialiteit bij: {namen}. Pas de invoer aan."
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
                granulariteit=int(plan_gran),
                vergelijk=False,
            )["max_fout_convolutie"]
        except ValueError as e:
            st.error(f"Fout bij initiële evaluatie: {e}")
            st.stop()

        # Vul de weergavetabel met de berekende basiswaarden.
        tabel_update = invoer_df.copy()
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
        st.session_state.plan_granulariteit = int(plan_gran)
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
                    f"Optimalisatie voltooid! Eindfout: {fmt_fout} is "
                    "kleiner dan de materialiteit."
                )
            st.rerun()
