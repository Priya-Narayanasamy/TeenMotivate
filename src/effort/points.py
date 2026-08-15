"""The points engine.

Everything negotiable lives in ``POINTS_CONFIG`` at the top of this file. Change
a number there and the whole app follows — including the "How points work"
panel in the UI, which is generated from this dict so it cannot drift from the
code.

Two rules are structural rather than numeric, and are relied on everywhere:
points are never negative, and points are never taken away once earned.
"""

from __future__ import annotations

import math

import pandas as pd

POINTS_CONFIG = {
    # Base rate: this many minutes earns one point, before the multiplier.
    "minutes_per_point": 5,

    # What an entry is worth per minute, decided by the *kind* of thing it was
    # rather than by a self-rating. She no longer has to judge her own effort;
    # the rate is agreed once, here, and applies the same way every time.
    "category_multipliers": {
        "School Work": 1.0,
        "Tuition": 1.25,
        "Chores": 1.25,
        "Sports": 1.5,
        "Painting": 2.0,
        "Reading book": 2.0,
        "Science with Appa": 2.0,
        "Piano": 2.0,
    },

    # Used if a category somehow has no rate of its own. Never rewards more
    # than the agreed rates, and never zero, so an entry always counts.
    "default_multiplier": 1.0,

    # The most minutes of one activity that can count towards points in a
    # single day. Longer is fine and still shows in the charts — it just stops
    # earning. Two sessions of the same activity on one day share this cap.
    "daily_activity_cap_minutes": 60,

    # Weeks run Monday to Sunday.
    "week_starts_on_weekday": 0,

    # Whole-week rewards for spreading effort out, on top of activity points.
    "bonuses": {
        "distinct_days": {
            "threshold": 5,
            "points": 10,
            "label": "Spread-out bonus",
            "describe": "log something on {threshold} or more different days in a week",
        },
        "distinct_categories": {
            "threshold": 3,
            "points": 10,
            "label": "Mix-it-up bonus",
            "describe": "log {threshold} or more different categories in a week",
        },
    },

    # Starting position of the target slider on the This Week page.
    "default_weekly_target": 150,
}

SCORED_COLUMNS = ("countable_minutes", "multiplier", "points")

WEEKLY_COLUMNS = (
    "week_start",
    "week_end",
    "activity_points",
    "distinct_days",
    "distinct_categories",
    "distinct_days_bonus",
    "distinct_categories_bonus",
    "bonus_points",
    "total_points",
    "minutes",
    "entries",
)


def _round_half_up(value: float) -> int:
    """Round to the nearest whole point, with halves going up.

    Python's built-in ``round`` rounds halves to even, so 2.5 becomes 2. For a
    12-year-old counting her own points, losing one to a rounding convention she
    has never heard of is indefensible. Values here are never negative, so
    ``floor(value + 0.5)`` is exactly "round half up".
    """
    return int(math.floor(value + 0.5))


def week_start(when, config: dict = POINTS_CONFIG) -> pd.Timestamp:
    """The Monday of the week containing ``when`` (midnight, no time part)."""
    stamp = pd.Timestamp(when).normalize()
    weekday = config["week_starts_on_weekday"]
    return stamp - pd.Timedelta(days=(stamp.weekday() - weekday) % 7)


def week_end(when, config: dict = POINTS_CONFIG) -> pd.Timestamp:
    """The Sunday closing the week containing ``when``."""
    return week_start(when, config) + pd.Timedelta(days=6)


