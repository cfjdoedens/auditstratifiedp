"""Tests voor plan_stratified."""

import pandas as pd
import pytest

from auditstat.stratified.plan_stratified import (  # pyrefly: ignore[missing-import]
    plan_stratified,
    plan_stratified_basis,
)


def test_happy_flow_succesvolle_planning():
    """De Happy Flow: Succesvolle planning voor meerdere strata[cite: 12]."""
    # Definieer de testinvoer met meerdere strata en bekende fouten[cite: 12].
    test_succes = pd.DataFrame({
        "naam": ["Grote_Klanten", "Kleine_Klanten"],
        "waarde_laag": [300000.0, 500000.0],
        "verwachte_foutfractie": [0.01, 0.015],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.05, 0.05],
        "fout_hoog": [2000.0, 0.0],
        "waarde_hoog": [200000.0, 0.0],
        "kosten": [1.0, 1.0],
    })

    # Voer de planning uit met standaardwaarden[cite: 12].
    resultaat = plan_stratified(
        steekproeven=test_succes, materialiteit=0.05, zekerheid=0.95
    )

    # Verifieer de structuur en integriteit van het resultaat[cite: 12].
    assert isinstance(resultaat, pd.DataFrame), (
        "Het resultaat van plan_stratified moet een pandas DataFrame zijn[cite: 12]."
    )
    assert "n_laag" in resultaat.columns, (
        "De kolom 'n_laag' ontbreekt in het planningsresultaat[cite: 12]."
    )
    assert "kosten" in resultaat.columns, (
        "De kolom 'kosten' ontbreekt in het planningsresultaat[cite: 12]."
    )
    assert (resultaat["kosten"] == 1.0).all(), (
        "Niet alle kostenwaarden komen overeen met de invoer[cite: 12]."
    )


def test_foutmelding_verwachte_foutfractie_te_hoog():
    """Foutmelding: Verwachte foutfractie is al te hoog voor planning[cite: 12]."""
    # Construeer een dataset waarbij de verwachte fout de grenzen overschrijdt[cite: 12].
    test_fout_verwacht = pd.DataFrame({
        "naam": ["Alle_Klanten"],
        "waarde_laag": [1000000.0],
        "verwachte_foutfractie": [0.06],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.07],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })

    # Controleer of de juiste foutmelding wordt opgeworpen[cite: 12].
    with pytest.raises(ValueError, match="Totale verwachte fout in de laagstrata"):
        plan_stratified(test_fout_verwacht, materialiteit=0.05)


def test_foutmelding_bekende_fout_hoogstratum_nekt_materialiteit():
    """Foutmelding: Bekende fout in hoogstratum nekt de algehele materialiteit[cite: 12].

    materialiteit_kolom=0.10: 0.10 * 1.000.000 = 100.000 > 60.000 → per-stratum check passeert[cite: 12].
    Algehele check: fout_hoog=60.000 > materialiteit_param=0.05 * 1.000.000=50.000 → ValueError[cite: 12].
    """
    # Definieer data met een te hoge bekende fout in het hoogstratum[cite: 12].
    test_fout_hoog = pd.DataFrame({
        "naam": ["Alle_Klanten"],
        "waarde_laag": [800000.0],
        "verwachte_foutfractie": [0.01],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.10],
        "fout_hoog": [60000.0],
        "waarde_hoog": [200000.0],
        "kosten": [1.0],
    })

    # Verifieer dat de algehele materialiteitsgrens bewaakt wordt[cite: 12].
    with pytest.raises(ValueError, match="Bekende fout in de hoogstrata"):
        plan_stratified(test_fout_hoog, materialiteit=0.05)


def test_foutmelding_inconsistentie_op_stratum_niveau():
    """Foutmelding: Inconsistentie op stratum-niveau (verwachte fout > materialiteit)[cite: 12]."""
    # Maak een dataset aan met een te hoge verwachte foutfractie ten opzichte van de materialiteit[cite: 12].
    test_inconsistent = pd.DataFrame({
        "naam": ["Stratum1"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.03],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.02],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })

    # Controleer of de stratuminconsistentie wordt afgevangen[cite: 12].
    with pytest.raises(
        ValueError, match="Verwachte foutfractie >= de omgerekende materialiteit"
    ):
        plan_stratified(test_inconsistent, materialiteit=0.05)


