"""Samengestelde verdeling van de euro-fout bij een klant, met variabele postgroottes.

Niveau 2 en 3 van de SSO-theorie (``theorie.qmd``): de fout in euro's bij een
klant is ``E = Z_1 + ... + Z_K``, met ``K`` het aantal foute posten (Beta-
Binomiaal resp. Negatief-Binomiaal, net als bij de exacte methode op niveau 1)
en ``Z_i`` de waarde van een foute post:

* niveau 2: ``Z`` is Gamma-verdeeld met gemiddelde ``mu = waarde / N_klant`` en
  variatiecoëfficiënt ``cv`` (de Gamma-familie is een parametrische keuze;
  alleen gemiddelde en variantie komen uit de data);
* niveau 3: ``Z`` volgt de empirische verdeling van een lijst postwaarden,
  herschaald naar gemiddelde ``mu`` (alleen de vorm van de verdeling telt).

De verdeling van ``E`` volgt uit de kanskarakteristieke functie
``phi_E(w) = som_K P(K) * phi_Z(w)**K`` op een euro-rooster (FFT). De
trekkingen ``Z_i`` zijn onafhankelijk met teruglegging (een benadering van
trekken zonder teruglegging; de spreiding is daardoor iets te groot, dus
conservatief).

Conventie: de kansmassa van het continue deel (``K >= 1``) wordt één roostercel
omhoog geschoven (``E`` is dan nooit te laag in het rooster); ``K = 0`` staat
exact op cel 0. Kansmassa boven ``waarde`` komt in de laatste cel.
"""

import math

import numpy as np
from scipy.special import betaln, gammainc, gammaln
from scipy.stats import nbinom

_STAARTMASSA = 1e-12
# Grootste aantal waarden van K waarover wordt gesommeerd (elke waarde kost
# één vermenigvuldiging van een rooster-lange vector).
MAX_K_VENSTER = 1_000_000
_MAX_FFT_LENGTE = 2**22
# Aantal frequenties per blok in de K-lus (past in de L1/L2-cache).
_FREQUENTIEBLOK = 2048


def aantal_fouten_venster(model, n, k, N):
    """Venster ``(k_laag, pmf)`` rond de kansmassa van het aantal foute posten.

    ``pmf[i]`` is ``P(K = k_laag + i)``; het venster bevat de massa tussen
    ``1e-12`` en ``1 - 1e-12`` en is genormaliseerd op som 1.
    """
    a, b = k + 1, n - k + 1
    if model == "binomiaal":
        j = np.arange(0, N + 1)
        log_pmf = (
            gammaln(N + 1)
            - gammaln(j + 1)
            - gammaln(N - j + 1)
            + betaln(j + a, N - j + b)
            - betaln(a, b)
        )
        pmf = np.exp(log_pmf)
    else:
        q = n / (n + N)
        hoogste = int(nbinom.ppf(1 - _STAARTMASSA, k + 1, q)) + 1
        pmf = nbinom.pmf(np.arange(0, hoogste + 1), k + 1, q)
    # Normaliseren vóór de cumulatieve som: de log-gamma-berekening telt door
    # afrondingsfouten op tot ca. 1 - 1e-10, waardoor ``cum`` nooit 1 - 1e-12
    # haalde en het venster onterecht tot K = N doorliep. De bovenstaart
    # komt uit een omgekeerde som (nauwkeurig voor kleine massa's).
    pmf = pmf / pmf.sum()
    cum = np.cumsum(pmf)
    staart = np.cumsum(pmf[::-1])[::-1]  # staart[j] = P(K >= j)
    laag = int(np.searchsorted(cum, _STAARTMASSA))
    hoog = int(np.max(np.nonzero(staart > _STAARTMASSA)[0]))
    venster = pmf[laag : hoog + 1]
    return laag, venster / venster.sum()


