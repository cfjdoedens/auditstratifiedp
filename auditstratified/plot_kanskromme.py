import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


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
            0.5, 0.5,
            f"100% Integraal Gecontroleerd\n\nEr is geen statistische onzekerheid.\n"
            f"De fout is exact vastgesteld op \u20ac {min_geld:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            ha="center", va="center", fontsize=13, fontweight="bold", color="#2c3e50",
            transform=ax.transAxes
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

    # Teken de gevulde vlakken per gebied via maskers.
    for lbl, kleur in kleuren.items():
        if lbl == lbl_onm_min:
            masker = x_geld < min_geld
        elif lbl == lbl_onm_max:
            masker = x_geld > totaal_geld
        elif lbl == lbl_buiten:
            masker = (x_geld > max_val) & (x_geld <= totaal_geld)
        else:
            masker = (x_geld >= min_geld) & (x_geld <= max_val)

        if masker.any():
            ax.fill_between(x_geld, y_dichtheid, where=masker, color=kleur, alpha=0.8, label=lbl)

    # Buitenste contourlijn.
    ax.plot(x_geld, y_dichtheid, color="#2c3e50", linewidth=1)

    # Verticale referentielijnen.
    ax.axvline(mode_val, color="blue", linestyle="--", linewidth=1)
    ax.axvline(max_val, color="red", linestyle="--", linewidth=1)

    # Opmaak.
    def nl_format(x, _pos=None):
        return f"\u20ac\u00a0{x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

    ax.xaxis.set_major_formatter(plt.FuncFormatter(nl_format))
    ax.set_xlabel("fout in euro\u2019s", fontsize=12)
    ax.set_ylabel("relatieve kansdichtheid", fontsize=12)
    ax.set_title("kanskromme van de geprojecteerde fout", fontweight="bold", fontsize=13)
    ax.set_yticks([])

    subtitle = (
        f"blauwe lijn = meest waarschijnlijke fout  |  "
        f"rode lijn = maximale fout ({zekerheid_pct:.0f}% zekerheid)"
    )
    ax.set_title(subtitle, fontsize=10, loc="left", pad=0)
    ax.set_title("kanskromme van de geprojecteerde fout", fontweight="bold", fontsize=13, loc="center")

    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.spines[["top", "right", "left"]].set_visible(False)

    # Legenda.
    legend_patches = [
        mpatches.Patch(color=kleuren[lbl_binnen], label=lbl_binnen),
        mpatches.Patch(color=kleuren[lbl_buiten], label=lbl_buiten),
        mpatches.Patch(color=kleuren[lbl_onm_min], label=lbl_onm_min),
        mpatches.Patch(color=kleuren[lbl_onm_max], label=lbl_onm_max),
    ]
    ax.legend(
        handles=legend_patches,
        loc="upper right",
        title="kansmassa",
        title_fontsize=10,
        fontsize=9,
        ncol=2,
    )

    fig.tight_layout()
    return fig
