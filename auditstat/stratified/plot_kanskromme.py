import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from auditstat._formatting import nl_getal


def _gekleurde_subtitel(
    ax, segmenten: list[tuple[str, str]], y: float = 1.04, fontsize: int = 10
):
    """Teken een subtitel boven ``ax`` opgebouwd uit meerdere, los gekleurde tekststukken.

    Matplotlib ondersteunt geen kleurwisseling binnen één tekststring (ook niet via
    mathtext, dat geen ``\\color``-commando kent), dus elk stuk wordt als los
    ``Text``-object getekend en op basis van de werkelijk gerenderde breedte
    (via de canvas-renderer) tegen elkaar aan gepositioneerd en gezamenlijk
    gecentreerd boven de as.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    teksten = [
        ax.text(
            0,
            y,
            tekst,
            fontsize=fontsize,
            color=kleur,
            ha="left",
            va="bottom",
            transform=ax.transAxes,
        )
        for tekst, kleur in segmenten
    ]

    fig.canvas.draw()
    breedtes = [t.get_window_extent(renderer=renderer).width for t in teksten]
    totale_breedte = sum(breedtes)

    as_bbox = ax.get_window_extent(renderer=renderer)
    start_x = as_bbox.x0 + (as_bbox.width - totale_breedte) / 2

    inv = ax.transAxes.inverted()
    cum_x = start_x
    for t, breedte in zip(teksten, breedtes, strict=True):
        x_frac, _ = inv.transform((cum_x, 0))
        t.set_position((x_frac, y))
        cum_x += breedte

    return teksten


def plot_kanskromme(res: dict) -> plt.Figure:
    """Teken de kanskromme van de evaluatie.

    Parameters
    ----------
    res:
        Het resultaatobject uit ``eval_stratified``.

    Returns
    -------
    matplotlib.figure.Figure
    """
    d = res["kanskromme"]
    totaal_geld = res["populatie_totaal"]
    min_geld = sum(res["steekproeven"]["fout_hoog"])
    totaal_laag_geld = sum(res["steekproeven"]["waarde_laag"])

    mode_val = max(res["mw_fout_convolutie_geld"], min_geld)
    max_val = max(res["max_fout_convolutie_geld"], min_geld)

    zekerheid_pct = res["invoer"]["zekerheid"] * 100
    rest_pct = 100 - zekerheid_pct

    lbl_binnen = f"linker {zekerheid_pct:.0f}%"
    lbl_buiten = f"rechter {rest_pct:.0f}%"
    lbl_onm_min = "Onmogelijk (< minimum fout)"
    lbl_onm_max = "Onmogelijk (> populatiewaarde)"

    fig, ax = plt.subplots(figsize=(10, 5))

    # Speciale weergave als alles integraal is gecontroleerd.
    if totaal_laag_geld < 0.01:
        ax.text(
            0.5,
            0.5,
            f"100% Integraal Gecontroleerd\n\nEr is geen statistische onzekerheid.\n"
            f"De fout is exact vastgesteld op \u20ac {nl_getal(min_geld, 2)}",
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="#2c3e50",
            transform=ax.transAxes,
        )
        ax.axis("off")
        return fig

    x_geld = np.array(d["x"]) * totaal_geld
    y_dichtheid = np.array(d["y"])

    # Kleuren per gebied.
    kleuren = {
        lbl_binnen: "#2980b9",
        lbl_buiten: "#aed6f1",
        lbl_onm_min: "#e74c3c",
        lbl_onm_max: "#e67e22",
    }

    def gebied_van(x):
        if x < min_geld:
            return lbl_onm_min
        if x > totaal_geld:
            return lbl_onm_max
        if x <= max_val:
            return lbl_binnen
        return lbl_buiten

    # Teken de gevulde vlakken per gebied via maskers en onthoud welke we tekenen.
    gebruikte_labels = []

    for lbl, kleur in kleuren.items():
        if lbl == lbl_onm_min:
            masker = x_geld < min_geld
        elif lbl == lbl_onm_max:
            masker = x_geld > totaal_geld
        elif lbl == lbl_buiten:
            masker = (x_geld > max_val) & (x_geld <= totaal_geld)
        else:
            masker = (x_geld >= min_geld) & (x_geld <= max_val)

        # Controleer of er in dit gebied daadwerkelijk kansmassa (y > 1e-10) is.
        # Dit voorkomt dat een onzichtbare platte lijn op y=0 de legenda triggert.
        if (masker & (y_dichtheid > 1e-10)).any():
            ax.fill_between(
                x_geld, y_dichtheid, where=masker, color=kleur, alpha=0.8, label=lbl
            )
            gebruikte_labels.append(lbl)

    # Buitenste contourlijn.
    ax.plot(x_geld, y_dichtheid, color="#2c3e50", linewidth=1)

    # Verticale referentielijnen.
    ax.axvline(mode_val, color="blue", linestyle="--", linewidth=1)
    ax.axvline(max_val, color="red", linestyle="--", linewidth=1)

    # Opmaak.
    def nl_format(x, _pos=None):
        return f"\u20ac\u00a0{nl_getal(x, 0)}"

    ax.xaxis.set_major_formatter(plt.FuncFormatter(nl_format))
    ax.set_xlabel("fout in euro\u2019s", fontsize=12)
    ax.set_ylabel("relatieve kansdichtheid", fontsize=12)
    ax.set_yticks([])

    # --- NIEUW: Opmaak Titels ---
    fig.suptitle(
        "kanskromme van de geprojecteerde fout", fontweight="bold", fontsize=14
    )

    # --- NIEUW: Schaal X-as ---
    # Zoom in zodat de grafiek geen 'naald' wordt.
    # We pakken de maximale fout * 2.5, maar we maximeren dit op de omvang van de totale populatie.
    x_lim_max = min(max_val * 2.5, totaal_geld)
    if x_lim_max <= 0:
        x_lim_max = totaal_geld if totaal_geld > 0 else 1.0
    ax.set_xlim(0, x_lim_max)

    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.spines[["top", "right", "left"]].set_visible(False)

    # Legenda: bouw deze nu puur op basis van de gebruikte_labels
    legend_patches = [
        mpatches.Patch(color=kleuren[lbl], label=lbl) for lbl in gebruikte_labels
    ]

    ax.legend(
        handles=legend_patches,
        loc="upper right",
        title="kansmassa",
        title_fontsize=10,
        fontsize=9,
        ncol=2,
    )

    # Layout eerst vastzetten: de gekleurde subtitel hieronder positioneert zijn
    # tekststukken op basis van de uiteindelijke, gerenderde as-afmetingen, dus
    # een latere tight_layout/subplots_adjust zou die positionering weer verstoren.
    fig.tight_layout()
    fig.subplots_adjust(top=0.88)

    # Subtitel: "blauwe lijn"/"rode lijn" in de bijpassende kleur, zodat de tekst
    # overeenkomt met wat ze beschrijft (zie _gekleurde_subtitel hierboven).
    _gekleurde_subtitel(
        ax,
        [
            ("blauwe lijn", "blue"),
            (" = meest waarschijnlijke fout   |   ", "#2c3e50"),
            ("rode lijn", "red"),
            (f" = maximale fout ({zekerheid_pct:.0f}% zekerheid)", "#2c3e50"),
        ],
    )

    return fig
