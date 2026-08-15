"""Tests for the points engine.

Only the engine — this is where the rules she cares about live, and where a
quiet mistake would show up as points she did or didn't get.

Dates are chosen deliberately: 2026-08-10 is a Monday, 2026-08-09 the Sunday
before it. The first test asserts that, so the rest can rely on it.
"""

import pandas as pd
import pytest

from effort.config import CATEGORIES
from effort.points import (
    POINTS_CONFIG,
    category_breakdown,
    current_streak,
    rules_markdown,
    score_entries,
    total_earned,
    week_start,
    week_summary,
    weekly_totals,
)
from effort.validation import VALID_DTYPES

MONDAY = "2026-08-10"
SUNDAY_BEFORE = "2026-08-09"


def make_log(rows):
    """Build a frame shaped exactly like validated output."""
    columns = ["date", "activity", "category", "minutes", "effort", "notes"]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        frame = pd.DataFrame({name: pd.Series(dtype="object") for name in columns})
    return frame.astype(VALID_DTYPES)


def entry(date, activity="Geography", category="School Work", minutes=30, effort=1, notes=""):
    return {
        "date": pd.Timestamp(date),
        "activity": activity,
        "category": category,
        "minutes": minutes,
        "effort": effort,
        "notes": notes,
    }


def test_every_category_has_a_rate_and_every_rate_has_a_category():
    """The two lists must agree, or a category silently stops working.

    CATEGORIES is what validation accepts; category_multipliers is what the
    engine pays. Adding a new activity means editing both — miss one and either
    the rows are rejected despite having a rate, or a category is accepted and
    quietly paid the default.
    """
    accepted = set(CATEGORIES)
    priced = set(POINTS_CONFIG["category_multipliers"])

    assert accepted - priced == set(), "accepted but has no rate of its own"
    assert priced - accepted == set(), "has a rate but validation will reject it"


def test_chosen_dates_are_the_weekdays_the_tests_assume():
    assert pd.Timestamp(MONDAY).day_name() == "Monday"
    assert pd.Timestamp(SUNDAY_BEFORE).day_name() == "Sunday"


# --- the 60-minute cap ------------------------------------------------------

def test_single_activity_caps_at_sixty_minutes():
    log = make_log([entry(MONDAY, minutes=90)])
    scored = score_entries(log)

    assert scored.loc[0, "countable_minutes"] == 60
    assert scored.loc[0, "minutes"] == 90, "the logged minutes are left alone"
    assert scored.loc[0, "points"] == 12  # 60 / 5 * 1.0 (School Work)


def test_two_sessions_of_the_same_activity_share_one_daily_cap():
    log = make_log([
        entry(MONDAY, activity="Maths", category="Tuition", minutes=45),
        entry(MONDAY, activity="Maths", category="Tuition", minutes=40),
    ])
    scored = score_entries(log)

    # The earlier session fills the allowance first: 45, then 15 of the 40.
    assert list(scored["countable_minutes"]) == [45, 15]
    assert scored["countable_minutes"].sum() == 60
    assert list(scored["points"]) == [11, 4]  # 45/5*1.25 = 11.25 -> 11; 15/5*1.25 = 3.75 -> 4


def test_the_cap_is_per_activity_not_per_day():
    log = make_log([
        entry(MONDAY, activity="Geography", category="School Work", minutes=90),
        entry(MONDAY, activity="Swimming", category="Sports", minutes=90),
    ])
    scored = score_entries(log)

    assert list(scored["countable_minutes"]) == [60, 60]


def test_the_cap_resets_the_next_day():
    log = make_log([
        entry(MONDAY, minutes=60),
        entry("2026-08-11", minutes=60),
    ])
    scored = score_entries(log)

    assert list(scored["countable_minutes"]) == [60, 60]


def test_the_same_activity_typed_differently_still_shares_the_cap():
    log = make_log([
        entry(MONDAY, activity="Geography", minutes=45),
        entry(MONDAY, activity="geography ", minutes=45),
    ])
    scored = score_entries(log)

    assert scored["countable_minutes"].sum() == 60


