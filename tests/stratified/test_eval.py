import pandas as pd
import pytest

from auditstat.stratified.eval_stratified import (  # pyrefly: ignore[missing-import]
    eval_stratified,
)


def test_eval_stratified_basis():
    """Test de succesvolle uitvoering van de convolutiemotor met standaardwaarden."""
    # Creëer een simpele test-dataset met twee zuivere strata zonder fouten in de steekproef.
    data = pd.DataFrame({
        "naam": ["Stratum A", "Stratum B"],
        "waarde_laag": [100000.0, 50000.0],
        "n_laag": [60, 30],
        "k_laag": [0.0, 0.0],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.02, 0.02],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })

    # Draai de evaluatie met de FFT-methode op het binomiale model.
    resultaat = eval_stratified(
        data, model="binomiaal", zekerheid=0.95, methode="FFT samen", granulariteit=1000
    )

    # Valideer of het resultaat een dictionary is met de juiste wiskundige sleutels.
    assert isinstance(resultaat, dict)
    assert "max_fout_convolutie" in resultaat
    assert "kanskromme" in resultaat
    assert "populatie_totaal" in resultaat

    # Valideer of de berekende maximale fout een logische fractiewaarde heeft tussen nul en één.
    assert 0.0 < resultaat["max_fout_convolutie"] < 1.0

    # Valideer of de populatiewaarde correct is opgeteld.
    assert resultaat["populatie_totaal"] == 150000.0


def test_eval_stratified_foutieve_invoer():
    """Test of de motor netjes weigert bij incomplete of foutieve invoerdata."""
    # Maak een DataFrame met ontbrekende verplichte kolommen, zoals de naam en risico's.
    foute_data = pd.DataFrame({"waarde_laag": [100000.0], "n_laag": [60]})

    # Controleer of de functie een ValueError opwerpt zodra er kolommen missen.
    with pytest.raises(ValueError):
        eval_stratified(foute_data)


def test_eval_stratified_dubbele_namen():
    """Test of de motor weigert om strata met exact dezelfde naam te verwerken."""
    # Creëer een test-dataset waarin twee strata abusievelijk dezelfde naam hebben gekregen.
    data_dubbel = pd.DataFrame({
        "naam": ["Stratum A", "Stratum A"],
        "waarde_laag": [100000.0, 50000.0],
        "n_laag": [60, 30],
        "k_laag": [0.0, 0.0],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.02, 0.02],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })

    # Controleer of de functie dit direct afstraft met een ValueError ter bescherming van de aggregatie.
    with pytest.raises(ValueError):
        eval_stratified(data_dubbel)


def test_vergelijk_convolutie_methoden():
    """Vergelijk de vier convolutiealgoritmen om consistentie te bewijzen."""
    # Creëer een representatieve dataset met meerdere strata en een kleine verwachte fout.
    data_vergelijk = pd.DataFrame({
        "naam": ["Stratum A", "Stratum B", "Stratum C"],
        "waarde_laag": [50000.0, 30000.0, 20000.0],
        "n_laag": [100, 60, 40],
        "k_laag": [1.0, 0.0, 0.0],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "materialiteit": [0.05, 0.05, 0.05],
        "waarde_hoog": [0.0, 0.0, 0.0],
        "fout_hoog": [0.0, 0.0, 0.0],
    })

    # Bereken de referentiewaarde via de gelijktijdige FFT methode.
    ref_res = eval_stratified(
        data_vergelijk, methode="FFT samen", zekerheid=0.95, granulariteit=10000
    )
    ref_fout = ref_res["max_fout_convolutie"]

    # Bereken de resultaten voor de paarsgewijze FFT methode en de directe methode.
    paarsgewijs_res = eval_stratified(
        data_vergelijk, methode="FFT paarsgewijs", zekerheid=0.95, granulariteit=10000
    )
    direct_res = eval_stratified(
        data_vergelijk, methode="direct", zekerheid=0.95, granulariteit=10000
    )

    # Bereken het resultaat via Monte Carlo simulatie met een vaste seed voor reproduceerbaarheid.
    mc_res = eval_stratified(
        data_vergelijk,
        methode="Monte Carlo",
        zekerheid=0.95,
        granulariteit=100000,
        start=42,
    )

    # Eis dat de wiskundig exacte methoden tot op zeer grote precisie overeenkomen met de referentie.
    assert paarsgewijs_res["max_fout_convolutie"] == pytest.approx(
        ref_fout, abs=1e-7
    ), (
        f"FFT paarsgewijs max fout ({paarsgewijs_res['max_fout_convolutie']:.7f}) wijkt af van referentie ({ref_fout:.7f})."
    )
    assert direct_res["max_fout_convolutie"] == pytest.approx(ref_fout, abs=1e-7), (
        f"Direct max fout ({direct_res['max_fout_convolutie']:.7f}) wijkt af van referentie ({ref_fout:.7f})."
    )

    # Eis dat de stochastische Monte Carlo methode binnen een acceptabele foutmarge van de referentie valt.
    assert mc_res["max_fout_convolutie"] == pytest.approx(ref_fout, abs=0.01), (
        f"Monte Carlo max fout ({mc_res['max_fout_convolutie']:.4f}) wijkt te veel af van referentie ({ref_fout:.4f})."
    )