def test_attribuutverificatie_geretourneerde_dataset():
    """Attribuutverificatie op de geretourneerde dataset[cite: 12]."""
    # Zet een eenvoudige dataset klaar om attributen te testen[cite: 12].
    test_data = pd.DataFrame({
        "naam": ["Simple"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.001],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })

    # Voer de planning uit en controleer de attributen[cite: 12].
    resultaat = plan_stratified(test_data, materialiteit=0.05)
    assert isinstance(resultaat, pd.DataFrame), (
        "Het geretourneerde object moet een DataFrame zijn[cite: 12]."
    )
    assert "geplande_max_fout_totaal" in resultaat.attrs, (
        "Het attribuut 'geplande_max_fout_totaal' ontbreekt[cite: 12]."
    )


def test_foutmelding_dubbele_stratumnamen():
    """Foutmelding: Dubbele stratumnamen in de invoer[cite: 12]."""
    # Maak een dataset met dubbele namen aan[cite: 12].
    test_dubbel = pd.DataFrame({
        "naam": ["Stratum_A", "Stratum_A"],
        "waarde_laag": [100000.0, 200000.0],
        "verwachte_foutfractie": [0.01, 0.01],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.05, 0.05],
        "fout_hoog": [0.0, 0.0],
        "waarde_hoog": [0.0, 0.0],
        "kosten": [1.0, 1.0],
    })

    # Verifieer dat dubbele namen worden geweigerd[cite: 12].
    with pytest.raises(ValueError, match="stratumnamen komen vaker dan"):
        plan_stratified(test_dubbel, materialiteit=0.05)


# Lever een minimale, geldige invoer voor de parametertests.
@pytest.fixture
def basis_plan_invoer():
    """Fixture voor minimale geldige invoer[cite: 12]."""
    return pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.01],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })


def test_plan_ongeldig_model(basis_plan_invoer):
    """Foutmelding: Ongeldig model opgegeven[cite: 12]."""
    # Test of een ongeldig model direct wordt afgewezen[cite: 12].
    with pytest.raises(ValueError, match="Model moet"):
        plan_stratified(basis_plan_invoer, model="frequentist", materialiteit=0.05)


# Test alle foutieve invoer voor de parameter materialiteit in één keer.
@pytest.mark.parametrize(
    "foute_waarde, exc_type, match_tekst",
    [
        (True, TypeError, "boolean"),
        ("0.05", TypeError, "getal"),
        (-0.01, ValueError, "Materialiteit moet >= 0"),
        (1.5, ValueError, "Materialiteit moet <= 1"),
    ],
)
def test_plan_materialiteit_invoer(
    basis_plan_invoer, foute_waarde, exc_type, match_tekst
):
    """Invoercontrole op de parameter materialiteit[cite: 12]."""
    # Voer de test uit met de schone dataset uit de fixture en de foute parameter[cite: 12].
    with pytest.raises(exc_type, match=match_tekst):
        plan_stratified(basis_plan_invoer, materialiteit=foute_waarde)


# Test alle foutieve invoer voor de parameter zekerheid in één keer.
@pytest.mark.parametrize(
    "foute_waarde, exc_type, match_tekst",
    [
        (True, TypeError, "boolean"),
        ("0.95", TypeError, "getal"),
        (-0.1, ValueError, "Zekerheid moet >= 0"),
        (1.5, ValueError, "Zekerheid moet <= 1"),
    ],
)
def test_plan_zekerheid_invoer(basis_plan_invoer, foute_waarde, exc_type, match_tekst):
    """Invoercontrole op de parameter zekerheid[cite: 12]."""
    # Weer wordt de functie geïnjecteerd met de dataset[cite: 12].
    with pytest.raises(exc_type, match=match_tekst):
        plan_stratified(basis_plan_invoer, materialiteit=0.05, zekerheid=foute_waarde)


# Test alle foutieve invoer voor de parameter granulariteit in één keer.
@pytest.mark.parametrize(
    "foute_waarde, exc_type, match_tekst",
    [
        (True, TypeError, "boolean"),
        (100.5, TypeError, "geheel getal"),
        (-1, ValueError, "Granulariteit moet > 0"),
    ],
)
def test_plan_granulariteit_invoer(
    basis_plan_invoer, foute_waarde, exc_type, match_tekst
):
    """Invoercontrole op de parameter granulariteit[cite: 12]."""
    # Voer de test uit met een schone dataset en foutieve granulariteit[cite: 12].
    with pytest.raises(exc_type, match=match_tekst):
        plan_stratified(
            basis_plan_invoer, materialiteit=0.05, granulariteit=foute_waarde
        )


