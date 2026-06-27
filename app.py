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
LEGE_EVAL_DF = pd.DataFrame(
    {
        "naam": [""] * 8,
        "waarde_laag": [""] * 8,
        "n_laag": [""] * 8,
        "k_laag": [""] * 8,
        "fout_hoog": ["0"] * 8,
        "goed_hoog": ["0"] * 8,
        "ihr": ["H"] * 8,
        "ibr": ["H"] * 8,
        "car": ["H"] * 8,
        "materialiteit": ["0,01"] * 8,
    }
)

# Bereid een leeg sjabloon-dataframe voor om de invoertabel voor de planning te initialiseren.
LEGE_PLAN_DF = pd.DataFrame(
    {
        "naam": [""] * 8,
        "waarde_laag": [""] * 8,
        "verwachte_foutfractie": ["0,001"] * 8,
        "fout_hoog": ["0"] * 8,
        "goed_hoog": ["0"] * 8,
        "ihr": ["H"] * 8,
        "ibr": ["H"] * 8,
        "car": ["H"] * 8,
        "materialiteit": ["0,01"] * 8,
        "kosten": ["1,0"] * 8,  
        "n_laag": [None] * 8,
        "n_laag_extra": [None] * 8,
        "n_laag_tot": [None] * 8,
    }
)

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
    """Pas de Nederlandstalige parsing toe op een volledige pandas Series kolom."""
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
    """Verwerk wijzigingen in de evaluatietabel direct in de sessiestatus en formatteer deze naar de Nederlandse stijl."""
    state = st.session_state["eval_tabel"]
    df = st.session_state.eval_df_saved.copy()
    
    # Pas gewijzigde celwaarden direct en geformatteerd toe op het opgeslagen dataframe.
    for row_idx, changes in state.get("edited_rows", {}).items():
        while row_idx >= len(df):
            df = pd.concat([df, pd.DataFrame([{col: "" for col in df.columns}])], ignore_index=True)
            
        for col, val in changes.items():
            if col in ["waarde_laag", "fout_hoog", "goed_hoog"]:
                df.at[row_idx, col] = _format_nl_auto(val, 2)
            elif col in ["n_laag", "k_laag", "materialiteit"]:
                min_dec = 0 if col == "n_laag" else 2
                df.at[row_idx, col] = _format_nl_auto(val, min_dec)
            else:
                df.at[row_idx, col] = val
                
    # Initialiseer nieuw toegevoegde tabelrijen met logische standaardwaarden en formats.
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row["ihr"] = "H"
        new_row["ibr"] = "H"
        new_row["car"] = "H"
        new_row["materialiteit"] = "0,01"
        new_row["fout_hoog"] = "0"
        new_row["goed_hoog"] = "0"
        
        for col, val in row.items():
            if col in ["waarde_laag", "fout_hoog", "goed_hoog"]:
                new_row[col] = _format_nl_auto(val, 2)
            elif col in ["n_laag", "k_laag", "materialiteit"]:
                min_dec = 0 if col == "n_laag" else 2
                new_row[col] = _format_nl_auto(val, min_dec)
            else:
                new_row[col] = val
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
    # Verwijder geselecteerde rijen en herindexeer het opgeslagen dataframe.
    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)
        
    # Controleer direct bij het invoeren of de fout k_laag de omvang n_laag overschrijdt binnen de actieve rijen.
    te_veel_fouten = []
    for idx, row in df.iterrows():
        n_val = _parse_nl(row["n_laag"])
        k_val = _parse_nl(row["k_laag"])
        naam_cel = str(row["naam"]).strip()
        rij_naam = naam_cel if naam_cel != "" else f"Stratum {idx + 1}"
        if n_val is not None and k_val is not None and k_val > n_val:
            te_veel_fouten.append(rij_naam)

    # Toon direct een foutmelding op het scherm als er een foutieve invoer is gedetecteerd.
    if te_veel_fouten:
        st.session_state.eval_error = (
            f"Invoerfout: de som van de foutfracties (k_laag) mag niet groter zijn "
            f"dan de steekproefomvang (n_laag) bij: {', '.join(te_veel_fouten)}."
        )
    else:
        st.session_state.eval_error = None

    st.session_state.eval_df_saved = df


