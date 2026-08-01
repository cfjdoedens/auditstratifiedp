import pandas as pd
import pytest

from auditstratified.plan_stratified import plan_stratified, plan_stratified_basis


def test_happy_flow_succesvolle_planning():
    """De Happy Flow: Succesvolle planning voor meerdere strata."""
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

    resultaat = plan_stratified(
        steekproeven=test_succes, materialiteit=0.05, zekerheid=0.95
    )

    assert isinstance(resultaat, pd.DataFrame)
    assert "n_laag" in resultaat.columns
    assert "kosten" in resultaat.columns
    assert (resultaat["kosten"] == 1.0).all()


def test_foutmelding_verwachte_foutfractie_te_hoog():
    """Foutmelding: Verwachte foutfractie is al te hoog voor planning."""
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

    with pytest.raises(ValueError, match="Totale verwachte fout in de laagstrata"):
        plan_stratified(test_fout_verwacht, materialiteit=0.05)


def test_foutmelding_bekende_fout_hoogstratum_nekt_materialiteit():
    """Foutmelding: Bekende fout in hoogstratum nekt de materialiteit."""
    test_fout_hoog = pd.DataFrame({
        "naam": ["Alle_Klanten"],
        "waarde_laag": [800000.0],
        "verwachte_foutfractie": [0.01],
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [60000.0],
        "waarde_hoog": [200000.0],
        "kosten": [1.0],
    })

    with pytest.raises(ValueError, match="Bekende fout in de hoogstrata"):
        plan_stratified(test_fout_hoog, materialiteit=0.05)


def test_foutmelding_inconsistentie_op_stratum_niveau():
    """Foutmelding: Inconsistentie op stratum-niveau (verwachte fout > materialiteit)."""
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

    with pytest.raises(
        ValueError, match="Verwachte foutfractie >= de stratummaterialiteit"
    ):
        plan_stratified(test_inconsistent, materialiteit=0.05)


def test_attribuutverificatie_geretourneerde_dataset():
    """Attribuutverificatie op de geretourneerde dataset."""
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

    resultaat = plan_stratified(test_data, materialiteit=0.05)
    assert isinstance(resultaat, pd.DataFrame)
    assert "geplande_max_fout_totaal" in resultaat.attrs


def test_foutmelding_dubbele_stratumnamen():
    """Foutmelding: Dubbele stratumnamen in de invoer."""
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

    with pytest.raises(ValueError, match="stratumnamen komen vaker dan"):
        plan_stratified(test_dubbel, materialiteit=0.05)


# Lever een minimale, geldige invoer voor de parametertests.
@pytest.fixture
def basis_plan_invoer():
    """Fixture voor minimale geldige invoer."""
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
    """Foutmelding: Ongeldig model opgegeven."""
    # Test of een ongeldig model direct wordt afgewezen.
    with pytest.raises(AssertionError, match="Model moet"):
        plan_stratified(basis_plan_invoer, model="frequentist", materialiteit=0.05)


# Test alle foutieve invoer voor de parameter materialiteit in één keer.
@pytest.mark.parametrize(
    "foute_waarde, match_tekst",
    [
        (True, "boolean"),
        ("0.05", "getal"),
        (-0.01, "Materialiteit moet >= 0"),
        (1.5, "Materialiteit moet <= 1"),
    ],
)
def test_plan_materialiteit_invoer(basis_plan_invoer, foute_waarde, match_tekst):
    """Invoercontrole op de parameter materialiteit."""
    # Voer de test uit met de schone dataset uit de fixture en de foute parameter.
    with pytest.raises(AssertionError, match=match_tekst):
        plan_stratified(basis_plan_invoer, materialiteit=foute_waarde)


# Test alle foutieve invoer voor de parameter zekerheid in één keer.
@pytest.mark.parametrize(
    "foute_waarde, match_tekst",
    [
        (True, "boolean"),
        ("0.95", "getal"),
        (-0.1, "Zekerheid moet >= 0"),
        (1.5, "Zekerheid moet <= 1"),
    ],
)
def test_plan_zekerheid_invoer(basis_plan_invoer, foute_waarde, match_tekst):
    """Invoercontrole op de parameter zekerheid."""
    # Weer wordt de functie geïnjecteerd met de dataset.
    with pytest.raises(AssertionError, match=match_tekst):
        plan_stratified(basis_plan_invoer, materialiteit=0.05, zekerheid=foute_waarde)


# Test alle foutieve invoer voor de parameter granulariteit in één keer.
@pytest.mark.parametrize(
    "foute_waarde, match_tekst",
    [
        (True, "boolean"),
        (100.5, "geheel getal"),
        (-1, "Granulariteit moet > 0"),
    ],
)
def test_plan_granulariteit_invoer(basis_plan_invoer, foute_waarde, match_tekst):
    """Invoercontrole op de parameter granulariteit."""
    # Voer de test uit met een schone dataset en foutieve granulariteit.
    with pytest.raises(AssertionError, match=match_tekst):
        plan_stratified(
            basis_plan_invoer, materialiteit=0.05, granulariteit=foute_waarde
        )