def test_plan_verwachte_fout_laagstrata_alleen_te_groot():
    """Foutmelding: Verwachte fout in laagstrata overschrijdt de algehele materialiteit[cite: 12]."""
    # Maak data aan waarbij de verwachte fout in de laagstrata te hoog is[cite: 12].
    data = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [1000000.0],
        "verwachte_foutfractie": [0.06],  # 6% verwacht[cite: 12]
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [
            0.07
        ],  # stratummaterialiteit hoger: geen stratum-inconsistentie[cite: 12]
        "fout_hoog": [0.0],  # geen bekende fout: check 1 valt niet[cite: 12]
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })
    # Valideer dat de algehele check faalt[cite: 12].
    with pytest.raises(ValueError, match="laagstrata alleen al"):
        plan_stratified(data, materialiteit=0.05)


# Genereer een representatieve dataset met twee strata voor de simulatietesten.
@pytest.fixture
def basis_steekproeven():
    """Fixture voor een representatieve dataset[cite: 12]."""
    return pd.DataFrame({
        "naam": ["Subsidies", "Inkoop"],
        "waarde_laag": [1000000.0, 500000.0],
        "verwachte_foutfractie": [0.01, 0.005],
        "ihr": ["M", "L"],
        "ibr": ["M", "L"],
        "car": ["M", "L"],
        "materialiteit": [0.03, 0.03],
        "fout_hoog": [0.0, 0.0],
        "waarde_hoog": [100000.0, 50000.0],
        "kosten": [1.0, 1.0],
    })


def test_plan_stratified_binomiaal_sluitend(basis_steekproeven):
    """Verifieer of plan_stratified een exact sluitend steekproefplan genereert voor binomiaal[cite: 12]."""
    # Gebruik de fixture dataset direct voor de calculatie[cite: 12].
    resultaat = plan_stratified(
        steekproeven=basis_steekproeven,
        materialiteit=0.03,
        zekerheid=0.95,
        model="binomiaal",
        granulariteit=10000,
    )

    # Controleer of het resultaat aan de materialiteitsgrens voldoet met pytest.approx[cite: 12].
    assert isinstance(resultaat, pd.DataFrame), (
        "Het planningsresultaat moet een DataFrame zijn[cite: 12]."
    )
    assert "n_laag" in resultaat.columns, "Kolom 'n_laag' ontbreekt[cite: 12]."
    geplande_fout = resultaat.attrs["geplande_max_fout_totaal"]
    assert geplande_fout == pytest.approx(0.03, abs=0.03) or geplande_fout <= 0.03, (
        f"Geplande maximale fout ({geplande_fout:.5f}) overschrijdt de materialiteit (0.03)[cite: 12]."
    )


def test_plan_stratified_poisson_strakke_marges(basis_steekproeven):
    """Verifieer of plan_stratified correct werkt met de poisson verdeling en strakke marges[cite: 12]."""
    # Maak expliciet een kopie van de fixture dataset om mutatie side-effects te voorkomen[cite: 12].
    test_data = basis_steekproeven.copy()
    test_data["verwachte_foutfractie"] = [0.02, 0.01]

    # Voer de planning uit voor poisson[cite: 12].
    resultaat = plan_stratified(
        steekproeven=test_data,
        materialiteit=0.05,
        zekerheid=0.95,
        model="poisson",
        granulariteit=10000,
    )

    # Verifieer de uitkomst en marges[cite: 12].
    assert isinstance(resultaat, pd.DataFrame), (
        "Het planningsresultaat moet een DataFrame zijn[cite: 12]."
    )
    assert "n_laag" in resultaat.columns, "Kolom 'n_laag' ontbreekt[cite: 12]."
    geplande_fout = resultaat.attrs["geplande_max_fout_totaal"]
    assert geplande_fout <= 0.05, (
        f"Geplande maximale fout voor Poisson ({geplande_fout:.5f}) overschrijdt de materialiteit (0.05)[cite: 12]."
    )


