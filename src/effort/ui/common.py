"""Pieces every page shares: data loading, the problems panel, the rules expander.

Streamlit files stay thin on purpose — anything that decides *what a number is*
lives in the engine modules, and this package only decides how it looks.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from ..config import LIVE_LOG, SAMPLE_LOG
from ..loading import LogFileError, load_log
from ..points import POINTS_CONFIG, rules_markdown
from ..validation import validate

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def active_log_path() -> Path:
    """Her real log if she has one, otherwise the sample that ships with the repo."""
    return LIVE_LOG if LIVE_LOG.exists() else SAMPLE_LOG


@st.cache_data(show_spinner=False)
def _read(path_text: str, _fingerprint: tuple) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    """Load and validate. The fingerprint busts the cache when the file changes."""
    try:
        raw = load_log(path_text)
    except LogFileError as exc:
        return pd.DataFrame(), pd.DataFrame(), str(exc)
    result = validate(raw)
    return result.valid, result.problems, None


def get_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """``(valid, problems)`` for the active log.

    A file-level failure is shown and the page stops there — but it stops with
    an explanation, not a traceback.
    """
    path = active_log_path()
    fingerprint = (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else (0, 0)
    valid, problems, error = _read(str(path), fingerprint)

    if error:
        st.error(f"**Nothing could be read from the log file.**\n\n{error}")
        st.stop()

    return valid, problems


def today() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def problems_panel(problems: pd.DataFrame) -> None:
    """Everything that could not be counted, and why. Never blocks the page."""
    if problems.empty:
        return

    rows = int(problems["line"].nunique())
    noun = "entry" if rows == 1 else "entries"
    with st.expander(f"⚠️ {rows} {noun} couldn't be counted — tap to see why", expanded=False):
        st.caption(
            f"Everything else was counted as normal. Fix these in "
            f"`{active_log_path().name}` and they'll appear straight away."
        )
        st.dataframe(
            problems.rename(columns={
                "line": "Line",
                "date": "Date",
                "activity": "Activity",
                "problem": "What's wrong",
            }),
            hide_index=True,
            width="stretch",
        )


def rules_expander(expanded: bool = False) -> None:
    """The "How points work" panel, generated from POINTS_CONFIG."""
    with st.expander("🎯 How points work", expanded=expanded):
        st.markdown(rules_markdown(POINTS_CONFIG))


def source_caption() -> None:
    path = active_log_path()
    if path == SAMPLE_LOG:
        st.caption(f"Reading the sample log (`{path.name}`). Drop your own in as `data/effort_log.csv`.")
    else:
        st.caption(f"Reading `{path.name}`.")


def week_label(start: pd.Timestamp) -> str:
    """"11 – 17 Aug" style, kept short enough for a phone."""
    end = start + pd.Timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {end.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b')}"