def test_voorbeeld_paul_van_batenburg():
    """Test op basis van het voorbeeld van Paul van Batenburg."""
    vb_paul = pd.DataFrame({
        "naam": ["populatie1", "populatie2"],
        "waarde_laag": [1000000.0, 1000000.0],
        "n_laag": [512, 106],
        "k_laag": [1.0, 2.0],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })
    r = eval_stratified(
        vb_paul, zekerheid=0.95, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.0310, abs=1e-3), (
        f"Paul van Batenburg casus wijkt af. Berekend: {r['max_fout_convolutie']:.5f}, Verwacht: 0.0310"
    )


def test_uitleg_samennemen_beschrijving():
    """Uitleg over samennemen van steekproeven met verschillende risico-inschattingen."""
    example = pd.DataFrame({
        "naam": ["populatie1", "populatie2"],
        "waarde_laag": [100000000.0, 100000000.0],
        "n_laag": [148, 50],
        "k_laag": [1.0, 0.0],
        "ihr": ["H", "L"],
        "ibr": ["H", "L"],
        "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })
    r = eval_stratified(
        example, zekerheid=0.95, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.0184, abs=1e-3), (
        f"Samennemen casus wijkt af. Berekend: {r['max_fout_convolutie']:.5f}, Verwacht: 0.0184"
    )


def test_voorbeelden_niels_van_leeuwen():
    """Uitgebreide voorbeelden voor Niels van Leeuwen met diverse zekerheidsniveaus."""
    sniels = pd.DataFrame({
        "naam": ["x", "y"],
        "waarde_laag": [100.0, 200.0],
        "n_laag": [300, 160],
        "k_laag": [0.0, 0.0],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })

    # Test 95%
    r = eval_stratified(
        sniels, zekerheid=0.95, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.0136, abs=1e-3), (
        f"Niels van Leeuwen (95%) wijkt af. Berekend: {r['max_fout_convolutie']:.5f}"
    )
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.0156, abs=1e-3)

    # Test 90%
    r = eval_stratified(
        sniels, zekerheid=0.90, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.0108, abs=1e-3)
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.0120, abs=1e-3)

    # Test 55%
    r = eval_stratified(
        sniels, zekerheid=0.55, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.004510, abs=1e-4)
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.00418, abs=1e-4)

    # Test 10% (Hier is convolutie voor het eerst groter dan los)
    r = eval_stratified(
        sniels, zekerheid=0.10, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.00118, abs=1e-4)
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.000553, abs=1e-5)