def on_plan_tabel_change():
    """Verwerk wijzigingen in de planningstabel direct in de sessiestatus en formatteer deze naar de Nederlandse stijl."""
    state = st.session_state["plan_tabel_editor"]
    df = st.session_state.plan_tabel.copy()
    
    # Pas gewijzigde celwaarden in de planningstabel direct toe.
    for row_idx, changes in state.get("edited_rows", {}).items():
        while row_idx >= len(df):
            df = pd.concat([df, pd.DataFrame([{col: "" for col in df.columns}])], ignore_index=True)
            
        for col, val in changes.items():
            if col in ["waarde_laag", "fout_hoog", "goed_hoog"]:
                df.at[row_idx, col] = _format_nl_auto(val, 2)
            elif col in ["verwachte_foutfractie", "materialiteit"]:
                min_dec = 3 if col == "verwachte_foutfractie" else 2
                df.at[row_idx, col] = _format_nl_auto(val, min_dec)
            else:
                df.at[row_idx, col] = val
                
    # Initialiseer nieuw toegevoegde planningsrijen met logische standaardwaarden en formats.
    for row in state.get("added_rows", []):
        new_row = {col: "" for col in df.columns}
        new_row["ihr"] = "H"
        new_row["ibr"] = "H"
        new_row["car"] = "H"
        new_row["materialiteit"] = "0,01"
        new_row["verwachte_foutfractie"] = "0,001"
        new_row["fout_hoog"] = "0"
        new_row["goed_hoog"] = "0"
        
        for col, val in row.items():
            if col in ["waarde_laag", "fout_hoog", "goed_hoog"]:
                new_row[col] = _format_nl_auto(val, 2)
            elif col in ["verwachte_foutfractie", "materialiteit"]:
                min_dec = 3 if col == "verwachte_foutfractie" else 2
                new_row[col] = _format_nl_auto(val, min_dec)
            else:
                new_row[col] = val
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
    # Verwijder geselecteerde rijen uit de planningsdata.
    deleted_indices = state.get("deleted_rows", [])
    if deleted_indices:
        df = df.drop(index=deleted_indices).reset_index(drop=True)
        
    st.session_state.plan_tabel = df


# Bouw de hoofdnavigatie van de applicatie op met vier functionele tabbladen.
st.title("auditstratified")

tab_nnz, tab_fpe, tab_eval, tab_plan = st.tabs(
    [
        "nog nodige zekerheid",
        "foutlozepostenequivalent",
        "evaluatie gestratificeerd",
        "planning gestratificeerd",
    ]
)

# Configureer het eerste tabblad voor de berekening van de nog nodige zekerheid.
with tab_nnz:
    col_links, col_rechts = st.columns([1, 3])

    with col_links:
        st.subheader("risico-inschatting")
        haro_ihr = st.selectbox(
            "IHR (InHerent Risico)", RISK_OPTIES,
            format_func=RISK_LABELS.get, key="haro_ihr"
        )
        haro_ibr = st.selectbox(
            "IBR (Interne BeheersingsRisico)", RISK_OPTIES,
            format_func=RISK_LABELS.get, key="haro_ibr"
        )
        haro_car = st.selectbox(
            "CAR (CijferAnalyseRisico)", RISK_OPTIES,
            format_func=RISK_LABELS.get, key="haro_car"
        )

    with col_rechts:
        st.subheader("Resultaat")
        val = haro_nog_nodige_zekerheid(haro_ihr, haro_ibr, car_optie := haro_car)
        st.metric("nog nodige zekerheid", f"{_nl(val, 4)}")