def score_entries(valid: pd.DataFrame, config: dict = POINTS_CONFIG) -> pd.DataFrame:
    """Add ``countable_minutes``, ``multiplier`` and ``points`` to valid rows.

    The daily cap applies per activity per day: two Maths sessions on the same
    day share one 60-minute allowance. The earlier session fills it first, so
    the minutes that stop counting are the ones at the end of the day.
    """
    scored = valid.copy()

    if scored.empty:
        for name in SCORED_COLUMNS:
            scored[name] = pd.Series(dtype="float64" if name == "multiplier" else "int64")
        scored["week_start"] = pd.Series(dtype="datetime64[ns]")
        return scored

    scored = scored.sort_values("date", kind="stable").reset_index(drop=True)

    cap = config["daily_activity_cap_minutes"]
    # Same activity written with different capitalisation is still the same
    # activity as far as the cap is concerned.
    day_activity = [scored["date"], scored["activity"].str.strip().str.casefold()]
    already_counted = scored.groupby(day_activity, sort=False)["minutes"].cumsum() - scored["minutes"]
    allowance = (cap - already_counted).clip(lower=0)

    scored["countable_minutes"] = scored["minutes"].where(scored["minutes"] < allowance, allowance).astype("int64")
    scored["multiplier"] = (
        scored["category"]
        .map(config["category_multipliers"])
        .fillna(config.get("default_multiplier", 1.0))
        .astype("float64")
    )

    raw = scored["countable_minutes"] / config["minutes_per_point"] * scored["multiplier"]
    scored["points"] = raw.map(_round_half_up).astype("int64")

    scored["week_start"] = scored["date"].map(lambda day: week_start(day, config))
    return scored


def weekly_totals(valid: pd.DataFrame, config: dict = POINTS_CONFIG) -> pd.DataFrame:
    """One row per week that has entries, with bonuses applied.

    Weeks with no entries are absent rather than zero — see :func:`week_summary`
    for the single-week view the This Week page needs.
    """
    scored = score_entries(valid, config)

    if scored.empty:
        empty = {name: pd.Series(dtype="int64") for name in WEEKLY_COLUMNS}
        empty["week_start"] = pd.Series(dtype="datetime64[ns]")
        empty["week_end"] = pd.Series(dtype="datetime64[ns]")
        for name in ("distinct_days_bonus", "distinct_categories_bonus"):
            empty[name] = pd.Series(dtype="bool")
        return pd.DataFrame(empty)

    grouped = scored.groupby("week_start", sort=True)
    weeks = pd.DataFrame({
        "activity_points": grouped["points"].sum(),
        "distinct_days": grouped["date"].nunique(),
        "distinct_categories": grouped["category"].nunique(),
        "minutes": grouped["minutes"].sum(),
        "entries": grouped["date"].size(),
    }).reset_index()

    bonuses = config["bonuses"]
    weeks["distinct_days_bonus"] = weeks["distinct_days"] >= bonuses["distinct_days"]["threshold"]
    weeks["distinct_categories_bonus"] = (
        weeks["distinct_categories"] >= bonuses["distinct_categories"]["threshold"]
    )
    weeks["bonus_points"] = (
        weeks["distinct_days_bonus"].astype("int64") * bonuses["distinct_days"]["points"]
        + weeks["distinct_categories_bonus"].astype("int64") * bonuses["distinct_categories"]["points"]
    )
    weeks["total_points"] = weeks["activity_points"] + weeks["bonus_points"]
    weeks["week_end"] = weeks["week_start"] + pd.Timedelta(days=6)

    return weeks.loc[:, list(WEEKLY_COLUMNS)].reset_index(drop=True)


def week_summary(valid: pd.DataFrame, when, config: dict = POINTS_CONFIG) -> dict:
    """Everything the This Week page shows, for the week containing ``when``.

    A week with no entries returns a fully-formed zero summary rather than
    nothing, so the page never has to guard against a missing key.
    """
    start = week_start(when, config)
    weeks = weekly_totals(valid, config)
    match = weeks.loc[weeks["week_start"] == start] if not weeks.empty else weeks

    bonuses = config["bonuses"]
    if match.empty:
        summary = {
            "week_start": start,
            "week_end": start + pd.Timedelta(days=6),
            "activity_points": 0,
            "distinct_days": 0,
            "distinct_categories": 0,
            "distinct_days_bonus": False,
            "distinct_categories_bonus": False,
            "bonus_points": 0,
            "total_points": 0,
            "minutes": 0,
            "entries": 0,
        }
    else:
        summary = match.iloc[0].to_dict()
        for name in ("activity_points", "distinct_days", "distinct_categories",
                     "bonus_points", "total_points", "minutes", "entries"):
            summary[name] = int(summary[name])

    summary["days_to_next_bonus"] = max(
        0, bonuses["distinct_days"]["threshold"] - summary["distinct_days"]
    )
    summary["categories_to_next_bonus"] = max(
        0, bonuses["distinct_categories"]["threshold"] - summary["distinct_categories"]
    )

    previous = weekly_totals(valid, config)
    previous_start = start - pd.Timedelta(days=7)
    previous_match = (
        previous.loc[previous["week_start"] == previous_start] if not previous.empty else previous
    )
    summary["previous_total_points"] = (
        int(previous_match.iloc[0]["total_points"]) if not previous_match.empty else 0
    )
    summary["delta_points"] = summary["total_points"] - summary["previous_total_points"]

    return summary


