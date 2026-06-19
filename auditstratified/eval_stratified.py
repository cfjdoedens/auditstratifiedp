import numpy as np
import pandas as pd
from scipy.stats import beta, gamma, gaussian_kde
from scipy.fft import fft, ifft, next_fast_len

# Zorg ervoor dat de helper-functie (uit je nog te bouwen utils.py) beschikbaar is.
from auditstratified.utils import foutloze_posten_equivalent

def eval_stratified(steekproeven: pd.DataFrame, model: str = "binomiaal", 
                    zekerheid: float = 0.95, methode: str = "FFT samen", 
                    granulariteit: int = None, start: int = 1, vergelijk: bool = True) -> dict:
    """
    Evalueer samen de resultaten van 1 of meer steekproeven op uitgaand geld.
    
    Het samennemen van de resultaten gebeurt door convolutie van
    de foutkanskrommes van de afzonderlijke steekproeven tot 1 foutkanskromme.
    """
    # Bepaal en valideer de argumentkeuzes.
    if model not in ["binomiaal", "poisson"]:
        raise ValueError("Model moet 'binomiaal' of 'poisson' zijn.")
    if methode not in ["FFT paarsgewijs", "FFT samen", "direct", "Monte Carlo"]:
        raise ValueError("Ongeldige methode.")

    # Bepaal dynamische verstekwaarde voor granulariteit.
    if granulariteit is None:
        granulariteit = int(1e7) if methode == "Monte Carlo" else int(1e5)

    # Controleer de invoer op datatype en lege waarden.
    if not isinstance(steekproeven, pd.DataFrame):
        raise TypeError("Steekproeven moet een pandas DataFrame zijn.")
    if len(steekproeven) == 0:
        raise ValueError("Steekproeven is leeg.")

    # Strikte controle op alle vereiste kolommen.
    vereiste_kolommen = [
        "naam", "waarde_laag", "n_laag", "k_laag",
        "ihr", "ibr", "car", "materialiteit",
        "waarde_hoog", "fout_hoog"
    ]
    ontbrekend = set(vereiste_kolommen) - set(steekproeven.columns)
    if ontbrekend:
        raise ValueError(f"Ontbrekende kolommen: {', '.join(ontbrekend)}")

    # Controle op dubbele stratumnamen.
    if steekproeven['naam'].duplicated().any():
        dubbele = steekproeven[steekproeven['naam'].duplicated()]['naam'].unique()
        raise ValueError(f"Evaluatiefout: De volgende stratumnamen komen vaker dan één keer voor: {', '.join(dubbele)}")

    # Bepaal totaal geldswaarde, inclusief het 100%-getoetste deel.
    totaalgeld_laag = steekproeven['waarde_laag'].sum()
    totaalgeld_fout_hoog = steekproeven['fout_hoog'].sum()
    totaalgeld_goed_hoog = (steekproeven['waarde_hoog'] - steekproeven['fout_hoog']).sum()
    totaalgeld_algeheel = totaalgeld_laag + totaalgeld_fout_hoog + totaalgeld_goed_hoog

    # Creëer uitvoer DataFrame met regels per steekproef en vul afgeleide kolommen.
    t_uit = steekproeven.copy()
    t_uit['goed_hoog'] = t_uit['waarde_hoog'] - t_uit['fout_hoog']
    t_uit['waarde_populatie'] = t_uit['waarde_laag'] + t_uit['waarde_hoog']
    
    # Bepaal de foutloze posten equivalent (Noot: vereist de helper-functie).
    t_uit['extra_foutloze_posten'] = t_uit.apply(lambda row: foutloze_posten_equivalent(row['ihr'], row['ibr'], row['car'], row['materialiteit']), axis=1)
      
    t_uit['toch_fouten'] = ~((t_uit['ihr'] == "H") & (t_uit['ibr'] == "H") & (t_uit['car'] == "H")) & (t_uit['k_laag'] > 0)

    # Convolutie: FFT, FFT samen, direct, of MonteCarlo.
    if methode == "FFT paarsgewijs":
        conv = convolutie_fft(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel)
    elif methode == "FFT samen":
        conv = convolutie_fft_gelijktijdig(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel)
    elif methode == "direct":
        conv = convolutie_direct(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel)
    else:
        conv = convolutie_montecarlo(t_uit, model, zekerheid, granulariteit, start, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel)

    # Ter vergelijking: los en als1.
    vergelijk_met = {}
    if vergelijk:
        verg = vergelijk_los_en_als1(t_uit, model, zekerheid, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel)
        t_uit = verg['t_uit']
        vergelijk_met = {
            'mw_fout_los': verg['mw_fout_los'],
            'mw_fout_los_geld': verg['mw_fout_los'] * totaalgeld_algeheel,
            'min_fout_los': verg['min_fout_los'],
            'min_fout_los_geld': verg['min_fout_los'] * totaalgeld_algeheel,
            'max_fout_los': verg['max_fout_los'],
            'max_fout_los_geld': verg['max_fout_los'] * totaalgeld_algeheel,
            'mw_fout_als1': verg['mw_fout_als1'],
            'mw_fout_als1_geld': verg['mw_fout_als1'] * totaalgeld_algeheel,
            'min_fout_als1': verg['min_fout_als1'],
            'min_fout_als1_geld': verg['min_fout_als1'] * totaalgeld_algeheel,
            'max_fout_als1': verg['max_fout_als1'],
            'max_fout_als1_geld': verg['max_fout_als1'] * totaalgeld_algeheel
        }

    # Resultaat opstellen en retourneren als dictionary.
    return {
        'kanskromme': conv['d'],
        'populatie_totaal': totaalgeld_algeheel,
        'modus_fout_convolutie': conv['modus_fout'],
        'modus_fout_convolutie_geld': conv['modus_fout'] * totaalgeld_algeheel,
        'mediaan_fout_convolutie': conv['mediaan_fout'],
        'mediaan_fout_convolutie_geld': conv['mediaan_fout'] * totaalgeld_algeheel,
        'gemiddelde_fout_convolutie': conv['gemiddelde_fout'],
        'gemiddelde_fout_convolutie_geld': conv['gemiddelde_fout'] * totaalgeld_algeheel,
        'mw_fout_convolutie': conv['modus_fout'],
        'mw_fout_convolutie_geld': conv['modus_fout'] * totaalgeld_algeheel,
        'min_fout_convolutie': conv['min_fout'],
        'min_fout_convolutie_geld': conv['min_fout'] * totaalgeld_algeheel,
        'max_fout_convolutie': conv['max_fout'],
        'max_fout_convolutie_geld': conv['max_fout'] * totaalgeld_algeheel,
        'vergelijk_met': vergelijk_met,
        'steekproeven': t_uit,
        'invoer': {
            'model': model,
            'zekerheid': zekerheid,
            'methode': methode,
            'granulariteit': granulariteit,
            'start': start,
            'vergelijk': vergelijk
        }
    }


