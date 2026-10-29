import pandas as pd
import pytest

from auditstat.sso.evalueer_SSO_totaal import evalueer_SSO_totaal
from auditstat.stratified.eval_stratified import eval_stratified


def _post(naam="totaal", n=200, k=4, waarde=2_500_000.0):
    return dict(naam=naam, n=n, k=k, waarde_laag=waarde)


def test_een_stratum_gelijk_aan_eval_stratified_op_ruwe_steekproef():
    res = evalueer_SSO_totaal([_post()])
    direct = eval_stratified(
        pd.DataFrame(
            [dict(naam="totaal", waarde_laag=2_500_000.0, n_laag=200, k_laag=4)]
        )
    )
    assert res["max_fout_convolutie"] == pytest.approx(direct["max_fout_convolutie"])
    assert list(res["steekproeven"]["n_laag"]) == [200]
    assert list(res["steekproeven"]["k_laag"]) == [4]


def test_geldbedrag_is_fractie_maal_massa():
    res = evalueer_SSO_totaal([_post()])
    assert res["max_fout_convolutie_geld"] == pytest.approx(
        res["max_fout_convolutie"] * 2_500_000.0
    )


def test_meerdere_typen_posten_geven_een_stratum_per_type():
    res = evalueer_SSO_totaal(
        [
            _post("Emolumenten", 120, 1, 1_500_000.0),
            _post("Inkoopfacturen", 80, 3, 1_000_000.0),
        ]
    )
    assert list(res["steekproeven"]["naam"]) == ["Emolumenten", "Inkoopfacturen"]


def test_float_met_geheel_getal_wordt_geaccepteerd():
    res = evalueer_SSO_totaal([_post(n=200.0, k=4.0)])
    assert res["steekproeven"]["n_laag"].iloc[0] == 200


def test_niet_geheel_getal_wordt_geweigerd():
    with pytest.raises(ValueError, match="geen geheel getal"):
        evalueer_SSO_totaal([_post(n=200.5)])


def test_ontbrekend_veld_wordt_geweigerd():
    with pytest.raises(ValueError, match="mist verplicht"):
        evalueer_SSO_totaal([dict(naam="x", n=10, k=0)])


def test_lege_lijst_wordt_geweigerd():
    with pytest.raises(ValueError):
        evalueer_SSO_totaal([])


def test_poisson_model_werkt():
    res = evalueer_SSO_totaal([_post()], model="poisson")
    assert res["max_fout_convolutie"] > 0