def test_materialiteit_kolom_stuurt_laagstratum_n_basis():
    """De kolom 'materialiteit' stuurt de steekproefomvang van het laagstratum[cite: 12].

    materialiteit slaat op laag+hoog samen; voor strata zonder hoogstratum (waarde_hoog=0,
    fout_hoog=0) is materialiteit_laag gelijk aan materialiteit_kolom zelf[cite: 12].
    Een strakkere stratummaterialiteit vereist daardoor meer steken in het laagstratum[cite: 12].
    """
    # Definieer de gemeenschappelijke basisparameters[cite: 12].
    gemeenschappelijk = dict(
        naam=["Stratum_A"],
        waarde_laag=[500000.0],
        verwachte_foutfractie=[0.01],
        ihr=["H"],
        ibr=["H"],
        car=["H"],
        fout_hoog=[0.0],
        waarde_hoog=[0.0],
        kosten=[1.0],
    )

    # Bereken de basisomvang voor strakke en ruime materialiteit[cite: 12].
    strak = plan_stratified_basis(
        pd.DataFrame({**gemeenschappelijk, "materialiteit": [0.03]})
    )
    ruim = plan_stratified_basis(
        pd.DataFrame({**gemeenschappelijk, "materialiteit": [0.10]})
    )

    # Valideer de invloed op n_basis[cite: 12].
    n_basis_strak = strak["n_basis"].iloc[0]
    n_basis_ruim = ruim["n_basis"].iloc[0]
    assert n_basis_strak > n_basis_ruim, (
        f"Een strakkere materialiteit (0.03) moet meer steken vereisen dan een ruime (0.10). "
        f"Gekregen: strak={n_basis_strak}, ruim={n_basis_ruim}[cite: 12]"
    )


def test_materialiteit_kolom_heeft_geen_invloed_op_hoogstratum():
    """De kolom 'materialiteit' heeft geen invloed op de verwerking van het hoogstratum[cite: 12].

    materialiteit slaat op laag+hoog samen; fout_hoog en waarde_hoog worden
    als invoerkolommen ongewijzigd doorgegeven ongeacht de waarde van 'materialiteit'[cite: 12].
    """
    # Stel de basisconfiguratie op[cite: 12].
    basis = dict(
        naam=["Stratum_A"],
        waarde_laag=[400000.0],
        verwachte_foutfractie=[0.01],
        ihr=["H"],
        ibr=["H"],
        car=["H"],
        fout_hoog=[8000.0],
        waarde_hoog=[100000.0],
        kosten=[1.0],
    )

    # Test verschillende materialiteitswaarden[cite: 12].
    for mat_kolom in [0.04, 0.10]:
        resultaat = plan_stratified(
            pd.DataFrame({**basis, "materialiteit": [mat_kolom]}),
            materialiteit=0.05,
            zekerheid=0.95,
        )
        assert resultaat["fout_hoog"].iloc[0] == 8000.0, (
            f"fout_hoog mag niet wijzigen bij materialiteit-kolom={mat_kolom}[cite: 12]."
        )
        assert resultaat["waarde_hoog"].iloc[0] == 100000.0, (
            f"waarde_hoog mag niet wijzigen bij materialiteit-kolom={mat_kolom}[cite: 12]."
        )


@pytest.fixture
def geldige_invoer():
    """Minimale geldige invoer voor kolominhoudstests[cite: 12]."""
    return pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.01],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })


def test_kolominhoud_nan_in_numerieke_kolom_wordt_geweigerd(geldige_invoer):
    """NaN (float) in een numerieke kolom wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "waarde_laag"] = float("nan")
    with pytest.raises(ValueError, match="lege waarden"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("kolom", ["naam", "ihr", "ibr", "car"])
def test_kolominhoud_none_in_tekstkolom_wordt_geweigerd(geldige_invoer, kolom):
    """None in een tekstkolom wordt als lege waarde herkend en geweigerd[cite: 12]."""
    geldige_invoer.loc[0, kolom] = None
    with pytest.raises(ValueError, match="lege waarden"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_lege_string_naam_wordt_geweigerd(geldige_invoer):
    """Een lege string in kolom 'naam' wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "naam"] = ""
    with pytest.raises(ValueError, match="lege strings"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_whitespace_naam_wordt_geweigerd(geldige_invoer):
    """Een naam die alleen spaties bevat wordt als leeg beschouwd en geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "naam"] = "   "
    with pytest.raises(ValueError, match="lege strings"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_niet_numeriek_wordt_geweigerd(geldige_invoer):
    """Een niet-numerieke waarde in een numerieke kolom wordt geweigerd[cite: 12]."""
    geldige_invoer["waarde_laag"] = geldige_invoer["waarde_laag"].astype(str)
    with pytest.raises(ValueError, match="numerieke waarden"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_negatieve_waarde_laag_wordt_geweigerd(geldige_invoer):
    """Negatieve waarde_laag wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "waarde_laag"] = -1.0
    with pytest.raises(ValueError, match="waarde_laag"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("waarde", [-0.01, 1.0, 1.5])
def test_kolominhoud_verwachte_foutfractie_buiten_bereik(geldige_invoer, waarde):
    """verwachte_foutfractie buiten [0, 1) wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "verwachte_foutfractie"] = waarde
    with pytest.raises(ValueError, match="verwachte_foutfractie"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("waarde", [0.0, -1.0])
def test_kolominhoud_kosten_niet_positief_wordt_geweigerd(geldige_invoer, waarde):
    """Kosten <= 0 wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "kosten"] = waarde
    with pytest.raises(ValueError, match="kosten"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_negatieve_waarde_hoog_wordt_geweigerd(geldige_invoer):
    """Negatieve waarde_hoog wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "waarde_hoog"] = -100.0
    with pytest.raises(ValueError, match="waarde_hoog"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_negatieve_fout_hoog_wordt_geweigerd(geldige_invoer):
    """Negatieve fout_hoog wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "fout_hoog"] = -1.0
    with pytest.raises(ValueError, match="fout_hoog"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_fout_hoog_groter_dan_waarde_hoog_wordt_geweigerd(geldige_invoer):
    """fout_hoog groter dan waarde_hoog wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "waarde_hoog"] = 1000.0
    geldige_invoer.loc[0, "fout_hoog"] = 2000.0
    with pytest.raises(ValueError, match="fout_hoog"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("waarde", [0.0, 1.0, -0.01, 1.5])
def test_kolominhoud_materialiteit_kolom_buiten_bereik(geldige_invoer, waarde):
    """Materialiteit-kolom buiten (0, 1) wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, "materialiteit"] = waarde
    with pytest.raises(ValueError, match="materialiteit"):
        plan_stratified(geldige_invoer, materialiteit=0.5)