def test_drie_dezelfde_steekproeven():
    """Evaluatie van drie exact gelijke steekproeven."""
    dezelfde_drie = pd.DataFrame({
        "naam": ["s1", "s2", "s3"],
        "waarde_laag": [10.0] * 3,
        "n_laag": [10] * 3,
        "k_laag": [0.0] * 3,
        "ihr": ["H"] * 3,
        "ibr": ["H"] * 3,
        "car": ["H"] * 3,
        "materialiteit": [0.01] * 3,
        "waarde_hoog": [0.0] * 3,
        "fout_hoog": [0.0] * 3,
    })
    r = eval_stratified(
        dezelfde_drie, zekerheid=0.60, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.088, abs=1e-3)
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.0799, abs=1e-3)


def test_tweeendertig_dezelfde_steekproeven():
    """Stress-test: evaluatie van 32 exact gelijke steekproeven (vectorized opbouw)."""
    dezelfde_32 = pd.DataFrame({
        "naam": [f"s{i}" for i in range(1, 33)],
        "waarde_laag": [10.0] * 32,
        "n_laag": [10] * 32,
        "k_laag": [0.0] * 32,
        "ihr": ["H"] * 32,
        "ibr": ["H"] * 32,
        "car": ["H"] * 32,
        "materialiteit": [0.01] * 32,
        "waarde_hoog": [0.0] * 32,
        "fout_hoog": [0.0] * 32,
    })

    # 51% Zekerheid
    r = eval_stratified(
        dezelfde_32, zekerheid=0.51, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.0830, abs=1e-3)
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.0628, abs=1e-3)

    # 95% Zekerheid
    r = eval_stratified(
        dezelfde_32, zekerheid=0.95, methode="FFT samen", granulariteit=100000
    )
    assert r["max_fout_convolutie"] == pytest.approx(0.106, abs=1e-3)
    assert r["vergelijk_met"]["max_fout_los"] == pytest.approx(0.238, abs=1e-3)


def test_lnv_2023_wim_slot():
    """Praktijkcase LNV 2023 (Wim Slot)."""
    lnv_2023 = pd.DataFrame({
        "naam": ["kd_beleid", "lbv", "inkopen"],
        "waarde_laag": [69600741.0, 223532422.0, 12146914.0],
        "n_laag": [8, 22, 1],
        "k_laag": [0.0, 0.0331905, 0.0],
        "ihr": ["H", "H", "H"],
        "ibr": ["H", "H", "H"],
        "car": ["H", "H", "H"],
        "materialiteit": [0.01, 0.01, 0.01],
        "waarde_hoog": [0.0, 0.0, 0.0],
        "fout_hoog": [0.0, 0.0, 0.0],
    })

    r = eval_stratified(
        lnv_2023, zekerheid=0.95, methode="FFT samen", granulariteit=100000
    )

    # De originele R-test gebruikte Monte Carlo, wat kleine stochastische ruis opleverde.
    # Omdat we hier de exacte FFT-methode gebruiken, testen we op de zuivere wiskundige uitkomst van 42,34 miljoen.
    assert r["max_fout_convolutie"] == pytest.approx(0.139, abs=1e-3)
    assert r["max_fout_convolutie_geld"] == pytest.approx(42343061, abs=50.0)


def test_evaluatie_met_hoogstratum():
    """Evaluatie met een 100%-getoetst topstratum inclusief redundantie.

    materialiteit=0.05 betekent: 5% van de totale populatie (600.000) = 30.000 is
    toegestane fout. Na aftrek van fout_hoog=10.000 resteert 20.000 voor het
    laagstratum, dus materialiteit_laag = 20.000 / 500.000 = 0,04.
    """
    test_top = pd.DataFrame({
        "naam": ["stratum_met_top"],
        "waarde_laag": [500000.0],
        "n_laag": [100],
        "k_laag": [1.0],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "waarde_hoog": [100000.0],
        "fout_hoog": [10000.0],
    })

    r_fft = eval_stratified(test_top, zekerheid=0.95, methode="FFT paarsgewijs")
    assert r_fft["mw_fout_convolutie_geld"] == pytest.approx(15000, abs=10.0)