# --- category multipliers and rounding -------------------------------------

@pytest.mark.parametrize(
    "category,expected",
    [
        ("School Work", 6),         # 30/5 * 1.0
        ("Tuition", 8),             # 30/5 * 1.25 = 7.5 -> 8
        ("Chores", 8),              # 30/5 * 1.25 = 7.5 -> 8
        ("Sports", 9),              # 30/5 * 1.5
        ("Painting", 12),           # 30/5 * 2.0
        ("Reading book", 12),
        ("Science with Appa", 12),
    ],
)
def test_the_category_decides_the_multiplier(category, expected):
    scored = score_entries(make_log([entry(MONDAY, category=category, minutes=30)]))
    assert scored.loc[0, "points"] == expected


def test_effort_no_longer_changes_anything():
    """The same entry scores the same whatever effort says, including blank."""
    scores = [
        score_entries(make_log([entry(MONDAY, minutes=30, effort=value)])).loc[0, "points"]
        for value in (1, 2, 3, pd.NA)
    ]
    assert len(set(scores)) == 1, f"effort still moves the points: {scores}"


def test_an_unknown_category_falls_back_rather_than_scoring_zero():
    # Validation keeps unknown categories out, but the engine must not produce
    # a zero if one ever reaches it.
    scored = score_entries(make_log([entry(MONDAY, category="Something New", minutes=30)]))
    assert scored.loc[0, "points"] == 6  # the default multiplier of 1.0


def test_halves_round_up_not_to_even():
    # 10 minutes of Tuition is exactly 2.5 points. Python's round() would give
    # 2 here; she gets 3.
    scored = score_entries(make_log([entry(MONDAY, category="Tuition", minutes=10)]))
    assert scored.loc[0, "points"] == 3


# --- the two weekly bonuses -------------------------------------------------

def days_log(day_count, categories=("School Work",)):
    rows = []
    for offset in range(day_count):
        category = categories[offset % len(categories)]
        rows.append(entry(
            pd.Timestamp(MONDAY) + pd.Timedelta(days=offset),
            activity=f"{category} work",
            category=category,
            minutes=30,
        ))
    return make_log(rows)


def test_five_distinct_days_earns_the_spread_out_bonus():
    four = weekly_totals(days_log(4)).iloc[0]
    five = weekly_totals(days_log(5)).iloc[0]

    assert not four["distinct_days_bonus"]
    assert five["distinct_days_bonus"]
    assert five["total_points"] - five["activity_points"] == 10


def test_three_distinct_categories_earns_the_mix_it_up_bonus():
    two = weekly_totals(days_log(2, ("School Work", "Tuition"))).iloc[0]
    three = weekly_totals(days_log(3, ("School Work", "Tuition", "Sports"))).iloc[0]

    assert not two["distinct_categories_bonus"]
    assert three["distinct_categories_bonus"]
    assert three["bonus_points"] == 10


def test_both_bonuses_stack():
    week = weekly_totals(days_log(5, ("School Work", "Tuition", "Sports"))).iloc[0]

    assert week["distinct_days_bonus"]
    assert week["distinct_categories_bonus"]
    assert week["bonus_points"] == 20
    assert week["total_points"] == week["activity_points"] + 20


def test_repeating_one_category_over_five_days_earns_only_the_day_bonus():
    week = weekly_totals(days_log(5, ("School Work",))).iloc[0]

    assert week["distinct_days_bonus"]
    assert not week["distinct_categories_bonus"]
    assert week["bonus_points"] == 10


def test_several_entries_on_one_day_are_still_one_distinct_day():
    log = make_log([
        entry(MONDAY, activity="Geography", category="School Work"),
        entry(MONDAY, activity="Reading", category="Reading book"),
        entry(MONDAY, activity="Swimming", category="Sports"),
    ])
    week = weekly_totals(log).iloc[0]

    assert week["distinct_days"] == 1
    assert week["distinct_categories"] == 3
    assert week["bonus_points"] == 10  # categories only


