"""Unified academic chart style (serif, thin grid, fixed palette)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = ["#222222", "#4682b4", "#e07b39", "#d94f3e", "#2a8f8f", "#7f6bab", "#808080"]
FIGSIZE = {
    "single": (9, 7), "wide": (11, 7), "tall": (9, 9), "small": (7, 5),
    "panel_2": (14, 7), "panel_3": (18, 7), "panel_2x2": (14, 14),
}
FS = 18


def setup_style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["CMU Serif", "STIX", "STIXGeneral", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix", "font.size": 18,
        "axes.titlesize": 20, "axes.titleweight": "normal", "axes.titlepad": 12,
        "axes.labelsize": 18, "axes.labelpad": 6, "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.labelsize": 16, "ytick.labelsize": 16,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 4, "ytick.major.size": 4,
        "xtick.direction": "out", "ytick.direction": "out",
        "axes.grid": True, "grid.alpha": 0.3, "grid.color": "#aaaaaa",
        "grid.linewidth": 0.5, "grid.linestyle": "-",
        "legend.fontsize": 16, "legend.frameon": False, "legend.handlelength": 1.5,
        "figure.dpi": 150, "figure.titlesize": 22, "figure.titleweight": "normal",
        "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.15,
        "lines.linewidth": 2.0, "lines.markersize": 5,
    })