def test_plan_verwachte_fout_laagstrata_alleen_te_groot():
    """Foutmelding: Verwachte fout in laagstrata overschrijdt de algehele materialiteit."""
    data = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [1000000.0],
        "verwachte_foutfractie": [0.06],  # 6% verwacht
        "ihr": ["H"],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [
            0.07
        ],  # stratummaterialiteit hoger: geen stratum-inconsistentie
        "fout_hoog": [0.0],  # geen bekende fout: check 1 valt niet
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })
    with pytest.raises(ValueError, match="laagstrata alleen al"):
        plan_stratified(data, materialiteit=0.05)


# Genereer een representatieve dataset met twee strata voor de simulatietesten.
@pytest.fixture
def basis_steekproeven():
    """Fixture voor een representatieve dataset."""
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
    """Verifieer of plan_stratified een exact sluitend steekproefplan genereert voor binomiaal."""
    # Gebruik de fixture dataset direct voor de calculatie.
    resultaat = plan_stratified(
        steekproeven=basis_steekproeven,
        materialiteit=0.03,
        zekerheid=0.95,
        model="binomiaal",
        granulariteit=10000,
    )

    assert isinstance(resultaat, pd.DataFrame)
    assert "n_laag" in resultaat.columns
    assert resultaat.attrs["geplande_max_fout_totaal"] <= 0.03


def test_plan_stratified_poisson_strakke_marges(basis_steekproeven):
    """Verifieer of plan_stratified correct werkt met de poisson verdeling en strakke marges."""
    # Maak expliciet een kopie van de fixture dataset om mutatie side-effects te voorkomen.
    test_data = basis_steekproeven.copy()
    test_data["verwachte_foutfractie"] = [0.02, 0.01]

    resultaat = plan_stratified(
        steekproeven=test_data,
        materialiteit=0.05,
        zekerheid=0.95,
        model="poisson",
        granulariteit=10000,
    )

    assert isinstance(resultaat, pd.DataFrame)
    assert "n_laag" in resultaat.columns
    assert resultaat.attrs["geplande_max_fout_totaal"] <= 0.05


def test_materialiteit_kolom_stuurt_laagstratum_n_basis():
    """De kolom 'materialiteit' stuurt uitsluitend de steekproefomvang van het laagstratum.

    Een strakkere stratummaterialiteit vereist meer steken in het laagstratum.
    Dit bewijst dat de kolom exclusief op het laagstratum werkt via drawsneeded().
    """
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

    strak = plan_stratified_basis(
        pd.DataFrame({**gemeenschappelijk, "materialiteit": [0.03]})
    )
    ruim = plan_stratified_basis(
        pd.DataFrame({**gemeenschappelijk, "materialiteit": [0.10]})
    )

    assert strak["n_basis"].iloc[0] > ruim["n_basis"].iloc[0], (
        "Een strakkere stratummaterialiteit moet meer steken vereisen in het laagstratum."
    )


def test_materialiteit_kolom_heeft_geen_invloed_op_hoogstratum():
    """De kolom 'materialiteit' heeft geen invloed op de verwerking van het hoogstratum.

    fout_hoog en waarde_hoog worden ongewijzigd doorgegeven ongeacht de waarde
    van de 'materialiteit'-kolom. Dit bewijst dat de kolom exclusief op het
    laagstratum van toepassing is.
    """
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

    for mat_kolom in [0.04, 0.10]:
        resultaat = plan_stratified(
            pd.DataFrame({**basis, "materialiteit": [mat_kolom]}),
            materialiteit=0.05,
            zekerheid=0.95,
        )
        assert resultaat["fout_hoog"].iloc[0] == 8000.0, (
            f"fout_hoog mag niet wijzigen bij materialiteit-kolom={mat_kolom}."
        )
        assert resultaat["waarde_hoog"].iloc[0] == 100000.0, (
            f"waarde_hoog mag niet wijzigen bij materialiteit-kolom={mat_kolom}."
        )