def test_fft_vs_monte_carlo():
    """Controleer of FFT en Monte Carlo nagenoeg dezelfde uitkomsten geven."""
    sniels = pd.DataFrame({
        "naam": ["x", "y"],
        "waarde_laag": [100.0, 200.0],
        "n_laag": [300, 160],
        "k_laag": [0.0, 0.0],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.01, 0.01],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })

    r_mc = eval_stratified(
        sniels, zekerheid=0.95, methode="Monte Carlo", granulariteit=100000, start=1
    )
    r_fft = eval_stratified(
        sniels, zekerheid=0.95, methode="FFT paarsgewijs", granulariteit=10000
    )

    # De resultaten mogen een klein beetje ruis hebben vanwege de Monte Carlo benadering.
    assert r_fft["max_fout_convolutie"] == pytest.approx(
        r_mc["max_fout_convolutie"], abs=0.015
    )


def test_effect_hoogstratum_toevoeging():
    """Controleer effect van toevoegen van posten uit het hoogstratum.

    waarde_laag is bewust veel groter dan waarde_hoog zodat er bij beide scenario's
    (fout_hoog=0 en fout_hoog=waarde_hoog) een positief materialiteitsbudget
    overblijft voor het laagstratum.

    materialiteit=0.2 van populatie 11.000 = 2.200.
    Scenario a: materialiteit_laag = 2.200 / 10.000 = 0,22.
    Scenario b: materialiteit_laag = (2.200 - 1.000) / 10.000 = 0,12.
    Het verschil in max_fout_convolutie = fout_hoog_verschil / totaalgeld = 1.000 / 11.000.
    """
    a = pd.DataFrame({
        "naam": ["x"],
        "waarde_laag": [10000.0],
        "n_laag": [300],
        "k_laag": [0.0],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.2],
        "waarde_hoog": [1000.0],
        "fout_hoog": [0.0],
    })
    b = a.copy()
    b.loc[0, "fout_hoog"] = 1000.0

    ra = eval_stratified(a, methode="FFT samen", vergelijk=False)
    rb = eval_stratified(b, methode="FFT samen", vergelijk=False)

    assert ra["max_fout_convolutie"] < rb["max_fout_convolutie"]

    verwacht_verschil = (1000.0 - 0.0) / (10000.0 + 1000.0)
    werkelijk_verschil = rb["max_fout_convolutie"] - ra["max_fout_convolutie"]
    assert werkelijk_verschil == pytest.approx(verwacht_verschil, abs=1e-3)


# --- Invoercontroles ---
def get_geldige_steekproef():
    """Lever een standaard, geldige steekproef aan voor de invoercontroles."""
    return pd.DataFrame({
        "naam": ["test"],
        "waarde_laag": [1000.0],
        "n_laag": [50],
        "k_laag": [1.0],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "waarde_hoog": [0.0],
        "fout_hoog": [0.0],
    })


def test_invoercontrole_geen_dataframe():
    with pytest.raises(TypeError, match="DataFrame"):
        eval_stratified("geen dataframe")


def test_invoercontrole_ongeldig_model():
    with pytest.raises(ValueError, match="Model moet"):
        eval_stratified(get_geldige_steekproef(), model="frequentist")


def test_invoercontrole_zekerheid_bool():
    with pytest.raises(TypeError, match="boolean"):
        eval_stratified(get_geldige_steekproef(), zekerheid=True)


def test_invoercontrole_zekerheid_geen_getal():
    with pytest.raises(TypeError, match="getal"):
        eval_stratified(get_geldige_steekproef(), zekerheid="0.95")


def test_invoercontrole_zekerheid_negatief():
    with pytest.raises(ValueError, match="segment"):
        eval_stratified(get_geldige_steekproef(), zekerheid=-0.1)


def test_invoercontrole_zekerheid_te_groot():
    with pytest.raises(ValueError, match="segment"):
        eval_stratified(get_geldige_steekproef(), zekerheid=1.5)


def test_invoercontrole_ongeldige_methode():
    with pytest.raises(ValueError, match="Ongeldige methode"):
        eval_stratified(get_geldige_steekproef(), methode="onbekende_methode")


def test_invoercontrole_granulariteit_bool():
    with pytest.raises(TypeError, match="bool"):
        eval_stratified(get_geldige_steekproef(), granulariteit=True)