def convolutie_montecarlo(t_uit, model, zekerheid, granulariteit, start, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel):
    """Convolutie via Monte Carlo simulatie."""
    # Zorg voor reproduceerbaarheid via de seed.
    if start != 0:
        np.random.seed(start)

    # Simuleer foutfracties per stratum via kansverdelingen.
    n_steekproeven = len(t_uit)
    krommen = np.zeros((int(granulariteit), n_steekproeven))
    
    for i in range(n_steekproeven):
        n_calc = t_uit['n_laag'].iloc[i] + t_uit['extra_foutloze_posten'].iloc[i]
        k_calc = t_uit['k_laag'].iloc[i]

        if model == "binomiaal":
            krommen[:, i] = beta.rvs(a=k_calc + 1, b=n_calc - k_calc + 1, size=int(granulariteit))
        else:
            krommen[:, i] = gamma.rvs(a=k_calc + 1, scale=1.0/n_calc, size=int(granulariteit))

    # Convolutie via matrixvermenigvuldiging (dot product) van fracties en geldwaarden.
    convolutie = (np.dot(krommen, t_uit['waarde_laag'].values) + totaalgeld_fout_hoog) / totaalgeld_algeheel

    # Kernel density estimation over de simulatie-uitkomst.
    bovengrens = 1.0 if model == "binomiaal" else (np.max(convolutie) + 0.1)
    kde = gaussian_kde(convolutie)
    kde.set_bandwidth(bw_method=kde.factor * 1.5)

    x_grid = np.linspace(0, bovengrens, 512)
    y_vals = kde.evaluate(x_grid)

    # Normaliseer de kernel density.
    dx = x_grid[1] - x_grid[0]
    oppervlakte = np.sum(y_vals) * dx
    y_vals = y_vals / oppervlakte

    return {
        'd': {'x': x_grid, 'y': y_vals},
        'min_fout': np.percentile(convolutie, (1 - zekerheid) * 100),
        'max_fout': np.percentile(convolutie, zekerheid * 100),
        'mediaan_fout': np.percentile(convolutie, 50),
        'modus_fout': x_grid[np.argmax(y_vals)],
        'gemiddelde_fout': np.mean(convolutie)
    }


