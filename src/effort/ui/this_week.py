"""This Week — the page she actually opens."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from .. import theme
from ..points import POINTS_CONFIG, category_breakdown, current_streak, week_summary
from .common import get_data, problems_panel, rules_expander, source_caption, today


def _target() -> int:
    """The weekly goal, adjustable and remembered for the session."""
    default = POINTS_CONFIG["default_weekly_target"]
    st.sidebar.subheader("This week")
    return st.sidebar.slider(
        "Weekly points target",
        min_value=50,
        max_value=500,
        value=st.session_state.get("weekly_target", default),
        step=10,
        key="weekly_target",
        help=f"Where the goal line sits. Starts at {default}.",
    )


def _bonus_row(summary: dict) -> None:
    """Both weekly bonuses: earned, or how much is left to earn them."""
    bonuses = POINTS_CONFIG["bonuses"]
    left, right = st.columns(2)

    for column, key, remaining_key, unit in (
        (left, "distinct_days", "days_to_next_bonus", "day"),
        (right, "distinct_categories", "categories_to_next_bonus", "kind of thing"),
    ):
        bonus = bonuses[key]
        earned = summary[f"{key}_bonus"]
        remaining = summary[remaining_key]
        with column:
            if earned:
                st.success(f"**{bonus['label']}** earned  \n+{bonus['points']} points", icon="✅")
            else:
                plural = unit if remaining == 1 else f"{unit}s"
                st.info(
                    f"**{bonus['label']}**  \n{remaining} more {plural} for +{bonus['points']} points",
                    icon="⭐",
                )


def _breakdown_chart(breakdown: pd.DataFrame) -> alt.LayerChart:
    ink = theme.chrome()

    base = alt.Chart(breakdown).encode(
        # labelOverlap=False so every category keeps its name — the labels are
        # what carry identity here, with colour only echoing them.
        y=alt.Y("category:N", sort="-x", title=None,
                axis=alt.Axis(labelFontSize=12, labelPadding=8, ticks=False,
                              domain=False, labelOverlap=False)),
        x=alt.X("points:Q", title="Points", axis=alt.Axis(tickCount=4, grid=True)),
        tooltip=[
            alt.Tooltip("category:N", title="Category"),
            alt.Tooltip("points:Q", title="Points"),
            alt.Tooltip("minutes:Q", title="Minutes"),
            alt.Tooltip("entries:Q", title="Entries"),
        ],
    )

    bars = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
        # Colour is pinned to the category, so it means the same thing here as
        # it does on Trends. The axis labels carry identity; colour only echoes it.
        color=alt.Color("category:N", scale=theme.category_scale(), legend=None),
    )
    labels = base.mark_text(align="left", dx=6, fontSize=11, color=ink["text_secondary"]).encode(
        text=alt.Text("points:Q", format="d"),
    )

    return (bars + labels).properties(height=alt.Step(32))


def _empty_state(summary: dict, streak: int) -> None:
    st.info(
        "**Nothing logged this week yet.**\n\n"
        "Add a row to the log for anything you've done — homework, reading, piano, "
        "netball, even emptying the dishwasher. It all counts.",
        icon="📝",
    )

    left, right = st.columns(2)
    left.metric("Last week", f"{summary['previous_total_points']} pts")
    right.metric("Streak", f"{streak} days")

    if streak:
        st.caption(f"You're on a {streak}-day streak — one entry today keeps it going.")


def render() -> None:
    valid, problems = get_data()
    now = today()
    summary = week_summary(valid, now)
    streak = current_streak(valid, now)
    target = _target()

    st.title("This Week")
    st.caption(
        f"Monday {summary['week_start'].day} {summary['week_start'].strftime('%b')}"
        f" to Sunday {summary['week_end'].day} {summary['week_end'].strftime('%b')}"
    )

    problems_panel(problems)

    if summary["entries"] == 0:
        _empty_state(summary, streak)
        rules_expander()
        source_caption()
        return

    total = summary["total_points"]
    delta = summary["delta_points"]

    top = st.columns(4)
    top[0].metric(
        "Points",
        total,
        delta=f"{delta:+d} vs last week" if delta else "same as last week",
        # A gain is green; level or behind is grey, never red. Mid-week she is
        # nearly always "behind" last week's finished total, and this app does
        # not tell a child off for it being Tuesday.
        delta_color="normal" if delta > 0 else "off",
    )
    top[1].metric("Days logged", summary["distinct_days"])
    top[2].metric("Streak", f"{streak} days")
    top[3].metric("Minutes", summary["minutes"])

    progress = min(1.0, total / target) if target else 0.0
    st.progress(progress)
    if total >= target:
        st.caption(f"🎉 **Target smashed** — {total} of {target} points.")
    else:
        st.caption(f"{total} of {target} points — {target - total} to go.")

    _bonus_row(summary)

    st.subheader("Where the points came from")
    breakdown = category_breakdown(valid, now)
    st.altair_chart(theme.style(_breakdown_chart(breakdown)), width="stretch")

    with st.expander("See the numbers"):
        st.dataframe(
            breakdown.rename(columns={
                "category": "Category", "points": "Points",
                "minutes": "Minutes", "entries": "Entries",
            }),
            hide_index=True,
            width="stretch",
        )
        if summary["bonus_points"]:
            st.caption(
                f"Plus {summary['bonus_points']} bonus points for the whole week, "
                "which don't belong to any one category."
            )

    rules_expander()
    source_caption()