# Configureer het tweede tabblad voor de berekening van het foutlozepostenequivalent.
with tab_fpe:
    col_links, col_rechts = st.columns([1, 3])

    with col_links:
        st.subheader("risico-inschatting")
        fpe_ihr = st.selectbox(
            "IHR (InHerent Risico)", RISK_OPTIES,
            format_func=RISK_LABELS.get, key="fpe_ihr"
        )
        fpe_ibr = st.selectbox(
            "IBR (Interne BeheersingsRisico)", RISK_OPTIES,
            format_func=RISK_LABELS.get, key="fpe_ibr"
        )
        fpe_car = st.selectbox(
            "CAR (CijferAnalyseRisico)", RISK_OPTIES,
            format_func=RISK_LABELS.get, key="fpe_car"
        )
        
        # Gebruik een tekstveld om de materialiteit in Europese notatie in te voeren.
        fpe_mat_text = st.text_input(
            "Materialiteit",
            value="0,01",
            help="De materialiteitsgrens als fractie (bijv. 0,01).",
            key="fpe_mat_text"
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
            key="strat_conf_text"
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
            key="strat_gran_text"
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
            label_visibility="collapsed"
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
                "Vul de strata in. Lege rijen worden genegeerd. "
                "Kolommen ihr, ibr, car: H = hoog, M = midden, L = laag."
            )
            
            # Toon de invoertabel gekoppeld aan de stabiele gespaarde sessiestructuur en de callback.
            eval_df_invoer = st.data_editor(
                st.session_state.eval_df_saved,
                width="stretch",
                num_rows="dynamic",
                key="eval_tabel",
                on_change=on_eval_tabel_change,
                column_config={
                    "naam": st.column_config.TextColumn("naam", help="Unieke naam van het stratum."),
                    "waarde_laag": st.column_config.TextColumn(
                        "waarde_laag (€)", help="Totale geldswaarde van het laagstratum."
                    ),
                    "n_laag": st.column_config.TextColumn(
                        "n_laag", help="Aantal posten getrokken uit het laagstratum."
                    ),
                    "k_laag": st.column_config.TextColumn(
                        "k_laag", help="Som van de foutfracties van de getrokken posten."
                    ),
                    "fout_hoog": st.column_config.TextColumn(
                        "fout_hoog (€)", help="Totaal foutbedrag van het hoogstratum."
                    ),
                    "goed_hoog": st.column_config.TextColumn(
                        "goed_hoog (€)", help="Totaal goedbedrag van het hoogstratum."
                    ),
                    "ihr": st.column_config.SelectboxColumn(
                        "ihr", help="Inherent risico (H/M/L).", options=RISK_OPTIES, required=True
                    ),
                    "ibr": st.column_config.SelectboxColumn(
                        "ibr", help="Intern beheersingsrisico (H/M/L).", options=RISK_OPTIES, required=True
                    ),
                    "car": st.column_config.SelectboxColumn(
                        "car", help="Cijferanalyserisico (H/M/L).", options=RISK_OPTIES, required=True
                    ),
                    "materialiteit": st.column_config.TextColumn(
                        "materialiteit",
                        help="Materialiteit voor dit stratum (laag + hoog samen).",
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
                    st.markdown(f"<h3 style='text-align: center; margin-bottom: 15px;'>{plot_titel}</h3>", unsafe_allow_html=True)
                    st.pyplot(fig)

                    st.table(
                        pd.DataFrame(
                            {
                                "metriek": ["mw fout", "max fout"],
                                "waarde": [
                                    f"\u20ac {_nl(res['mw_fout_convolutie_geld'], 2)}",
                                    f"\u20ac {_nl(res['max_fout_convolutie_geld'], 2)}",
                                ],
                            }
                        )
                    )
                except Exception as e:
                    st.error(f"Fout bij het weergeven van de resultaten: {e}")
            else:
                st.info("Vul de invoertabel in en klik op \u2018bereken evaluatie\u2019.")

    # Verwerk de berekeningsactie zodra de gebruiker op de knop drukt.
    if strat_knop:
        # Controleer de invoervelden in het linkermenu op wiskundige validiteit.
        if strat_conf is None or strat_conf < 0.5 or strat_conf >= 1.0:
            st.error("Voer een geldige zekerheid in tussen 0,50 en 0,999 (bijv. 0,95).")
        elif strat_gran < 100:
            st.error("Voer een geldige granulariteit in van minimaal 100 (bijv. 10.000).")
        else:
            # Parseer de Nederlandse tekstkolommen naar numerieke waarden voor de berekening.
            _EVAL_NL_KOLOMREN = ["waarde_laag", "n_laag", "k_laag", "fout_hoog", "goed_hoog", "materialiteit"]
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
                    waarde_hoog=lambda d: d["fout_hoog"].fillna(0) + d["goed_hoog"].fillna(0),
                    waarde_populatie=lambda d: d["waarde_laag"] + d["fout_hoog"].fillna(0) + d["goed_hoog"].fillna(0),
                    ihr=lambda d: d["ihr"].str.upper(),
                    ibr=lambda d: d["ibr"].str.upper(),
                    car=lambda d: d["car"].str.upper(),
                )
            )

            if df_clean.empty:
                st.session_state.eval_error = "Vul minimaal één stratum met waarde_laag, n_laag en k_laag in."
            else:
                # Valideer of de foutenomvang (k_laag) de getrokken steekproefomvang (n_laag) niet overschrijdt.
                te_veel_fouten = df_clean[df_clean["k_laag"] > df_clean["n_laag"]]
                if not te_veel_fouten.empty:
                    namen = ", ".join(te_veel_fouten["naam"].tolist())
                    st.session_state.eval_error = f"Aantal fouten (k_laag) mag niet groter zijn dan de steekproefomvang (n_laag) bij stratum: {namen}."
                    
                    # Schakel de actieve subtab-index over naar het resultatenvenster om de foutboodschap te tonen.
                    st.session_state.eval_subtab_index = 1
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

# Configureer het fourth tabblad voor het plannen en live optimaliseren van gestratificeerde steekproeven.
with tab_plan:
    col_inst, col_hoofd = st.columns([1, 3])

    with col_inst:
        st.subheader("instellingen")

        # Gebruik een tekstveld om de materialiteit in Europese notatie in te voeren.
        plan_mat_text = st.text_input(
            "materialiteit",
            value="0,01",
            help="De totale materialiteitsgrens opgevat als fractie als <= 1 (bijv. 0,01), anders als bedrag in euro’s (bijv. 73.600.000).",
            key="plan_mat_text"
        )
        plan_mat = _parse_nl(plan_mat_text)

        # Gebruik een tekstveld om de gewenste zekerheid in Europese notatie in te voeren.
        plan_conf_text = st.text_input(
            "zekerheid",
            value="0,95",
            help="De gewenste statistische zekerheid (bijv. 0,95 = 95%).",
            key="plan_conf_text"
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
            key="plan_gran_text"
        )
        plan_gran_raw = _parse_nl(plan_gran_text)
        plan_gran = int(plan_gran_raw) if plan_gran_raw is not None else 10000

        # Gebruik een selectie-schuifbalk om de live-vertraging direct te tonen met komma-notatie.
        plan_vertraging = st.select_slider(
            "live-vertraging (sec per optimalisatie- ofwel klimstap)",
            options=[0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0],
            value=0.3,
            format_func=lambda x: _nl(x, 2),
            key="plan_vertraging_input"
        )

        knop_col1, knop_col2 = st.columns(2)
        with knop_col1:
            start_knop = st.button(
                "bereken planning",
                type="primary",
                disabled=st.session_state.plan_berekening_actief,
                key="run_plan"
            )
        with knop_col2:
            stop_knop = st.button(
                "afbreken",
                type="secondary",
                disabled=not st.session_state.plan_berekening_actief,
                key="stop_plan"
            )

    with col_hoofd:
        # Presenteer de actuele status van de planningsberekening in een informatieve statusbalk.
        if st.session_state.plan_berekening_actief:
            st.info(st.session_state.plan_status)
        elif "voltooid" in st.session_state.plan_status.lower() or "afgebroken" in st.session_state.plan_status.lower():
            st.success(st.session_state.plan_status)
        else:
            st.info(st.session_state.plan_status)

        st.caption(
            "Vul de witte velden (links) in en klik op \u2018bereken planning\u2019. "
            "De grijze velden (rechts) worden live ingevuld."
        )

        # Toon de planningstabel gekoppeld aan de stabiele opgeslagen planningstructuur en de callback.
        plan_tabel_weergave = st.data_editor(
            st.session_state.plan_tabel,
            width="stretch",
            num_rows="dynamic",
            key="plan_tabel_editor",
            on_change=on_plan_tabel_change,
            disabled=["n_laag", "n_laag_extra", "n_laag_tot"],
            column_config={
                "naam": st.column_config.TextColumn("naam", help="Unieke naam van het stratum."),
                "waarde_laag": st.column_config.TextColumn(
                    "waarde laag (€)",
                    help="Totale geldswaarde van het laagstratum.",
                ),
                "verwachte_foutfractie": st.column_config.TextColumn(
                    "verwachte foutfractie",
                    help="De verwachte foutfractie binnen dit stratum.",
                ),
                "kosten": st.column_config.TextColumn(
                    "kosten per steek",
                    help="Relatieve kosten per steek (bijv. 1,0 voor standaard, 10,0 voor duur).",
                ),
                "fout_hoog": st.column_config.TextColumn(
                    "fout hoog (€)",
                    help="Totaal foutbedrag van het hoogstratum.",
                ),
                "goed_hoog": st.column_config.TextColumn(
                    "goed hoog (€)",
                    help="Totaal goedbedrag van het hoogstratum.",
                ),
                "ihr": st.column_config.SelectboxColumn(
                    "ihr", help="Inherent risico (H/M/L).", options=RISK_OPTIES, required=True
                ),
                "ibr": st.column_config.SelectboxColumn(
                    "ibr", help="Intern beheersingsrisico (H/M/L).", options=RISK_OPTIES, required=True
                ),
                "car": st.column_config.SelectboxColumn(
                    "car", help="Cijferanalyserisico (H/M/L).", options=RISK_OPTIES, required=True
                ),
                "materialiteit": st.column_config.TextColumn(
                    "materialiteit",
                    help="Materialiteit voor dit stratum (laag + hoog samen). Opgevat als fractie als <= 1 (bijv. 0,01) anders als bedrag in euro\u2019s (bijv. 736.000.000)."
                ),
                "n_laag": st.column_config.NumberColumn(
                    "n_laag",
                    help="Basissteekproefomvang per stratum.",
                    disabled=True,
                ),
                "n_laag_extra": st.column_config.NumberColumn(
                    "n_laag_extra",
                    help="Extra posten toegevoegd door de klimoptimalisatie.",
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
            st.error("Voer een geldige materialiteit in groter dan 0 (bijv. 0,01 of 75.000).")
            st.stop()
        if plan_conf is None or plan_conf < 0.5 or plan_conf >= 1.0:
            st.error("Voer een geldige zekerheid in tussen 0,50 en 0,999 (bijv. 0,95).")
            st.stop()
        if plan_gran < 100:
            st.error("Voer een geldige granulariteit in van minimaal 100 (bijv. 10.000).")
            st.stop()

        # Parseer Nederlandstalige tekstkolommen naar float voor berekeningen.
        _NL_KOLOMMEN = ["waarde_laag", "verwachte_foutfractie", "fout_hoog", "goed_hoog", "materialiteit", "kosten"]
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
                waarde_hoog=lambda d: d["fout_hoog"].fillna(0) + d["goed_hoog"].fillna(0),
                waarde_populatie=lambda d: d["waarde_laag"] + d["fout_hoog"].fillna(0) + d["goed_hoog"].fillna(0),
                ihr=lambda d: d["ihr"].str.upper(),
                ibr=lambda d: d["ibr"].str.upper(),
                car=lambda d: d["car"].str.upper(),
                kosten=lambda d: d["kosten"].fillna(1.0) # <--- DEZE REGEL IS CRUCIAAL
            )
        )

        if df_clean.empty:
            st.error("Vul minimaal één stratum in met naam en waarde_laag.")
            st.stop()

        # Bereken de effectieve rekenmaterialiteit.
        totale_pop_waarde = df_clean["waarde_populatie"].sum()
        reken_mat = plan_mat / totale_pop_waarde if plan_mat > 1 and totale_pop_waarde > 0 else plan_mat

        # Valideer: verwachte foutfractie < materialiteit per stratum.
        probleem = df_clean[df_clean["verwachte_foutfractie"] >= df_clean["materialiteit"]]
        if not probleem.empty:
            namen = ", ".join(probleem["naam"].tolist())
            st.error(f"Verwachte foutfractie \u2265 materialiteit bij: {namen}. Pas de invoer aan.")
            st.stop()

        # Bereken de basisplanning op basis van de risico's en de invoerparameters.
        try:
            strata_init = plan_stratified_basis(df_clean, model=plan_model)
        except Exception as e:
            st.error(f"Fout bij basisplanning: {e}")
            st.stop()

        init_fout = eval_stratified(
            strata_init, model=plan_model, zekerheid=plan_conf,
            methode="FFT samen", granulariteit=int(plan_gran), vergelijk=False
        )["max_fout_convolutie"]

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
                strata, model=model,
                klim_granulariteit=gran,
                totale_zekerheid=conf
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
                strata, model=model, zekerheid=conf,
                methode="FFT samen", granulariteit=gran, vergelijk=False
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