def convolutie_fft_gelijktijdig(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel):
    """
    Convolutie via gelijktijdige Fast Fourier Transform.
    Transformeert alle strata tegelijk naar het frequentiedomein.
    """
    # Edge case: geen statistische controle, alles integraal.
    if totaalgeld_laag < 0.01:
        frac = totaalgeld_fout_hoog / totaalgeld_algeheel
        return {
            'd': {'x': np.array([frac]), 'y': np.array([1.0])},
            'min_fout': frac, 'max_fout': frac, 'mediaan_fout': frac,
            'modus_fout': frac, 'gemiddelde_fout': frac
        }

    # Bouw kansmassavectoren per stratum.
    dx = totaalgeld_laag / granulariteit
    p_strata = []

    for i in range(len(t_uit)):
        w_laag = t_uit['waarde_laag'].iloc[i]
        n_calc = t_uit['n_laag'].iloc[i] + t_uit['extra_foutloze_posten'].iloc[i]
        k_calc = t_uit['k_laag'].iloc[i]

        if w_laag > 0:
            max_frac = 1.0 if model == "binomiaal" else gamma.ppf(0.9999, a=k_calc + 1, scale=1.0/n_calc)
            x_grens = max(w_laag, max_frac * w_laag)
            x_as = np.arange(0, x_grens + dx, dx)

            if model == "binomiaal":
                p = beta.pdf(x_as / w_laag, k_calc + 1, n_calc - k_calc + 1)
            else:
                p = gamma.pdf(x_as / w_laag, a=k_calc + 1, scale=1.0/n_calc)

            p = np.nan_to_num(p, posinf=0.0, neginf=0.0)
            p = p / np.sum(p)
            p_strata.append(p)

    # Gelijktijdige convolutie via zero-padding en fft.
    if len(p_strata) == 1:
        p_totaal = p_strata[0]
    else:
        totale_lengte = sum(len(p) for p in p_strata) - len(p_strata) + 1
        pad_lengte = next_fast_len(totale_lengte)

        fft_product = np.ones(pad_lengte, dtype=complex)
        for p in p_strata:
            p_padded = np.pad(p, (0, pad_lengte - len(p)))
            fft_product *= fft(p_padded)

        p_totaal = np.real(ifft(fft_product))
        p_totaal = p_totaal[:totale_lengte]

        p_totaal[(p_totaal < 0) & (np.abs(p_totaal) < 1e-12)] = 0
        p_totaal = p_totaal / np.sum(p_totaal)

    # Bereken de totale assen en parameters.
    x_totaal_laag = np.arange(len(p_totaal)) * dx
    x_totaal_geld = x_totaal_laag + totaalgeld_fout_hoog
    x_totaal_fractie = x_totaal_geld / totaalgeld_algeheel

    dx_fractie = dx / totaalgeld_algeheel
    d = {'x': x_totaal_fractie, 'y': p_totaal / dx_fractie}

    cum_p = np.cumsum(p_totaal)

    min_fout = interpolate_quantile(cum_p, x_totaal_fractie, 1 - zekerheid)
    max_fout = interpolate_quantile(cum_p, x_totaal_fractie, zekerheid)
    mediaan_fout = interpolate_quantile(cum_p, x_totaal_fractie, 0.5)

    return {
        'd': d,
        'min_fout': min_fout,
        'max_fout': max_fout,
        'mediaan_fout': mediaan_fout,
        'modus_fout': x_totaal_fractie[np.argmax(p_totaal)],
        'gemiddelde_fout': np.sum(x_totaal_fractie * p_totaal)
    }