def _karakteristieke_z(z, mu, dx, lengte):
    """``phi_Z`` op de rfft-frequenties van een rooster met ``lengte`` cellen.

    Geeft ``(phi, sigma_z)``; ``sigma_z`` is de standaardafwijking van ``Z``.
    """
    if isinstance(z, tuple) and z[0] == "gamma":
        cv = float(z[1])
        alfa = 1.0 / cv**2
        theta = mu * cv**2
        omega = 2 * np.pi * np.arange(lengte // 2 + 1) / (lengte * dx)
        return (1 + 1j * omega * theta) ** (-alfa), cv * mu
    waarden = np.asarray(z, dtype=float)
    waarden = waarden * (mu / waarden.mean())
    sigma = float(waarden.std())
    pos = np.minimum(waarden / dx, lengte - 2.0)
    i = np.floor(pos).astype(np.int64)
    t = pos - i
    g = np.bincount(i, weights=1 - t, minlength=lengte) + np.bincount(
        i + 1, weights=t, minlength=lengte
    )
    g = g[:lengte] / len(waarden)
    return np.fft.rfft(g), sigma


def _rooster(model, n, k, N, waarde, z, dx):
    """Roosterafmetingen van ``kansmassa_compound``, met de limietcontroles.

    Geeft ``(ncellen, mu, k0, pmf, lengte)``.
    """
    ncellen = math.ceil(waarde / dx) + 1
    mu = waarde / N
    k0, pmf = aantal_fouten_venster(model, n, k, N)
    if len(pmf) > MAX_K_VENSTER:
        spreiding = f"{len(pmf):,}".replace(",", ".")
        maximum = f"{MAX_K_VENSTER:,}".replace(",", ".")
        raise ValueError(
            f"Het aantal mogelijke foute posten (spreiding {spreiding}) is te "
            f"groot voor de exacte methode met postgroottes (maximaal {maximum}; "
            "dat hangt vooral af van N_klant gedeeld door de "
            "SSO-steekproefomvang n); gebruik een van de andere methoden of "
            "een kleinere N_klant."
        )
    k_max = k0 + len(pmf) - 1
    # Voor de lengte van het FFT-rooster: boven E_max mag geen kansmassa meer
    # zitten, anders klapt die om naar de lage cellen.
    sigma_schatting = mu * float(z[1]) if isinstance(z, tuple) else mu * 10.0
    e_max = k_max * mu + 8 * sigma_schatting * math.sqrt(max(k_max, 1))
    lengte = 1 << max(2 * ncellen - 1, math.ceil(1.1 * e_max / dx) + 2).bit_length()
    if lengte > _MAX_FFT_LENGTE:
        raise ValueError(
            "De foutfractie kan bij deze steekproef zo hoog uitvallen dat het "
            "euro-rooster te groot wordt voor de exacte methode met "
            "postgroottes; gebruik een van de andere methoden."
        )
    return ncellen, mu, k0, pmf, lengte


# Ruwe kalibratie van de rekentijd van de K-lus (seconden per
# vensterlengte x halve FFT-lengte). Gemeten na de Horner-/blokaanpak
# (N_klant 30.000 / 100.000 / 300.000, 20.000 cellen, binomiaal en poisson):
# 1,1e-9 s per eenheid, vrijwel constant; 1,5e-9 laat enige marge. Alleen een
# orde-van-grootte-indicatie, afhankelijk van de computer.
_SECONDEN_PER_EENHEID = 1.5e-9


def schat_rekentijd_compound(model, n, k, N, waarde, z, dx):
    """Indicatie van de rekentijd (seconden) van ``kansmassa_compound``.

    Gooit dezelfde ``ValueError`` als ``kansmassa_compound`` als de
    limieten worden overschreden.
    """
    _, _, k0, pmf, lengte = _rooster(model, n, k, N, waarde, z, dx)
    start = max(k0, 1)
    if isinstance(z, tuple):
        start = max(start, min(math.ceil(10 * float(z[1]) ** 2), 400) + 1)
    k_max = k0 + len(pmf) - 1
    aantal = max(k_max - start + 1, 0)
    return aantal * (lengte // 2 + 1) * _SECONDEN_PER_EENHEID


def kansmassa_compound(model, n, k, N, waarde, z, dx, voortgang=None):
    """Kansmassa per roostercel van de euro-fout ``E`` van één type post.

    Parameters
    ----------
    model : {"binomiaal", "poisson"}
    n, k : float
        SSO-steekproef (``n`` inclusief de HARo-foutloze posten).
    N : int
        Aantal posten van dit type bij de klant.
    waarde : float
        Totale geldwaarde van dit type post bij de klant.
    z : tuple of array
        ``("gamma", cv)`` voor niveau 2, of een rij postwaarden voor niveau 3.
    dx : float
        Celbreedte van het euro-rooster.
    voortgang : callable, optional
        ``voortgang(fractie)`` met een getal tussen 0 en 1, regelmatig
        aangeroepen tijdens de rekenlus.

    Returns
    -------
    numpy.ndarray
        Lengte ``ceil(waarde / dx) + 1``; cel ``i`` hoort bij ``E = i * dx``.
    """
    ncellen, mu, k0, pmf, lengte = _rooster(model, n, k, N, waarde, z, dx)
    k_max = k0 + len(pmf) - 1
    phi, _ = _karakteristieke_z(z, mu, dx, lengte)

    # K = 0 staat exact op cel 0. Bij een Gamma-verdeelde Z met grote cv is de
    # dichtheid voor kleine K (aantal foute posten < cv^2) singulier in 0 en
    # zou puntbemonstering in het frequentiedomein haar slecht weergeven: die
    # K worden daarom exact uit de Gamma-cdf per cel gehaald (afgerond naar
    # boven op de celgrens). Voor grotere K gaat de som via de FFT.
    p0 = pmf[0] if k0 == 0 else 0.0
    uit = np.zeros(ncellen)
    uit[0] += p0
    start = max(k0, 1)
    if isinstance(z, tuple):
        alfa = 1.0 / float(z[1]) ** 2
        theta = mu * float(z[1]) ** 2
        grens_k = min(math.ceil(10 * float(z[1]) ** 2), 400)
        randen = np.arange(0, ncellen) * dx / theta
        for kk in range(start, min(grens_k, k_max) + 1):
            cdf = gammainc(kk * alfa, randen)
            massa_k = np.diff(np.concatenate([[0.0], cdf]))
            massa_k[-1] += 1.0 - cdf[-1]
            uit += pmf[kk - k0] * massa_k
        start = max(start, grens_k + 1)
    if start <= k_max:
        # Som_K pmf[K] * phi**K in de Horner-vorm (hoogste K eerst): één
        # vermenigvuldiging en één optelling per K. De frequenties worden in
        # blokken verwerkt die in de cache passen; dat is ca. 5 keer sneller
        # dan telkens de hele vector doorlopen (de lus is geheugengebonden).
        acc = np.empty(len(phi), dtype=complex)
        gewichten = pmf[start - k0 :]
        blokken = range(0, len(phi), _FREQUENTIEBLOK)
        for nr, begin in enumerate(blokken):
            if voortgang is not None:
                voortgang(nr / len(blokken))
            phi_b = phi[begin : begin + _FREQUENTIEBLOK]
            h = np.full(len(phi_b), gewichten[-1], dtype=complex)
            for w in gewichten[-2::-1]:
                h *= phi_b
                h += w
            acc[begin : begin + len(phi_b)] = h * phi_b**start
        massa = np.clip(np.fft.irfft(acc, lengte), 0.0, None)
        # Nearest-cel naar boven: schuif een cel op.
        uit[1:ncellen] += massa[: ncellen - 1]
        uit[ncellen - 1] += massa[ncellen - 1 :].sum()
    return uit / uit.sum()
