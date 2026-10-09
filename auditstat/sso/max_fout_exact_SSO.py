import numpy as np
from scipy.interpolate import interp1d
from scipy import stats


def _continue_kwantiel(cdf_func, max_val, target_p):
    """Interpolatie helper om discrete verdelingen continu te maken."""
    x_vals = np.arange(0, int(max_val) + 3)
    y_vals = cdf_func(x_vals)

    # Verwijder duplicaten om interpolatie fouten te voorkomen (bij staarten)
    unique_y, indices = np.unique(y_vals, return_index=True)
    unique_x = x_vals[indices]

    if target_p <= unique_y[0]:
        return float(unique_x[0])

    interp_func = interp1d(
        unique_y, unique_x, kind="linear", bounds_error=False, fill_value=(0, max_val)
    )
    return float(interp_func(target_p))


def max_fout_exact_SSO(n, k, N_klant, zekerheid=0.95, verdeling="binomiaal"):
    """
    Berekent de exacte maximale foutfractie voor een SSO-klant,
    met continue doortrekking van de discrete voorspellende verdelingen.
    """
    if verdeling == "binomiaal":
        # Voorspellende verdeling: Beta-Binomiaal (N_klant, alpha=k+1, beta=n-k+1)
        def cdf_func(x):
            return stats.betabinom.cdf(x, N_klant, k + 1, n - k + 1)

        aantal_fouten = _continue_kwantiel(cdf_func, N_klant, zekerheid)
        return aantal_fouten / N_klant

    elif verdeling == "poisson":
        # Voorspellende verdeling: Negatief-Binomiaal (r=k+1, p=n/(n+N_klant))
        # scipy.stats.nbinom hanteert het aantal mislukkingen, we passen parameters hierop aan.
        p_succes = n / (n + N_klant)
        cdf_func = lambda x: stats.nbinom.cdf(x, k + 1, p_succes)
        aantal_fouten = _continue_kwantiel(cdf_func, N_klant, zekerheid)
        return aantal_fouten / N_klant
    else:
        raise ValueError("Kies 'binomiaal' of 'poisson'")