def test_invoercontrole_granulariteit_geen_int():
    with pytest.raises(TypeError, match="geheel getal"):
        eval_stratified(get_geldige_steekproef(), granulariteit=100.5)


def test_invoercontrole_granulariteit_te_klein():
    with pytest.raises(ValueError, match=">= 1"):
        eval_stratified(get_geldige_steekproef(), granulariteit=0)


def _steekproef_met_extreem_gewichtsverschil():
    """Twee strata met een gewichtsverhouding van 1000:1 (klein stratum = 1.000, groot = 1.000.000)."""
    return pd.DataFrame({
        "naam": ["Groot", "Klein"],
        "waarde_laag": [1_000_000.0, 1_000.0],
        "n_laag": [50, 50],
        "k_laag": [1.0, 0.0],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.05, 0.05],
        "waarde_hoog": [0.0, 0.0],
        "fout_hoog": [0.0, 0.0],
    })


def test_granulariteit_te_laag_voor_extreem_gewichtsverschil_fft():
    """FFT-methoden werpen een ValueError als het kleinste stratum in het rooster verdwijnt.

    Met waarde_laag = [1.000.000, 1.000] en granulariteit=100:
    dx = 1.001.000 / 100 = 10.010 >= 1.000 → crash-voorwaarde is vervuld.
    """
    data = _steekproef_met_extreem_gewichtsverschil()
    for methode in ["FFT samen", "FFT paarsgewijs", "direct"]:
        with pytest.raises(ValueError, match="te laag"):
            eval_stratified(data, methode=methode, granulariteit=100)


def test_granulariteit_te_laag_voor_extreem_gewichtsverschil_monte_carlo_vrijgesteld():
    """Monte Carlo gebruikt geen vast rooster en is vrijgesteld van de granulariteitscheck."""
    data = _steekproef_met_extreem_gewichtsverschil()
    # Mag niet gooien, ongeacht hoe laag de granulariteit is.
    result = eval_stratified(
        data, methode="Monte Carlo", granulariteit=100, vergelijk=False
    )
    assert "max_fout_convolutie" in result


def test_granulariteit_voldoende_voor_extreem_gewichtsverschil():
    """Bij een hoge genoeg granulariteit slaagt de evaluatie gewoon."""
    data = _steekproef_met_extreem_gewichtsverschil()
    # min_benodigde_gran = ceil(1.001.000 / 1.000 * 10) = 10.010 → 20.000 is ruim voldoende.
    result = eval_stratified(
        data, methode="FFT samen", granulariteit=20_000, vergelijk=False
    )
    assert "max_fout_convolutie" in result


def test_invoercontrole_start_bool():
    with pytest.raises(TypeError, match="bool"):
        eval_stratified(get_geldige_steekproef(), start=True)


def test_invoercontrole_start_geen_getal():
    with pytest.raises(TypeError, match="int of een float"):
        eval_stratified(get_geldige_steekproef(), start="1")


def test_invoercontrole_vergelijk_geen_bool():
    with pytest.raises(TypeError, match="boolean"):
        eval_stratified(get_geldige_steekproef(), vergelijk="ja")


def test_invoercontrole_ontbrekende_kolom():
    slecht = get_geldige_steekproef().drop(columns=["k_laag"])
    with pytest.raises(ValueError, match="Ontbrekende kolommen"):
        eval_stratified(slecht)


def test_optionele_kolommen_worden_aangevuld_als_ontbrekend():
    """ihr, ibr, car, waarde_hoog, fout_hoog en materialiteit zijn optioneel.

    Als ze ontbreken worden ze aangevuld met respectievelijk 'H', 'H', 'H', 0.0, 0.0, 0.01.
    """
    minimaal = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
        "n_laag": [50],
        "k_laag": [0],
    })
    resultaat = eval_stratified(minimaal, vergelijk=False)
    steekproeven_uit = resultaat["steekproeven"]
    assert (steekproeven_uit["ihr"] == "H").all()
    assert (steekproeven_uit["ibr"] == "H").all()
    assert (steekproeven_uit["car"] == "H").all()
    assert (steekproeven_uit["waarde_hoog"] == 0.0).all()
    assert (steekproeven_uit["fout_hoog"] == 0.0).all()
    assert (steekproeven_uit["materialiteit"] == 0.01).all()


