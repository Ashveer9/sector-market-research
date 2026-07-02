"""A single, consistent visual identity for every figure in the project."""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# A calm, professional consulting palette.
PALETTE = [
    "#0B3D91",  # deep blue (primary)
    "#00A6A6",  # teal
    "#F4A259",  # amber
    "#BC4749",  # brick
    "#6A4C93",  # purple
    "#8AC926",  # green
]
PRIMARY = PALETTE[0]
ACCENT = PALETTE[1]


def apply_theme() -> None:
    """Apply the shared matplotlib rcParams. Idempotent."""
    mpl.rcParams.update(
        {
            "figure.figsize": (10, 6),
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.prop_cycle": mpl.cycler(color=PALETTE),
            "legend.frameon": False,
        }
    )


def savefig(fig: plt.Figure, path, title: str | None = None) -> None:
    """Save a figure, optionally setting a suptitle, and close it."""
    if title:
        fig.suptitle(title, fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