def category_breakdown(valid: pd.DataFrame, when=None, config: dict = POINTS_CONFIG) -> pd.DataFrame:
    """Points and minutes per category, for one week or for everything.

    Bonuses are whole-week and belong to no category, so they are not included.
    """
    scored = score_entries(valid, config)
    if when is not None and not scored.empty:
        scored = scored.loc[scored["week_start"] == week_start(when, config)]

    if scored.empty:
        return pd.DataFrame({
            "category": pd.Series(dtype="string"),
            "points": pd.Series(dtype="int64"),
            "minutes": pd.Series(dtype="int64"),
            "entries": pd.Series(dtype="int64"),
        })

    grouped = scored.groupby("category", observed=True)
    return (
        pd.DataFrame({
            "points": grouped["points"].sum(),
            "minutes": grouped["minutes"].sum(),
            "entries": grouped["date"].size(),
        })
        .reset_index()
        .sort_values("points", ascending=False, kind="stable")
        .reset_index(drop=True)
    )


def current_streak(valid: pd.DataFrame, today=None) -> int:
    """Consecutive days up to today with at least one entry.

    If nothing is logged yet today the streak is measured to yesterday, so it
    does not appear to break every midnight before she has had a chance to log.
    """
    if valid.empty:
        return 0

    today = pd.Timestamp(today).normalize() if today is not None else pd.Timestamp.today().normalize()
    logged = set(valid["date"].dt.normalize())

    if today in logged:
        cursor = today
    elif (today - pd.Timedelta(days=1)) in logged:
        cursor = today - pd.Timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in logged:
        streak += 1
        cursor -= pd.Timedelta(days=1)
    return streak


def total_earned(valid: pd.DataFrame, config: dict = POINTS_CONFIG) -> int:
    """All points ever earned, bonuses included. Never negative."""
    weeks = weekly_totals(valid, config)
    if weeks.empty:
        return 0
    return max(0, int(weeks["total_points"].sum()))


def rules_markdown(config: dict = POINTS_CONFIG) -> str:
    """The "How points work" text, built from the config so it cannot go stale."""
    per_point = config["minutes_per_point"]
    cap = config["daily_activity_cap_minutes"]
    multipliers = config["category_multipliers"]
    bonuses = config["bonuses"]

    example_minutes = 30
    # Best-paying first, so the answer to "what's worth most?" is the top row.
    ordered = sorted(multipliers.items(), key=lambda pair: (-pair[1], pair[0]))
    example_lines = [
        f"| {name} | ×{rate:g} | {example_minutes} minutes → "
        f"**{_round_half_up(example_minutes / per_point * rate)} points** |"
        for name, rate in ordered
    ]

    days = bonuses["distinct_days"]
    categories = bonuses["distinct_categories"]

    return f"""
**Every {per_point} minutes you spend is worth 1 point.**

Then the *kind* of thing it was decides what those minutes are worth. You don't
have to rate yourself — the rate is the same every time, and you can see it here.

| What you did | Worth | For example |
| --- | --- | --- |
{chr(10).join(example_lines)}

**Two bonuses, each worth {days["points"]} points, for whole weeks:**

- **{days["label"]}** — {days["describe"].format(threshold=days["threshold"])}.
- **{categories["label"]}** — {categories["describe"].format(threshold=categories["threshold"])}.

**The small print:**

- One activity counts for up to **{cap} minutes a day**. Do more if you want to —
  it still shows up in your charts, it just stops earning points. If you do the
  same thing twice in a day, the two sessions share those {cap} minutes.
- Weeks run **Monday to Sunday**. Bonuses are worked out when the week ends.
- Half a point always rounds **up**, never down.
- **Points are never taken away.** Once you've earned them, they're yours — you
  can't go backwards, and nothing you do can make your total go down.
""".strip()
