"""Chart colours and Altair defaults.

The palette is the data-viz reference palette, used unchanged and in its
documented slot order — that order is what makes it colourblind-safe for
adjacent marks (stacked segments, bars, lines), so it is not cosmetic and
should not be re-shuffled.

Dark mode is a selected set of steps for the dark surface, not an automatic
flip of the light ones.
"""

from __future__ import annotations

from .config import CATEGORIES

# Categorical slots 1-8, in order. Eight categories, eight slots, no cycling.
SERIES_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                "#e87ba4", "#008300", "#4a3aa7", "#e34948")
SERIES_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500",
               "#d55181", "#008300", "#9085e9", "#e66767")

# Sequential blue, light -> dark, for the heatmap's continuous magnitude.
SEQUENTIAL_LIGHT = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
SEQUENTIAL_DARK = ("#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb")

CHROME = {
    "light": {
        "surface": "#fcfcfb",
        "text_primary": "#0b0b0b",
        "text_secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "baseline": "#c3c2b7",
        "success": "#006300",
        "series": SERIES_LIGHT,
        "sequential": SEQUENTIAL_LIGHT,
    },
    "dark": {
        "surface": "#1a1a19",
        "text_primary": "#ffffff",
        "text_secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "baseline": "#383835",
        "success": "#0ca30c",
        "series": SERIES_DARK,
        "sequential": SEQUENTIAL_DARK,
    },
}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def mode() -> str:
    """Whichever theme Streamlit is currently rendering in."""
    try:
        import streamlit as st

        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


def chrome(which: str | None = None) -> dict:
    return CHROME[which or mode()]


def category_colors(which: str | None = None) -> dict:
    """Category -> hex, fixed for the life of the app.

    Colour follows the category, never its current rank or position, so
    filtering categories in the sidebar never repaints the survivors.
    """
    series = chrome(which)["series"]
    return {name: series[index] for index, name in enumerate(CATEGORIES)}


def category_scale(which: str | None = None):
    """An Altair colour scale pinned to the full category list."""
    import altair as alt

    colors = category_colors(which)
    return alt.Scale(domain=list(CATEGORIES), range=[colors[name] for name in CATEGORIES])


def style(chart, which: str | None = None):
    """Apply the shared chrome: hairline solid grid, recessive axes, no border."""
    ink = chrome(which)
    return (
        chart.configure_view(stroke=None, fill=ink["surface"])
        .configure(background=ink["surface"], font=FONT)
        .configure_axis(
            gridColor=ink["grid"],
            gridWidth=1,
            domainColor=ink["baseline"],
            tickColor=ink["baseline"],
            labelColor=ink["muted"],
            titleColor=ink["text_secondary"],
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
            grid=True,
        )
        .configure_legend(
            labelColor=ink["text_secondary"],
            titleColor=ink["text_secondary"],
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight="normal",
            symbolType="square",
            symbolSize=90,
        )
        .configure_title(color=ink["text_primary"], fontSize=13, fontWeight=600, anchor="start")
    )