# --- the Monday week boundary ----------------------------------------------

def test_week_starts_on_monday():
    assert week_start(MONDAY) == pd.Timestamp(MONDAY)
    assert week_start("2026-08-16") == pd.Timestamp(MONDAY)  # the Sunday closing it
    assert week_start(SUNDAY_BEFORE) == pd.Timestamp("2026-08-03")


def test_sunday_and_the_next_monday_are_different_weeks():
    log = make_log([
        entry(SUNDAY_BEFORE, minutes=30),
        entry(MONDAY, minutes=30),
    ])
    weeks = weekly_totals(log)

    assert len(weeks) == 2
    assert list(weeks["week_start"]) == [pd.Timestamp("2026-08-03"), pd.Timestamp(MONDAY)]


def test_a_bonus_earned_on_sunday_does_not_leak_into_the_next_week():
    # Five days Wed-Sun earns the day bonus for that week only. The Monday after
    # is a fresh start with nothing carried over.
    rows = [
        entry(pd.Timestamp("2026-08-05") + pd.Timedelta(days=offset), minutes=30)
        for offset in range(5)
    ]
    rows.append(entry(MONDAY, minutes=30))
    weeks = weekly_totals(make_log(rows)).set_index("week_start")

    assert weeks.loc[pd.Timestamp("2026-08-03"), "bonus_points"] == 10
    assert weeks.loc[pd.Timestamp(MONDAY), "bonus_points"] == 0


def test_the_week_boundary_falls_between_sunday_night_and_monday_morning():
    assert week_start("2026-08-09") != week_start("2026-08-10")
    assert week_start("2026-08-10") == week_start("2026-08-16")


# --- an empty week ----------------------------------------------------------

def test_empty_log_produces_no_weeks_and_no_points():
    empty = make_log([])

    assert weekly_totals(empty).empty
    assert score_entries(empty).empty
    assert category_breakdown(empty).empty
    assert total_earned(empty) == 0
    assert current_streak(empty, today=MONDAY) == 0


def test_a_week_with_no_entries_summarises_as_zeros_not_an_error():
    log = make_log([entry("2026-07-06", minutes=30)])  # a different week entirely
    summary = week_summary(log, MONDAY)

    assert summary["total_points"] == 0
    assert summary["activity_points"] == 0
    assert summary["bonus_points"] == 0
    assert summary["distinct_days"] == 0
    assert summary["distinct_categories"] == 0
    assert summary["entries"] == 0
    assert summary["week_start"] == pd.Timestamp(MONDAY)
    assert summary["week_end"] == pd.Timestamp("2026-08-16")


def test_an_empty_week_still_reports_what_is_needed_for_the_bonuses():
    summary = week_summary(make_log([]), MONDAY)

    assert summary["days_to_next_bonus"] == 5
    assert summary["categories_to_next_bonus"] == 3


def test_an_empty_week_after_a_good_one_shows_a_negative_delta_but_never_negative_points():
    log = days_log(5, ("School Work", "Tuition", "Sports"))  # week of 2026-08-10
    summary = week_summary(log, "2026-08-17")  # the week after, empty

    assert summary["total_points"] == 0
    assert summary["previous_total_points"] > 0
    assert summary["delta_points"] < 0, "the comparison can fall"
    assert summary["total_points"] >= 0, "the points themselves cannot"


# --- a single-row dataset ---------------------------------------------------

