from scipy import stats

from auditstat.sso.n_klant_k_klant_SSO import n_klant_k_klant_SSO


def max_fout_benaderd_SSO(n, k, N_klant, zekerheid=0.95, verdeling="binomiaal"):
    """
    Berekent de benaderde maximale foutfractie voor een SSO-klant.
    """
    n_klant, k_klant = n_klant_k_klant_SSO(n, k, N_klant)

    if verdeling == "binomiaal":
        # Vlakke prior (Beta(1,1)), posterior is Beta(k_klant+1, n_klant-k_klant+1)
        return stats.beta.ppf(zekerheid, k_klant + 1, n_klant - k_klant + 1)
    elif verdeling == "poisson":
        # Vlakke prior Gamma(1,0), posterior voor de fractie is Gamma(k_klant+1, schaal=1/n_klant)
        return stats.gamma.ppf(zekerheid, a=k_klant + 1, scale=1.0 / n_klant)
    else:
        raise ValueError("Kies 'binomiaal' of 'poisson'")
