"""Trends — how the weeks compare.

Three charts, one filter row. The sidebar category filter scopes all three, and
because colour is pinned to the category, filtering never repaints the
categories that remain.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from .. import theme
from ..config import CATEGORIES
from ..points import POINTS_CONFIG, score_entries, weekly_totals
from .common import DAY_NAMES, get_data, problems_panel, source_caption, week_label


def _category_filter() -> list[str]:
    st.sidebar.subheader("Trends")
    chosen = st.sidebar.multiselect(
        "Categories",
        options=list(CATEGORIES),
        default=list(CATEGORIES),
        help="Applies to all three charts.",
    )
    return chosen or list(CATEGORIES)


def _points_line(weeks: pd.DataFrame) -> alt.LayerChart:
    """Points per week. One series, so no legend — the heading names it."""
    ink = theme.chrome()
    color = ink["series"][0]

    frame = weeks.assign(label=weeks["week_start"].map(week_label))
    hover = alt.selection_point(on="pointerover", nearest=True, fields=["week_start"], empty=False)

    base = alt.Chart(frame).encode(
        x=alt.X("week_start:T", title=None,
                axis=alt.Axis(format="%d %b", tickCount=len(frame), grid=False)),
        y=alt.Y("total_points:Q", title="Points", scale=alt.Scale(zero=True)),
    )

    # Straight segments, not a smoothed curve: a curve through six weekly points
    # invents mid-week values that were never measured.
    line = base.mark_line(strokeWidth=2, color=color)
    points = base.mark_point(size=80, filled=True, color=color, stroke=ink["surface"], strokeWidth=2)

    # A crosshair rule that follows the pointer, carrying the tooltip. The hit
    # area is the full column height, so it is not a pinpoint target.
    crosshair = base.mark_rule(color=ink["baseline"], strokeWidth=1).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[
            alt.Tooltip("label:N", title="Week"),
            alt.Tooltip("total_points:Q", title="Points"),
            alt.Tooltip("activity_points:Q", title="From activities"),
            alt.Tooltip("bonus_points:Q", title="Bonuses"),
            alt.Tooltip("distinct_days:Q", title="Days logged"),
        ],
    ).add_params(hover)

    # Direct-label the most recent week only — the axis and tooltip carry the rest.
    label = (
        alt.Chart(frame.tail(1))
        .mark_text(align="right", dx=-8, dy=-14, fontSize=12, fontWeight=600,
                   color=ink["text_primary"])
        .encode(x="week_start:T", y="total_points:Q", text=alt.Text("total_points:Q", format="d"))
    )

    target = st.session_state.get("weekly_target", POINTS_CONFIG["default_weekly_target"])
    goal = (
        alt.Chart(pd.DataFrame({"target": [target]}))
        .mark_rule(color=ink["muted"], strokeWidth=1)
        .encode(y="target:Q")
    )

    return (goal + crosshair + line + points + label).properties(height=260)


def _category_stack(scored: pd.DataFrame) -> alt.Chart:
    """Minutes by category per week. Stacked, with a 2px surface gap between segments."""
    ink = theme.chrome()

    by_week = (
        scored.groupby(["week_start", "category"], observed=True)["minutes"].sum().reset_index()
    )
    by_week["label"] = by_week["week_start"].map(week_label)
    week_order = list(by_week.sort_values("week_start")["label"].unique())

    return (
        alt.Chart(by_week)
        .mark_bar(cornerRadiusEnd=4, stroke=ink["surface"], strokeWidth=2)
        .encode(
            x=alt.X("label:N", title=None, sort=week_order,
                    axis=alt.Axis(labelAngle=0, labelFontSize=11)),
            y=alt.Y("minutes:Q", title="Minutes", stack="zero"),
            color=alt.Color(
                "category:N",
                scale=theme.category_scale(),
                sort=list(CATEGORIES),
                legend=alt.Legend(title=None, orient="bottom", columns=4, symbolLimit=8),
            ),
            order=alt.Order("category:N"),
            tooltip=[
                alt.Tooltip("label:N", title="Week"),
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("minutes:Q", title="Minutes"),
            ],
        )
        .properties(height=280)
    )


def _day_heatmap(scored: pd.DataFrame) -> alt.Chart:
    """Which days she works. Sequential blue, one hue, light to dark."""
    ink = theme.chrome()

    grid = scored.copy()
    grid["day"] = grid["date"].dt.dayofweek.map(dict(enumerate(DAY_NAMES)))
    grid["label"] = grid["week_start"].map(week_label)

    cells = grid.groupby(["week_start", "label", "day"], observed=True).agg(
        minutes=("minutes", "sum"), points=("points", "sum"), entries=("date", "size"),
    ).reset_index()

    week_order = list(cells.sort_values("week_start")["label"].unique())

    return (
        alt.Chart(cells)
        .mark_rect(cornerRadius=4, stroke=ink["surface"], strokeWidth=2)
        .encode(
            x=alt.X("day:N", title=None, sort=list(DAY_NAMES),
                    axis=alt.Axis(labelAngle=0, labelFontSize=11, ticks=False, domain=False)),
            # labelOverlap=False: every week gets its label. Left to itself Vega
            # drops alternate ones, and a heatmap row with no label is unreadable.
            y=alt.Y("label:N", title=None, sort=week_order,
                    axis=alt.Axis(labelFontSize=11, ticks=False, domain=False,
                                  labelOverlap=False)),
            color=alt.Color(
                "minutes:Q",
                scale=alt.Scale(range=list(ink["sequential"])),
                legend=alt.Legend(title="Minutes", orient="bottom", gradientLength=140),
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Week"),
                alt.Tooltip("day:N", title="Day"),
                alt.Tooltip("minutes:Q", title="Minutes"),
                alt.Tooltip("points:Q", title="Points"),
                alt.Tooltip("entries:Q", title="Entries"),
            ],
        )
        # A fixed row height, so the cells stay square-ish however many weeks
        # there are, instead of being squashed into a total height.
        .properties(height=alt.Step(30))
    )


def render() -> None:
    valid, problems = get_data()
    chosen = _category_filter()

    st.title("Trends")
    problems_panel(problems)

    if valid.empty:
        st.info(
            "**Nothing to chart yet.** Once there are a few entries in the log, "
            "the weekly picture shows up here.",
            icon="📈",
        )
        source_caption()
        return

    filtered = valid.loc[valid["category"].isin(chosen)]
    if filtered.empty:
        st.warning("No entries match the categories chosen in the sidebar.", icon="🔍")
        source_caption()
        return

    if len(chosen) < len(CATEGORIES):
        st.caption(f"Filtered to: {', '.join(chosen)}.")

    scored = score_entries(filtered)
    weeks = weekly_totals(filtered)

    st.subheader("Points per week")
    st.caption("The grey line is the weekly target.")
    st.altair_chart(theme.style(_points_line(weeks)), width="stretch")

    st.subheader("Minutes by category")
    st.altair_chart(theme.style(_category_stack(scored)), width="stretch")

    st.subheader("Which days")
    st.caption("Darker means more minutes. Blank means nothing logged that day.")
    st.altair_chart(theme.style(_day_heatmap(scored)), width="stretch")

    with st.expander("See the numbers"):
        st.dataframe(
            weeks.assign(week=weeks["week_start"].map(week_label)).loc[
                :, ["week", "total_points", "activity_points", "bonus_points",
                    "distinct_days", "distinct_categories", "minutes", "entries"]
            ].rename(columns={
                "week": "Week", "total_points": "Points", "activity_points": "From activities",
                "bonus_points": "Bonuses", "distinct_days": "Days",
                "distinct_categories": "Categories", "minutes": "Minutes", "entries": "Entries",
            }),
            hide_index=True,
            width="stretch",
        )

    source_caption()