def test_a_single_row_is_enough_to_run_everything():
    log = make_log([entry(MONDAY, category="Tuition", minutes=30)])

    scored = score_entries(log)
    assert len(scored) == 1
    assert scored.loc[0, "points"] == 8  # 30 / 5 * 1.25 = 7.5 -> 8

    weeks = weekly_totals(log)
    assert len(weeks) == 1
    assert weeks.loc[0, "activity_points"] == 8
    assert weeks.loc[0, "bonus_points"] == 0, "one entry earns no bonus"
    assert weeks.loc[0, "total_points"] == 8

    summary = week_summary(log, MONDAY)
    assert summary["total_points"] == 8
    assert summary["distinct_days"] == 1
    assert summary["previous_total_points"] == 0
    assert summary["delta_points"] == 8

    breakdown = category_breakdown(log, MONDAY)
    assert len(breakdown) == 1
    assert breakdown.loc[0, "category"] == "Tuition"
    assert breakdown.loc[0, "points"] == 8

    assert total_earned(log) == 8
    assert current_streak(log, today=MONDAY) == 1


# --- points never go backwards ---------------------------------------------

def test_points_are_never_negative_for_any_effort_or_length():
    log = make_log([
        entry(MONDAY, activity=f"thing {n}", minutes=minutes, effort=effort)
        for n, (minutes, effort) in enumerate([(1, 1), (1, 3), (2, 1), (7, 2), (1440, 3)])
    ])
    scored = score_entries(log)

    assert (scored["points"] >= 0).all()
    assert (scored["countable_minutes"] >= 0).all()
    assert total_earned(log) >= 0


def test_adding_an_entry_never_lowers_the_total():
    before = make_log([entry(MONDAY, minutes=30)])
    after = make_log([entry(MONDAY, minutes=30), entry("2026-08-11", minutes=5, effort=1)])

    assert total_earned(after) >= total_earned(before)


def test_a_very_short_entry_earns_nothing_but_does_not_take_anything_away():
    scored = score_entries(make_log([entry(MONDAY, minutes=1, effort=1)]))
    assert scored.loc[0, "points"] == 0  # 1/5 = 0.2 -> 0


# --- streak -----------------------------------------------------------------

def test_streak_counts_consecutive_days_back_from_today():
    log = make_log([
        entry("2026-08-12"), entry("2026-08-13"), entry("2026-08-14"),
    ])
    assert current_streak(log, today="2026-08-14") == 3


def test_streak_survives_a_day_that_has_not_been_logged_yet():
    log = make_log([entry("2026-08-12"), entry("2026-08-13")])
    # Nothing logged today yet — the streak holds rather than breaking at midnight.
    assert current_streak(log, today="2026-08-14") == 2
    # But a whole missed day does break it.
    assert current_streak(log, today="2026-08-15") == 0


def test_a_gap_ends_the_streak():
    log = make_log([entry("2026-08-10"), entry("2026-08-12"), entry("2026-08-13")])
    assert current_streak(log, today="2026-08-13") == 2


# --- the generated rules text ----------------------------------------------

def test_rules_text_is_built_from_the_config():
    text = rules_markdown()

    assert str(POINTS_CONFIG["minutes_per_point"]) in text
    assert str(POINTS_CONFIG["daily_activity_cap_minutes"]) in text
    assert POINTS_CONFIG["bonuses"]["distinct_days"]["label"] in text
    assert "Monday to Sunday" in text


def test_rules_text_follows_a_changed_config():
    changed = {
        **POINTS_CONFIG,
        "minutes_per_point": 10,
        "daily_activity_cap_minutes": 45,
        "bonuses": {
            **POINTS_CONFIG["bonuses"],
            "distinct_days": {**POINTS_CONFIG["bonuses"]["distinct_days"], "threshold": 6},
        },
    }
    text = rules_markdown(changed)

    assert "Every 10 minutes" in text
    assert "45 minutes a day" in text
    assert "6 or more different days" in text


def test_a_changed_config_changes_the_points():
    log = make_log([entry(MONDAY, minutes=60, effort=1)])
    generous = {**POINTS_CONFIG, "minutes_per_point": 2}

    assert score_entries(log, generous).loc[0, "points"] == 30
    assert score_entries(log).loc[0, "points"] == 12