def convolutie_fft(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel):
    """Convolutie via paarsgewijze Fast Fourier Transformatie."""
    # Noot: de rekenstappen voor de assen zijn identiek aan de gelijktijdige methode.
    # We vallen voor de schoonheid van code hier terug op Numpy's native convolve die dit regelt.
    
    if totaalgeld_laag < 0.01:
        frac = totaalgeld_fout_hoog / totaalgeld_algeheel
        return {
            'd': {'x': np.array([frac]), 'y': np.array([1.0])},
            'min_fout': frac, 'max_fout': frac, 'mediaan_fout': frac,
            'modus_fout': frac, 'gemiddelde_fout': frac
        }

    dx = totaalgeld_laag / granulariteit
    p_strata = []

    for i in range(len(t_uit)):
        w_laag = t_uit['waarde_laag'].iloc[i]
        n_calc = t_uit['n_laag'].iloc[i] + t_uit['extra_foutloze_posten'].iloc[i]
        k_calc = t_uit['k_laag'].iloc[i]

        if w_laag > 0:
            max_frac = 1.0 if model == "binomiaal" else gamma.ppf(0.9999, a=k_calc + 1, scale=1.0/n_calc)
            x_grens = max(w_laag, max_frac * w_laag)
            x_as = np.arange(0, x_grens + dx, dx)

            if model == "binomiaal":
                p = beta.pdf(x_as / w_laag, k_calc + 1, n_calc - k_calc + 1)
            else:
                p = gamma.pdf(x_as / w_laag, a=k_calc + 1, scale=1.0/n_calc)

            p = np.nan_to_num(p, posinf=0.0, neginf=0.0)
            p = p / np.sum(p)
            p_strata.append(p)

    # Paarsgewijze convolutie in een klassieke loop.
    if len(p_strata) > 0:
        p_totaal = p_strata[0]
        for p_next in p_strata[1:]:
            p_totaal = np.convolve(p_totaal, p_next, mode='full')
            p_totaal[(p_totaal < 0) & (np.abs(p_totaal) < 1e-12)] = 0
            p_totaal = p_totaal / np.sum(p_totaal)

    x_totaal_laag = np.arange(len(p_totaal)) * dx
    x_totaal_geld = x_totaal_laag + totaalgeld_fout_hoog
    x_totaal_fractie = x_totaal_geld / totaalgeld_algeheel

    dx_fractie = dx / totaalgeld_algeheel
    d = {'x': x_totaal_fractie, 'y': p_totaal / dx_fractie}

    cum_p = np.cumsum(p_totaal)

    min_fout = interpolate_quantile(cum_p, x_totaal_fractie, 1 - zekerheid)
    max_fout = interpolate_quantile(cum_p, x_totaal_fractie, zekerheid)
    mediaan_fout = interpolate_quantile(cum_p, x_totaal_fractie, 0.5)

    return {
        'd': d,
        'min_fout': min_fout,
        'max_fout': max_fout,
        'mediaan_fout': mediaan_fout,
        'modus_fout': x_totaal_fractie[np.argmax(p_totaal)],
        'gemiddelde_fout': np.sum(x_totaal_fractie * p_totaal)
    }


def convolutie_direct(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel):
    """
    Convolutie via directe, lineaire vectorberekening.
    Omdat numpy.convolve op de achtergrond al kiest voor de optimale lineaire 
    vectorberekening, hergebruiken we in Python exact dezelfde code als de 
    paarsgewijze convolutie.
    """
    return convolutie_fft(t_uit, model, zekerheid, granulariteit, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel)