def test_invoercontrole_dubbele_stratumnamen():
    dubbel = pd.concat([get_geldige_steekproef(), get_geldige_steekproef()])
    with pytest.raises(ValueError, match="stratumnamen"):
        eval_stratified(dubbel)


def test_invoercontrole_lege_dataframe():
    leeg = get_geldige_steekproef().iloc[0:0]
    with pytest.raises(ValueError, match="is leeg"):
        eval_stratified(leeg)


def test_materialiteit_kolom_stuurt_extra_foutloze_posten():
    """De kolom 'materialiteit' stuurt de extra foutloze posten voor het laagstratum.

    Voor strata met niet-maximaal risico (hier: ihr=ibr=car='L') worden extra
    foutloze posten berekend via foutloze_posten_equivalent(). Een strakkere
    stratummaterialiteit levert meer extra posten op — en daarmee een lagere
    maximale foutschatting. Dit bewijst dat de kolom exclusief het laagstratum raakt.
    """
    gemeenschappelijk = dict(
        naam=["Stratum_A"],
        waarde_laag=[100000.0],
        n_laag=[50],
        k_laag=[0.0],
        ihr=["L"],  # Niet-H risico: extra_foutloze_posten > 0
        ibr=["L"],
        car=["L"],
        waarde_hoog=[0.0],
        fout_hoog=[0.0],
    )

    strak = eval_stratified(
        pd.DataFrame({**gemeenschappelijk, "materialiteit": [0.02]}),
        vergelijk=False,
    )
    ruim = eval_stratified(
        pd.DataFrame({**gemeenschappelijk, "materialiteit": [0.10]}),
        vergelijk=False,
    )

    extra_strak = strak["steekproeven"]["extra_foutloze_posten"].iloc[0]
    extra_ruim = ruim["steekproeven"]["extra_foutloze_posten"].iloc[0]

    # Strakkere materialiteit → meer extra foutloze posten.
    assert extra_strak > extra_ruim, (
        "Een strakkere stratummaterialiteit moet meer extra foutloze posten opleveren."
    )
    # Meer extra posten → lagere maximale foutschatting.
    assert strak["max_fout_convolutie"] < ruim["max_fout_convolutie"], (
        "Meer extra foutloze posten moeten de maximale foutschatting verlagen."
    )


def test_eval_kolominhoud_nan_in_numerieke_kolom_wordt_geweigerd():
    """NaN (float) in een numerieke kolom wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "waarde_laag"] = float("nan")
    with pytest.raises(ValueError, match="lege waarden"):
        eval_stratified(data)


@pytest.mark.parametrize("kolom", ["naam", "ihr", "ibr", "car"])
def test_eval_kolominhoud_none_in_tekstkolom_wordt_geweigerd(kolom):
    """None in een tekstkolom wordt als lege waarde herkend en geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, kolom] = None
    with pytest.raises(ValueError, match="lege waarden"):
        eval_stratified(data)


def test_eval_kolominhoud_lege_string_naam_wordt_geweigerd():
    """Een lege string in kolom 'naam' wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "naam"] = ""
    with pytest.raises(ValueError, match="lege strings"):
        eval_stratified(data)


def test_eval_kolominhoud_whitespace_naam_wordt_geweigerd():
    """Een naam die alleen spaties bevat wordt als leeg beschouwd en geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "naam"] = "   "
    with pytest.raises(ValueError, match="lege strings"):
        eval_stratified(data)


def test_eval_kolominhoud_niet_numeriek_wordt_geweigerd():
    """Een niet-numerieke waarde in een numerieke kolom wordt geweigerd."""
    data = get_geldige_steekproef()
    data["n_laag"] = data["n_laag"].astype(str)
    with pytest.raises(ValueError, match="numerieke waarden"):
        eval_stratified(data)


