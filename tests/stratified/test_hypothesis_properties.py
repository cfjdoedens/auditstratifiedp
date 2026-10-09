import hypothesis.strategies as st
import pandas as pd
import pytest
from hypothesis import given, settings

from auditstat.stratified import eval_stratified


@st.composite
def stratified_data_strategy(draw):
    """
    Genereer realistische, willekeurige audit-data met risicovariatie en hoogstrata.
    """
    # Bepaal het willekeurige aantal strata voor deze iteratie.
    m = draw(st.integers(min_value=1, max_value=4))

    # Stel de basiselementen van de strata samen.
    namen = [f"Stratum {i + 1}" for i in range(m)]
    waarden = draw(
        st.lists(
            st.floats(min_value=200_000.0, max_value=2_000_000.0),
            min_size=m,
            max_size=m,
        )
    )
    n_steken = draw(
        st.lists(
            st.integers(min_value=50, max_value=300),
            min_size=m,
            max_size=m,
        )
    )
    # Beperk het aantal fouten logisch binnen de steekproefomvang.
    k_fouten = [draw(st.integers(min_value=0, max_value=min(n, 10))) for n in n_steken]

    # Genereer willekeurige risicoprofielen per stratum.
    risico_opties = ["H", "M", "L"]
    ihr = draw(st.lists(st.sampled_from(risico_opties), min_size=m, max_size=m))
    ibr = draw(st.lists(st.sampled_from(risico_opties), min_size=m, max_size=m))
    car = draw(st.lists(st.sampled_from(risico_opties), min_size=m, max_size=m))

    # Voeg gecontroleerde hoogstrata toe voor deterministische verschuivingstests.
    waarde_hoog = draw(
        st.lists(
            st.floats(min_value=0.0, max_value=50_000.0),
            min_size=m,
            max_size=m,
        )
    )
    fout_hoog = [
        draw(st.floats(min_value=0.0, max_value=min(wh, 2_000.0))) for wh in waarde_hoog
    ]

    # Construeer het uiteindelijke DataFrame voor de evaluatie.
    df = pd.DataFrame({
        "naam": namen,
        "waarde_laag": waarden,
        "n_laag": n_steken,
        "k_laag": k_fouten,
        "ihr": ihr,
        "ibr": ibr,
        "car": car,
        "waarde_hoog": waarde_hoog,
        "fout_hoog": fout_hoog,
        "materialiteit": [0.05] * m,
    })
    return df


class TestPropertyBasedConvolutie:
    """
    Groep property-based tests met Hypothesis voor universele wiskundige invarianten.
    """

    @given(df=stratified_data_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_permutation_invariance(self, df):
        """
        Test of de permutatie-invariantie standhoudt bij willekeurige risico's en hoogstrata.
        """
        # Stel de vastgestelde parameters in voor de convolutie.
        zekerheid = 0.95
        granulariteit = 50_000

        # Bereken de baseline met de oorspronkelijke volgorde.
        res_orig = eval_stratified(
            steekproeven=df,
            model="poisson",
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=granulariteit,
            vergelijk=False,
        )

        # Hussel de rijen willekeurig door elkaar.
        df_shuffled = df.sample(frac=1.0).reset_index(drop=True)

        # Bereken het resultaat van de gehusselde dataset.
        res_shuffled = eval_stratified(
            steekproeven=df_shuffled,
            model="poisson",
            zekerheid=zekerheid,
            methode="FFT samen",
            granulariteit=granulariteit,
            vergelijk=False,
        )

        # Verifieer of de uitkomst identiek blijft.
        assert res_shuffled["max_fout_convolutie"] == pytest.approx(
            res_orig["max_fout_convolutie"], rel=1e-3
        ), (
            f"Permutatie-invariantie geschonden bij shuffling. "
            f"Origineel: {res_orig['max_fout_convolutie']:.6f}, "
            f"Gehusseld: {res_shuffled['max_fout_convolutie']:.6f}"
        )

    @given(df=stratified_data_strategy())
    @settings(max_examples=30, deadline=None)
    def test_property_confidence_monotonicity(self, df):
        """
        Test of de monotoniciteit van de zekerheid behouden blijft bij complexe invoer.
        """
        # Configureer de granulariteit voor de zekerheidstest.
        granulariteit = 50_000

        # Evalueer het model op een zekerheid van 95 procent.
        res_95 = eval_stratified(
            steekproeven=df,
            model="poisson",
            zekerheid=0.95,
            methode="FFT samen",
            granulariteit=granulariteit,
            vergelijk=False,
        )

        # Evalueer het model op een zekerheid van 99 procent.
        res_99 = eval_stratified(
            steekproeven=df,
            model="poisson",
            zekerheid=0.99,
            methode="FFT samen",
            granulariteit=granulariteit,
            vergelijk=False,
        )

        # Controleer of een hogere zekerheid leidt tot een grotere of gelijke maximale fout.
        assert res_99["max_fout_convolutie"] >= res_95["max_fout_convolutie"], (
            f"Monotoniciteit geschonden: 99% zekerheid ({res_99['max_fout_convolutie']:.6f}) "
            f"is lager dan 95% zekerheid ({res_95['max_fout_convolutie']:.6f})"
        )
