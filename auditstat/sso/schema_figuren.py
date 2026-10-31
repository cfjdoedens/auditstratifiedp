"""Schematische figuren voor de Theorie-tab en het Quarto-document.

De figuren worden getekend met matplotlib en zijn zowel door de Streamlit-app
(``theorie.qmd`` wordt daar ingelezen) als door Quarto zelf (``quarto render
theorie.qmd``) te gebruiken. ``THEORIE_FIGUREN`` koppelt het label van een
figuur in ``theorie.qmd`` aan de tekenfunctie.
"""

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Patch


def teken_sso_schema(met_centen: bool):
    """Schematische weergave van de SSO-steekproef en de klanten.

    Binnen de grote cirkel (de totale SSO-massa) liggen posten van ongeveer
    gelijke grootte (grijze ovaaltjes). Klanten (rechts) en de SSO-steekproef
    (links) staan buiten de massa; pijlen wijzen naar de posten waarop
    gestoken wordt. Eén steekproefpost valt bewust samen met een post van een
    klant (zwart omcirkeld). De indeling (posten, klantposten,
    steekproefposten) is voor beide varianten gelijk, zodat het tweede plaatje
    het eerste uitwerkt.

    Zonder ``met_centen``: de steekproefposten zijn rood gekleurd en de
    pijlen wijzen naar hele posten. Met ``met_centen``: elke post bestaat uit
    eurocenten (stippen); de SSO-steekproef is een geldsteekproef en steekt
    op één eurocent per post, de klanten steken op hele posten.
    """
    rng = np.random.default_rng(7305)
    fig, ax = plt.subplots(figsize=(9.0, 6.4))
    straal = 3.9
    post_w, post_h = 0.78, 0.56

    # Posten op een hexagonaal rooster binnen de cirkel (ongeveer even groot).
    posten = []
    rij = 0
    y = -straal
    while y <= straal:
        x0 = -straal + (0.45 if rij % 2 else 0.0)
        x = x0
        while x <= straal:
            if math.hypot(x, y) + 0.42 <= straal:
                posten.append((x, y))
            x += 0.9
        y += 0.78
        rij += 1

    def _punt_in_post(px, py, schaal=0.72):
        while True:
            dx = rng.uniform(-1, 1)
            dy = rng.uniform(-1, 1)
            if dx * dx + dy * dy <= 1:
                return (px + dx * post_w / 2 * schaal, py + dy * post_h / 2 * schaal)

    # Eurocenten per post (kleine grijze stippen).
    centen = [[_punt_in_post(px, py) for _ in range(8)] for px, py in posten]

    klant_kleuren = {"Klant A": "#e8a33d", "Klant B": "#4caf7d", "Klant C": "#c768a8"}
    klant_aantallen = {"Klant A": 3, "Klant B": 3, "Klant C": 2}
    kleur_s = "#c0392b"

    volgorde = list(range(len(posten)))
    rng.shuffle(volgorde)
    cursor = 0
    klant_posten = {}
    for naam, n in klant_aantallen.items():
        klant_posten[naam] = volgorde[cursor : cursor + n]
        cursor += n
    alle_klant_idx = [i for idxs in klant_posten.values() for i in idxs]
    kleur_van_post = {
        i: klant_kleuren[naam] for naam, idxs in klant_posten.items() for i in idxs
    }

    gedeeld_idx = int(rng.choice(alle_klant_idx))
    overige = [i for i in volgorde[cursor:] if i != gedeeld_idx]
    nieuwe_idx = [int(i) for i in rng.choice(overige, size=4, replace=False)]
    steekproef_posten = [*nieuwe_idx, gedeeld_idx]
    # Per steekproefpost: de ene eurocent waarop gestoken wordt.
    gestoken_cent = {i: int(rng.integers(0, 8)) for i in steekproef_posten}

    # Posten tekenen.
    for i, (px, py) in enumerate(posten):
        kleur = kleur_van_post.get(i)
        if kleur is None and not met_centen and i in steekproef_posten:
            kleur = kleur_s
        ax.add_patch(
            Ellipse(
                (px, py),
                width=post_w,
                height=post_h,
                facecolor=kleur if kleur else "#e6e6e6",
                alpha=0.75 if kleur else 0.6,
                edgecolor="#9a9a9a",
                linewidth=0.5,
                zorder=2,
            )
        )
        if met_centen:
            for j, (cx_, cy_) in enumerate(centen[i]):
                if gestoken_cent.get(i) == j:
                    continue
                ax.plot(cx_, cy_, "o", color="#6e6e6e", markersize=1.6, zorder=3)

    # Gestoken eurocenten van de SSO-steekproef.
    if met_centen:
        for i in steekproef_posten:
            cx_, cy_ = centen[i][gestoken_cent[i]]
            ax.plot(cx_, cy_, "o", color=kleur_s, markersize=4.2, zorder=6)

    gx, gy = posten[gedeeld_idx]
    ax.add_patch(
        Ellipse(
            (gx, gy),
            width=post_w + 0.2,
            height=post_h + 0.18,
            facecolor="none",
            edgecolor="black",
            linewidth=1.3,
            zorder=7,
        )
    )

    ax.add_patch(
        Circle((0, 0), straal, fill=False, edgecolor="#3b6ea5", linewidth=1.8, zorder=5)
    )
    ax.text(
        0,
        straal + 0.55,
        "Totale massa posten SSO ($N$ totaal); elke post bestaat uit eurocenten"
        if met_centen
        else "Totale massa posten SSO ($N$ totaal)",
        ha="center",
        fontsize=10,
        color="#3b6ea5",
    )

    def _punten_in_ellips(cx_, cy_, w, h, n):
        punten = []
        while len(punten) < n:
            x = rng.uniform(cx_ - w / 2, cx_ + w / 2)
            y = rng.uniform(cy_ - h / 2, cy_ + h / 2)
            if ((x - cx_) / (w / 2)) ** 2 + ((y - cy_) / (h / 2)) ** 2 <= 0.85:
                punten.append((x, y))
        return punten

    def _pijlen(bx_c, by_c, w, h, kleur, doelen, rad):
        bronnen = _punten_in_ellips(bx_c, by_c, w * 0.7, h * 0.7, len(doelen))
        for (bx, by), (tx, ty) in zip(bronnen, doelen, strict=True):
            ax.plot(bx, by, "o", color=kleur, markersize=4, zorder=6)
            ax.add_patch(
                FancyArrowPatch(
                    (bx, by),
                    (tx, ty),
                    arrowstyle="-|>",
                    mutation_scale=8,
                    color=kleur,
                    linewidth=0.9,
                    alpha=0.8,
                    zorder=5.5,
                    connectionstyle=f"arc3,rad={rad}",
                )
            )

    # Klanten (rechts): pijlen naar het midden van een hele post.
    klant_bronnen = [
        ("Klant A", 6.6, 2.6, 2.3, 1.9),
        ("Klant B", 6.6, -0.2, 2.3, 1.9),
        ("Klant C", 6.6, -2.9, 2.1, 1.7),
    ]
    for naam, bx_c, by_c, w, h in klant_bronnen:
        kleur = klant_kleuren[naam]
        ax.add_patch(
            Ellipse(
                (bx_c, by_c),
                width=w,
                height=h,
                facecolor=kleur,
                alpha=0.25,
                edgecolor=kleur,
                linewidth=1.5,
                zorder=2,
            )
        )
        ax.text(
            bx_c,
            by_c + h / 2 + 0.25,
            f"{naam} ($steek_{naam[-1]}$)",
            ha="center",
            fontsize=8.5,
            color=kleur,
            fontweight="bold",
        )
        doelen = [posten[i] for i in klant_posten[naam]]
        _pijlen(bx_c, by_c, w, h, kleur, doelen, rad=-0.1)

    # SSO-steekproef (links): pijlen naar één eurocent in een post.
    sx_c, sy_c, sw, sh = -6.6, 0.0, 2.0, 2.0
    ax.add_patch(
        Ellipse(
            (sx_c, sy_c),
            width=sw,
            height=sh,
            facecolor=kleur_s,
            alpha=0.25,
            edgecolor=kleur_s,
            linewidth=1.5,
            zorder=2,
        )
    )
    ax.text(
        sx_c,
        sy_c + sh / 2 + 0.25,
        "SSO-steekproef ($steek_0$, eurocenten)"
        if met_centen
        else "SSO-steekproef ($steek_0$)",
        ha="center",
        fontsize=8.5,
        color=kleur_s,
        fontweight="bold",
    )
    if met_centen:
        doelen_s = [centen[i][gestoken_cent[i]] for i in steekproef_posten]
    else:
        doelen_s = [posten[i] for i in steekproef_posten]
    _pijlen(sx_c, sy_c, sw, sh, kleur_s, doelen_s, rad=0.1)

    if met_centen:
        legenda = [
            Line2D(
                [],
                [],
                marker="o",
                color="none",
                markerfacecolor="#6e6e6e",
                markersize=3,
                label="eurocent",
            ),
            Line2D(
                [],
                [],
                marker="o",
                color="none",
                markerfacecolor=kleur_s,
                markersize=6,
                label="eurocent in de SSO-steekproef",
            ),
            Patch(
                facecolor="#e8a33d",
                alpha=0.75,
                edgecolor="#9a9a9a",
                label="post die een klant steekt (de hele post)",
            ),
        ]
        ax.legend(
            handles=legenda,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.02),
            ncol=3,
            fontsize=8,
            frameon=False,
        )

    ax.set_xlim(-9.0, 9.0)
    ax.set_ylim(-5.6 if met_centen else -4.8, 5.6)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig


def teken_sso_steekproefschema():
    """Eerste plaatje: de SSO-steekproef en de klanten op de massa posten."""
    return teken_sso_schema(met_centen=False)


def teken_sso_geldsteekproefschema():
    """Tweede plaatje: dezelfde situatie, met eurocenten in de posten."""
    return teken_sso_schema(met_centen=True)


THEORIE_FIGUREN = {
    "fig-sso-steekproefschema": teken_sso_steekproefschema,
    "fig-sso-geldsteekproefschema": teken_sso_geldsteekproefschema,
}
