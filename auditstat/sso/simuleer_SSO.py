import numpy as np


def simuleer_SSO(
    n, k, N_klant, zekerheid=0.95, verdeling="binomiaal", iteraties=500000
):
    """
    Controleert max_fout_SSO via Monte Carlo simulatie.
    """
    if verdeling == "binomiaal":
        # Trek p uit de posterior: Beta(k+1, n-k+1)
        p_sim = np.random.beta(k + 1, n - k + 1, iteraties)
        # Genereer fouten bij de klant gegeven de getrokken p's
        k_klant_sim = np.random.binomial(N_klant, p_sim)

    elif verdeling == "poisson":
        # Trek p uit de posterior Gamma (scale = 1/n)
        p_sim = np.random.gamma(k + 1, 1.0 / n, iteraties)
        k_klant_sim = np.random.poisson(N_klant * p_sim)

    else:
        raise ValueError("Kies 'binomiaal' of 'poisson'")

    # Zoek het empirische kwantiel van de foutfractie bij de klant
    fracties = k_klant_sim / N_klant
    gesimuleerde_grens = np.percentile(fracties, zekerheid * 100)

    return gesimuleerde_grens
