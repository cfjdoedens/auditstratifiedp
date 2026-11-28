import numpy as np
import pandas as pd
import pytest

from auditstat.geldsteek_gestratificeerd import (
    evalueer_geldsteek_gestratificeerd,
    projecteer_geldsteek_gestratificeerd,
)

GRAN = 20_000
MAT = 1.2e6


@pytest.fixture
def df():
    return pd.DataFrame({
        "naam": ["A", "B", "C"],
        "waarde_laag": [4e7, 1.5e7, 5e6],
        "n_laag": [400, 300, 150],
        "n_tot_nu": [100, 100, 50],
        "k_tot_nu": [1, 0, 0],
    })


def _maxfout(df, k_laag):
    t = df[["naam", "waarde_laag", "n_laag"]].copy()
    t["k_laag"] = k_laag
    return evalueer_geldsteek_gestratificeerd(t, granulariteit=GRAN, vergelijk=False)[
        "max_fout_convolutie_geld"
    ]


def _project(df, **kw):
    return projecteer_geldsteek_gestratificeerd(
        df, granulariteit=GRAN, materialiteit_geld=MAT, **kw
    )


def test_scenarios_zijn_geordend_en_verwacht_volgt_de_formule(df):
    res = _project(df)
    s = res["strata"]
    verwacht = df["k_tot_nu"] * df["n_laag"] / df["n_tot_nu"]
    assert np.allclose(s["k_verwacht"], verwacht)
    assert np.allclose(s["k_optimistisch"], df["k_tot_nu"])
    assert (s["k_optimistisch"] <= s["k_verwacht"]).all()
    assert (s["k_verwacht"] <= s["k_pessimistisch"]).all()
    m = res["samenvatting"]["max_fout_geld"].to_numpy()
    assert m[0] <= m[1] <= m[2]


def test_max_extra_k_komt_overeen_met_brute_force(df):
    res = _project(df)
    verwacht = res["strata"]["k_verwacht"].to_numpy()
    for i in range(len(df)):
        m = int(res["strata"]["n_rest"].iloc[i])
        toelaatbaar = []
        for x in range(m + 1):
            k = verwacht.copy()
            k[i] = df["k_tot_nu"].iloc[i] + x
            toelaatbaar.append(_maxfout(df, k) <= MAT)
        grootste = max(x for x, ok in enumerate(toelaatbaar) if ok)
        assert res["strata"]["max_extra_k"].iloc[i] == grootste


def test_reeds_overschreden_geeft_na(df):
    res = projecteer_geldsteek_gestratificeerd(
        df, granulariteit=GRAN, materialiteit_geld=1.0e5
    )
    assert res["strata"]["max_extra_k"].isna().all()
    assert res["samenvatting"]["overschreden"].all()


def test_niets_meer_te_beoordelen_geeft_alle_scenarios_gelijk(df):
    klaar = df.assign(n_tot_nu=df["n_laag"], k_tot_nu=[2, 1, 0])
    res = _project(klaar)
    assert (res["strata"]["n_rest"] == 0).all()
    assert res["samenvatting"]["max_fout_geld"].nunique() == 1


def test_p_rest_kolom_overschrijft_waargenomen_fractie(df):
    res = _project(df.assign(p_rest=0.05))
    extra = res["strata"]["k_verwacht"] - df["k_tot_nu"]
    assert np.allclose(extra, (df["n_laag"] - df["n_tot_nu"]) * 0.05)


def test_p_rest_kolom_per_stratum_met_terugval_op_waargenomen_fractie(df):
    met_kolom = df.assign(p_rest=[0.0, np.nan, 0.10])
    res = _project(met_kolom)
    s = res["strata"]
    assert np.allclose(s["p_rest"], [0.0, 0.0, 0.10])
    extra = s["k_verwacht"] - df["k_tot_nu"]
    assert np.allclose(extra, s["n_rest"] * s["p_rest"])


def test_p_rest_kolom_lost_nog_niets_beoordeeld_op(df):
    leeg = df.assign(
        n_tot_nu=[0, 100, 50], k_tot_nu=[0, 0, 0], p_rest=[0.01, np.nan, np.nan]
    )
    assert len(_project(leeg)["strata"]) == 3
    with pytest.raises(ValueError, match="p_rest"):
        _project(leeg.assign(p_rest=np.nan))


def test_p_rest_kolom_ongeldig(df):
    with pytest.raises(ValueError, match="p_rest"):
        _project(df.assign(p_rest=[0.1, 1.5, 0.0]))
    with pytest.raises(ValueError, match="p_rest"):
        _project(df.assign(p_rest=["a", "b", "c"]))


def test_pessimistisch_kwantiel_hoger_geeft_meer_fouten(df):
    laag = _project(df, pessimistisch_kwantiel=0.5)["strata"]["k_pessimistisch"]
    hoog = _project(df, pessimistisch_kwantiel=0.95)["strata"]["k_pessimistisch"]
    assert (hoog >= laag).all() and (hoog > laag).any()


def test_pessimistisch_telt_de_haro_posten_mee(df):
    from scipy.stats import betabinom

    laag_risico = df.assign(ihr="M", ibr="M", car="M")
    res = _project(laag_risico)
    s = res["strata"]
    assert (s["extra_foutloze_posten"] > 0).all()
    for r in s.itertuples():
        n_calc = r.n_tot_nu + r.extra_foutloze_posten
        verwacht = betabinom.ppf(
            0.80, r.n_rest, r.k_tot_nu + 1, n_calc - r.k_tot_nu + 1
        )
        assert r.k_pessimistisch == r.k_tot_nu + min(verwacht, r.n_rest)
    # Zonder HARo-posten (H/H/H) is de verdeling breder, dus meer fouten.
    zonder = _project(df)["strata"]
    assert (zonder["extra_foutloze_posten"] == 0).all()
    assert (zonder["k_pessimistisch"] >= s["k_pessimistisch"]).all()


def test_poisson_werkt(df):
    res = _project(df, model="poisson")
    assert len(res["samenvatting"]) == 3


def test_nog_niets_beoordeeld_vereist_p_rest(df):
    leeg = df.assign(n_tot_nu=[0, 100, 50], k_tot_nu=[0, 0, 0])
    with pytest.raises(ValueError, match="p_rest"):
        _project(leeg)
    assert len(_project(leeg.assign(p_rest=0.01))["strata"]) == 3


@pytest.mark.parametrize(
    "wijziging, fragment",
    [
        ({"n_tot_nu": [500, 100, 50]}, "groter dan `n_laag`"),
        ({"k_tot_nu": [101, 0, 0]}, "groter dan `n_tot_nu`"),
        ({"n_tot_nu": [100.5, 100, 50]}, "geheel"),
        ({"k_tot_nu": [-1, 0, 0]}, "negatief"),
    ],
)
def test_ongeldige_invoer(df, wijziging, fragment):
    with pytest.raises(ValueError, match=fragment):
        _project(df.assign(**wijziging))


def test_ontbrekende_kolom_en_types(df):
    with pytest.raises(ValueError, match="n_tot_nu"):
        _project(df.drop(columns="n_tot_nu"))
    with pytest.raises(TypeError):
        projecteer_geldsteek_gestratificeerd([1, 2, 3])
    with pytest.raises(ValueError, match="pessimistisch_kwantiel"):
        _project(df, pessimistisch_kwantiel=1.0)