def test_eval_kolominhoud_negatieve_waarde_laag_wordt_geweigerd():
    """Negatieve waarde_laag wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "waarde_laag"] = -1.0
    with pytest.raises(ValueError, match="waarde_laag"):
        eval_stratified(data)


def test_eval_kolominhoud_negatieve_n_laag_wordt_geweigerd():
    """Negatieve n_laag wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "n_laag"] = -1
    with pytest.raises(ValueError, match="n_laag"):
        eval_stratified(data)


def test_eval_kolominhoud_gebroken_n_laag_wordt_geweigerd():
    """Een niet-geheel getal in n_laag wordt geweigerd."""
    data = get_geldige_steekproef()
    data["n_laag"] = data["n_laag"].astype(float)
    data.loc[0, "n_laag"] = 30.5
    with pytest.raises(ValueError, match="gehele getallen"):
        eval_stratified(data)


def test_eval_kolominhoud_negatieve_k_laag_wordt_geweigerd():
    """Negatieve k_laag wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "k_laag"] = -0.5
    with pytest.raises(ValueError, match="k_laag"):
        eval_stratified(data)


def test_eval_kolominhoud_k_laag_groter_dan_n_laag_wordt_geweigerd():
    """k_laag groter dan n_laag wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "n_laag"] = 10
    data.loc[0, "k_laag"] = 11.0
    with pytest.raises(ValueError, match="k_laag"):
        eval_stratified(data)


def test_eval_kolominhoud_negatieve_waarde_hoog_wordt_geweigerd():
    """Negatieve waarde_hoog wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "waarde_hoog"] = -100.0
    with pytest.raises(ValueError, match="waarde_hoog"):
        eval_stratified(data)


def test_eval_kolominhoud_negatieve_fout_hoog_wordt_geweigerd():
    """Negatieve fout_hoog wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "fout_hoog"] = -1.0
    with pytest.raises(ValueError, match="fout_hoog"):
        eval_stratified(data)


def test_eval_kolominhoud_fout_hoog_groter_dan_waarde_hoog_wordt_geweigerd():
    """fout_hoog groter dan waarde_hoog wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "waarde_hoog"] = 500.0
    data.loc[0, "fout_hoog"] = 600.0
    with pytest.raises(ValueError, match="fout_hoog"):
        eval_stratified(data)


@pytest.mark.parametrize("waarde", [0.0, 1.0, -0.01, 1.5])
def test_eval_kolominhoud_materialiteit_kolom_buiten_bereik(waarde):
    """Materialiteit-kolom buiten (0, 1) wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, "materialiteit"] = waarde
    with pytest.raises(ValueError, match="materialiteit"):
        eval_stratified(data)


def test_eval_cross_constraint_materialiteit_te_laag_voor_fout_hoog():
    """materialiteit * waarde_populatie <= fout_hoog geeft een ValueError.

    waarde_laag=1000, waarde_hoog=1000, fout_hoog=100, materialiteit=0.05:
    0.05 * 2000 - 100 = 100 - 100 = 0 → budget is nul, wordt geweigerd.
    """
    data = get_geldige_steekproef()
    data.loc[0, "waarde_hoog"] = 1000.0
    data.loc[0, "fout_hoog"] = 100.0
    data.loc[0, "materialiteit"] = 0.05
    with pytest.raises(ValueError, match="geen foutmarge"):
        eval_stratified(data)


def test_eval_cross_constraint_materialiteit_strikt_kleiner_dan_fout_hoog_gedeeld_door_populatie():
    """materialiteit < fout_hoog / waarde_populatie geeft een ValueError.

    waarde_laag=500, waarde_hoog=500, fout_hoog=100:
    fout_hoog / waarde_populatie = 100 / 1000 = 0,10.
    materialiteit=0.05 < 0,10 → materialiteit_in_geld = 0.05 * 1000 - 100 = -50 < 0 → ValueError.
    """
    data = get_geldige_steekproef()
    data.loc[0, "waarde_laag"] = 500.0
    data.loc[0, "waarde_hoog"] = 500.0
    data.loc[0, "fout_hoog"] = 100.0
    data.loc[0, "materialiteit"] = 0.05  # < 100/1000 = 0.10
    with pytest.raises(ValueError, match="geen foutmarge"):
        eval_stratified(data)