def vergelijk_los_en_als1(t_uit, model, zekerheid, totaalgeld_laag, totaalgeld_fout_hoog, totaalgeld_algeheel):
    """Vergelijkingsmethoden: los (per stratum) en als1 (alles samengevoegd)."""
    t_uit_werk = t_uit.copy()
    n_steekproeven = len(t_uit_werk)

    # Los: per stratum apart extrapoleren, dan gewogen optellen.
    mw_fout_lijst, min_fout_lijst, max_fout_lijst = [], [], []

    for i in range(n_steekproeven):
        n_calc = t_uit_werk['n_laag'].iloc[i] + t_uit_werk['extra_foutloze_posten'].iloc[i]
        k_calc = t_uit_werk['k_laag'].iloc[i]

        mw_fout_lijst.append(k_calc / n_calc if n_calc > 0 else 0)
        
        if model == "binomiaal":
            min_fout_lijst.append(beta.ppf(1 - zekerheid, k_calc + 1, n_calc - k_calc + 1))
            max_fout_lijst.append(beta.ppf(zekerheid, k_calc + 1, n_calc - k_calc + 1))
        else:
            min_fout_lijst.append(gamma.ppf(1 - zekerheid, a=k_calc + 1, scale=1.0/n_calc))
            max_fout_lijst.append(gamma.ppf(zekerheid, a=k_calc + 1, scale=1.0/n_calc))

    t_uit_werk['mw_fout'] = mw_fout_lijst
    t_uit_werk['min_fout'] = min_fout_lijst
    t_uit_werk['max_fout'] = max_fout_lijst

    mw_fout_los = (np.sum(t_uit_werk['mw_fout'] * t_uit_werk['waarde_laag']) + totaalgeld_fout_hoog) / totaalgeld_algeheel
    min_fout_los = (np.sum(t_uit_werk['min_fout'] * t_uit_werk['waarde_laag']) + totaalgeld_fout_hoog) / totaalgeld_algeheel
    max_fout_los = (np.sum(t_uit_werk['max_fout'] * t_uit_werk['waarde_laag']) + totaalgeld_fout_hoog) / totaalgeld_algeheel

    # Als1: alle strata samenvoegen alsof het 1 steekproef is.
    n_calc_als1 = t_uit_werk['n_laag'].sum() + t_uit_werk['extra_foutloze_posten'].sum()
    k_calc_als1 = t_uit_werk['k_laag'].sum()

    mw_fout_als1_laag = k_calc_als1 / n_calc_als1 if n_calc_als1 > 0 else 0
    if model == "binomiaal":
        min_fout_als1_laag = beta.ppf(1 - zekerheid, k_calc_als1 + 1, n_calc_als1 - k_calc_als1 + 1)
        max_fout_als1_laag = beta.ppf(zekerheid, k_calc_als1 + 1, n_calc_als1 - k_calc_als1 + 1)
    else:
        min_fout_als1_laag = gamma.ppf(1 - zekerheid, a=k_calc_als1 + 1, scale=1.0/n_calc_als1)
        max_fout_als1_laag = gamma.ppf(zekerheid, a=k_calc_als1 + 1, scale=1.0/n_calc_als1)

    return {
        't_uit': t_uit_werk,
        'mw_fout_los': mw_fout_los, 'min_fout_los': min_fout_los, 'max_fout_los': max_fout_los,
        'mw_fout_als1': ((mw_fout_als1_laag * totaalgeld_laag + totaalgeld_fout_hoog) / totaalgeld_algeheel),
        'min_fout_als1': ((min_fout_als1_laag * totaalgeld_laag + totaalgeld_fout_hoog) / totaalgeld_algeheel),
        'max_fout_als1': ((max_fout_als1_laag * totaalgeld_laag + totaalgeld_fout_hoog) / totaalgeld_algeheel)
    }


def interpolate_quantile(cum_p, x_vals, target):
    """Bereken de exacte fractiewaarde van een kwantiel via lineaire interpolatie."""
    idx_boven_array = np.where(cum_p >= target)[0]
    
    if len(idx_boven_array) == 0:
        return x_vals[-1]
    
    idx_boven = idx_boven_array[0]
    if idx_boven == 0:
        return x_vals[0]
    
    idx_onder = idx_boven - 1
    p_onder = cum_p[idx_onder]
    p_boven = cum_p[idx_boven]
    x_onder = x_vals[idx_onder]
    x_boven = x_vals[idx_boven]
    
    if p_boven == p_onder:
        return x_boven
        
    pct = (target - p_onder) / (p_boven - p_onder)
    return x_onder + pct * (x_boven - x_onder)