@pytest.mark.parametrize("kolom", ["ihr", "ibr", "car"])
def test_kolominhoud_ongeldig_risico_wordt_geweigerd(geldige_invoer, kolom):
    """Een ongeldige risicowaarde in ihr, ibr of car wordt geweigerd[cite: 12]."""
    geldige_invoer.loc[0, kolom] = "X"
    with pytest.raises(ValueError, match=kolom):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_verwachte_foutfractie_wordt_aangevuld_als_ontbrekend():
    """verwachte_foutfractie is optioneel: ontbrekende kolom krijgt standaard 0.001."""
    zonder_verwachte_fout = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
    })
    resultaat = plan_stratified(zonder_verwachte_fout, materialiteit=0.05)
    assert (resultaat["verwachte_foutfractie"] == 0.001).all()


def test_kosten_worden_aangevuld_als_ontbrekend():
    """kosten is optioneel: ontbrekende kolom krijgt standaard 1.0."""
    zonder_kosten = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
    })
    resultaat = plan_stratified(zonder_kosten, materialiteit=0.05)
    assert (resultaat["kosten"] == 1.0).all()


def test_ihr_ibr_car_worden_aangevuld_als_ontbrekend():
    """ihr, ibr en car zijn optioneel: ontbrekende kolommen krijgen standaard 'H'."""
    zonder_risicokolommen = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.01],
        "materialiteit": [0.05],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })
    resultaat = plan_stratified(zonder_risicokolommen, materialiteit=0.05)
    assert (resultaat["ihr"] == "H").all()
    assert (resultaat["ibr"] == "H").all()
    assert (resultaat["car"] == "H").all()


def test_kosten_invloed_op_allocatie():
    """Verifieer of het algoritme prioriteit geeft aan een goedkoop stratum[cite: 12]."""
    test_kosten = pd.DataFrame({
        "naam": ["Duur_Stratum", "Goedkoop_Stratum"],
        "waarde_laag": [500000.0, 500000.0],
        "verwachte_foutfractie": [0.01, 0.01],
        "ihr": ["H", "H"],
        "ibr": ["H", "H"],
        "car": ["H", "H"],
        "materialiteit": [0.05, 0.05],
        "fout_hoog": [0.0, 0.0],
        "waarde_hoog": [0.0, 0.0],
        # Het ene stratum kost 100 keer zoveel om te controleren als het andere.
        "kosten": [100.0, 1.0],
    })

    resultaat = plan_stratified(
        steekproeven=test_kosten, materialiteit=0.03, granulariteit=10000
    )

    n_duur = resultaat.loc[resultaat["naam"] == "Duur_Stratum", "n_laag"].values[0]
    n_goedkoop = resultaat.loc[
        resultaat["naam"] == "Goedkoop_Stratum", "n_laag"
    ].values[0]

    # Omdat het ene stratum zoveel goedkoper is, zou het veel vaker gekozen moeten zijn[cite: 12].
    assert n_goedkoop > n_duur, (
        "Het planningsalgoritme hield onvoldoende rekening met de stuurkracht van uitvoeringskosten[cite: 12]!"
    )