def test_eval_cross_constraint_materialiteit_laag_groter_dan_1():
    """Materialiteit zo hoog dat materialiteit_laag >= 1 geeft een ValueError (geen AssertionError).

    waarde_laag=1000, waarde_hoog=10000, fout_hoog=0, materialiteit=0.9:
    materialiteit_in_geld = 0.9 * 11000 = 9900 > 0 (passeert cross-constraint),
    maar materialiteit_laag = 9900 / 1000 = 9.9 >= 1 → ValueError.
    """
    data = get_geldige_steekproef()
    data.loc[0, "waarde_hoog"] = 10000.0
    data.loc[0, "fout_hoog"] = 0.0
    data.loc[0, "materialiteit"] = 0.9
    with pytest.raises(ValueError, match="laagstratum"):
        eval_stratified(data)


@pytest.mark.parametrize("kolom", ["ihr", "ibr", "car"])
def test_eval_kolominhoud_ongeldig_risico_wordt_geweigerd(kolom):
    """Een ongeldige risicowaarde in ihr, ibr of car wordt geweigerd."""
    data = get_geldige_steekproef()
    data.loc[0, kolom] = "X"
    with pytest.raises(ValueError, match=kolom):
        eval_stratified(data)


def test_materialiteit_kolom_heeft_geen_invloed_op_hoogstratum_eval():
    """De kolom 'materialiteit' beïnvloedt fout_hoog en waarde_hoog in de uitvoer niet.

    Hoewel 'materialiteit' nu op laag+hoog samen slaat, worden fout_hoog en
    waarde_hoog als invoerkolommen ongewijzigd doorgegeven in het uitvoer-DataFrame,
    ongeacht de waarde van 'materialiteit'.

    Beide materialiteit-waarden (0,05 en 0,10) zijn geldig:
    fout_hoog/waarde_populatie = 5.000/150.000 ≈ 0,033, dus de grens is 0,05.
    """
    basis = dict(
        naam=["Stratum_A"],
        waarde_laag=[100000.0],
        n_laag=[50],
        k_laag=[0.0],
        ihr=["H"],
        ibr=["H"],
        car=["H"],
        fout_hoog=[5000.0],
        waarde_hoog=[50000.0],
    )

    for mat_kolom in [0.05, 0.10]:
        resultaat = eval_stratified(
            pd.DataFrame({**basis, "materialiteit": [mat_kolom]}),
            vergelijk=False,
        )
        assert resultaat["steekproeven"]["fout_hoog"].iloc[0] == 5000.0, (
            f"fout_hoog mag niet wijzigen bij materialiteit-kolom={mat_kolom}."
        )
        assert resultaat["steekproeven"]["waarde_hoog"].iloc[0] == 50000.0, (
            f"waarde_hoog mag niet wijzigen bij materialiteit-kolom={mat_kolom}."
        )


def test_edge_case_extreme_fout_kleine_steekproef():
    """
    Test een extreme edge case: n_laag = 1 en k_laag = n_laag
    (100% fouten geconstateerd in een minimale steekproef van 1).
    """
    data_extreem = pd.DataFrame({
        "naam": ["Mini Stratum"],
        "waarde_laag": [100_000.0],
        "n_laag": [1],
        "k_laag": [1.0],  # Alle steekproeven bevatten een fout
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "waarde_hoog": [0.0],
        "fout_hoog": [0.0],
    })

    # Controleer of de motor niet breekt over deze extreme statistische input
    resultaat = eval_stratified(
        data_extreem,
        model="binomiaal",
        zekerheid=0.95,
        methode="FFT samen",
        granulariteit=10_000,
        vergelijk=False,
    )

    assert isinstance(resultaat, dict)
    assert "max_fout_convolutie" in resultaat
    # Bij 100% fouten op 1 eenheid is de onzekerheid maximaal, dus de fout moet fors zijn
    assert resultaat["max_fout_convolutie"] > 0.0