@pytest.fixture
def geldige_invoer():
    """Minimale geldige invoer voor kolominhoudstests."""
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
    """NaN (float) in een numerieke kolom wordt geweigerd."""
    geldige_invoer.loc[0, "waarde_laag"] = float("nan")
    with pytest.raises(ValueError, match="lege waarden"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("kolom", ["naam", "ihr", "ibr", "car"])
def test_kolominhoud_none_in_tekstkolom_wordt_geweigerd(geldige_invoer, kolom):
    """None in een tekstkolom wordt als lege waarde herkend en geweigerd."""
    geldige_invoer.loc[0, kolom] = None
    with pytest.raises(ValueError, match="lege waarden"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_lege_string_naam_wordt_geweigerd(geldige_invoer):
    """Een lege string in kolom 'naam' wordt geweigerd."""
    geldige_invoer.loc[0, "naam"] = ""
    with pytest.raises(ValueError, match="lege strings"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_whitespace_naam_wordt_geweigerd(geldige_invoer):
    """Een naam die alleen spaties bevat wordt als leeg beschouwd en geweigerd."""
    geldige_invoer.loc[0, "naam"] = "   "
    with pytest.raises(ValueError, match="lege strings"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_niet_numeriek_wordt_geweigerd(geldige_invoer):
    """Een niet-numerieke waarde in een numerieke kolom wordt geweigerd."""
    geldige_invoer["waarde_laag"] = geldige_invoer["waarde_laag"].astype(str)
    with pytest.raises(ValueError, match="numerieke waarden"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_negatieve_waarde_laag_wordt_geweigerd(geldige_invoer):
    """Negatieve waarde_laag wordt geweigerd."""
    geldige_invoer.loc[0, "waarde_laag"] = -1.0
    with pytest.raises(ValueError, match="waarde_laag"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("waarde", [-0.01, 1.0, 1.5])
def test_kolominhoud_verwachte_foutfractie_buiten_bereik(geldige_invoer, waarde):
    """verwachte_foutfractie buiten [0, 1) wordt geweigerd."""
    geldige_invoer.loc[0, "verwachte_foutfractie"] = waarde
    with pytest.raises(ValueError, match="verwachte_foutfractie"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("waarde", [0.0, -1.0])
def test_kolominhoud_kosten_niet_positief_wordt_geweigerd(geldige_invoer, waarde):
    """Kosten <= 0 wordt geweigerd."""
    geldige_invoer.loc[0, "kosten"] = waarde
    with pytest.raises(ValueError, match="kosten"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_negatieve_waarde_hoog_wordt_geweigerd(geldige_invoer):
    """Negatieve waarde_hoog wordt geweigerd."""
    geldige_invoer.loc[0, "waarde_hoog"] = -100.0
    with pytest.raises(ValueError, match="waarde_hoog"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_negatieve_fout_hoog_wordt_geweigerd(geldige_invoer):
    """Negatieve fout_hoog wordt geweigerd."""
    geldige_invoer.loc[0, "fout_hoog"] = -1.0
    with pytest.raises(ValueError, match="fout_hoog"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_fout_hoog_groter_dan_waarde_hoog_wordt_geweigerd(geldige_invoer):
    """fout_hoog groter dan waarde_hoog wordt geweigerd."""
    geldige_invoer.loc[0, "waarde_hoog"] = 1000.0
    geldige_invoer.loc[0, "fout_hoog"] = 2000.0
    with pytest.raises(ValueError, match="fout_hoog"):
        plan_stratified(geldige_invoer, materialiteit=0.05)


@pytest.mark.parametrize("waarde", [0.0, 1.0, -0.01, 1.5])
def test_kolominhoud_materialiteit_kolom_buiten_bereik(geldige_invoer, waarde):
    """Materialiteit-kolom buiten (0, 1) wordt geweigerd."""
    geldige_invoer.loc[0, "materialiteit"] = waarde
    with pytest.raises(ValueError, match="materialiteit"):
        plan_stratified(geldige_invoer, materialiteit=0.5)


@pytest.mark.parametrize("kolom", ["ihr", "ibr", "car"])
def test_kolominhoud_ongeldig_risico_wordt_geweigerd(geldige_invoer, kolom):
    """Een ongeldige risicowaarde in ihr, ibr of car wordt geweigerd."""
    geldige_invoer.loc[0, kolom] = "X"
    with pytest.raises(ValueError, match=kolom):
        plan_stratified(geldige_invoer, materialiteit=0.05)


def test_kolominhoud_ihr_ontbreekt_in_vereiste_kolommen():
    """ihr moet als vereiste kolom worden herkend (voorheen ontbrekend in vereiste_kolommen)."""
    zonder_ihr = pd.DataFrame({
        "naam": ["Stratum_A"],
        "waarde_laag": [100000.0],
        "verwachte_foutfractie": [0.01],
        "ibr": ["H"],
        "car": ["H"],
        "materialiteit": [0.05],
        "fout_hoog": [0.0],
        "waarde_hoog": [0.0],
        "kosten": [1.0],
    })
    with pytest.raises(AssertionError, match="ihr"):
        plan_stratified(zonder_ihr, materialiteit=0.05)


def test_kosten_invloed_op_allocatie():
    """Verifieer of het algoritme prioriteit geeft aan een goedkoop stratum."""
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

    # Omdat het ene stratum zoveel goedkoper is, zou het veel vaker gekozen moeten zijn.
    assert n_goedkoop > n_duur, (
        "Het planningsalgoritme hield onvoldoende rekening met de stuurkracht van uitvoeringskosten!"
    )
