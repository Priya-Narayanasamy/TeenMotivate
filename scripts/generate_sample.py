"""Generate data/sample_effort_log.csv — seeded, so it regenerates identically.

Six weeks of plausible entries for a 12-year-old, ending Sat 2026-08-15, plus a
handful of deliberately broken rows so the validation panel has something to show.

The shape follows the real log: `activity` is what she did (Swimming, Geography)
and `category` is the kind of thing it was, which is what earns the multiplier.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 12
TODAY = date(2026, 8, 15)  # Saturday
WEEKS = 6

ACTIVITIES = {
    "School Work": ["Geography", "English", "Maths", "Science", "History"],
    "Tuition": ["Maths", "English"],
    "Sports": ["Swimming", "Netball", "Bike ride"],
    "Chores": ["Tidy room", "Dishes", "Walk the dog"],
    "Painting": ["Watercolours", "Sketching"],
    "Reading book": ["Reading"],
    "Science with Appa": ["Volcano experiment", "Star gazing", "Circuit kit"],
}

NOTES = [
    "", "", "", "", "",
    "Assignment",
    "Homework",
    "tricky bits at the end",
    "did it without being asked",
    "really did not feel like it",
    "finished the whole chapter",
    "coach said good effort",
]

SCHOOL_NIGHT = ["School Work", "Tuition", "Reading book", "Chores", "Painting"]
WEEKEND = ["Sports", "Chores", "Reading book", "Painting", "Science with Appa"]


def make_row(rng, day, category):
    return {
        "date": day.isoformat(),
        "activity": rng.choice(ACTIVITIES[category]),
        "category": category,
        "minutes": str(rng.choice([10, 15, 20, 25, 30, 30, 40, 45, 50, 60, 75, 90])),
        # Still written, still ignored by the engine. Kept so the column stays
        # readable and so old logs and new ones look the same.
        "effort": str(rng.choices([1, 2, 3], weights=[3, 4, 3])[0]),
        "notes": rng.choice(NOTES),
    }


def main():
    rng = random.Random(SEED)
    rows = []

    # Weeks run Monday-Sunday. Start on the Monday six weeks before this week's.
    this_monday = TODAY - timedelta(days=TODAY.weekday())
    start = this_monday - timedelta(weeks=WEEKS - 1)

    day = start
    while day <= TODAY:
        is_current_week = day >= this_monday

        if is_current_week:
            # Deliberate: this week logs Mon/Tue/Thu/Fri only — 4 distinct days.
            # The 3-category bonus is earned, the 5-day one is not yet. Gives the
            # This Week page something to nudge her about.
            if day.weekday() not in (0, 1, 3, 4):
                day += timedelta(days=1)
                continue
            n = rng.choice([1, 2])
        else:
            n = rng.choices([0, 1, 2, 3], weights=[1, 4, 4, 2])[0]

        pool = WEEKEND if day.weekday() >= 5 else SCHOOL_NIGHT
        picked = rng.sample(pool, k=min(n, len(pool)))
        for category in picked:
            rows.append(make_row(rng, day, category))

        day += timedelta(days=1)

    # A day with two Maths sessions over the 60-minute cap, so the cap is visible
    # in the data rather than only in the tests.
    cap_day = this_monday - timedelta(days=6)  # the Tuesday of last week
    rows.append({
        "date": cap_day.isoformat(), "activity": "Maths", "category": "Tuition",
        "minutes": "45", "effort": "2", "notes": "Homework",
    })
    rows.append({
        "date": cap_day.isoformat(), "activity": "Maths", "category": "Tuition",
        "minutes": "40", "effort": "3", "notes": "kept going after dinner",
    })

    rows.sort(key=lambda r: r["date"])

    # Deliberately broken rows, scattered through the file. Each one exercises a
    # different validation rule. They must never crash the app. Note that a bad
    # effort value is NOT here: effort no longer earns points, so it can no
    # longer invalidate a row.
    broken = [
        (8, {"date": "2026-07-14", "activity": "Swimming", "category": "Sports",
             "minutes": "2000", "effort": "2", "notes": "longer than a day"}),
        (17, {"date": "2026-07-20", "activity": "Maths", "category": "Tuition",
              "minutes": "abc", "effort": "2", "notes": "minutes not a number"}),
        (26, {"date": "2026-07-27", "activity": "Reading", "category": "Leisure",
              "minutes": "25", "effort": "2", "notes": "category not on the list"}),
        (34, {"date": "", "activity": "Reading", "category": "Reading book",
              "minutes": "20", "effort": "1", "notes": "no date"}),
        (41, {"date": "2026-08-03", "activity": "Bike ride", "category": "Sports",
              "minutes": "-30", "effort": "2", "notes": "negative minutes"}),
        (48, {"date": "2026-08-06", "activity": "", "category": "Chores",
              "minutes": "15", "effort": "1", "notes": "no activity name"}),
        # Not broken, both on purpose: an Australian-format date, and a blank
        # effort — which is now perfectly normal.
        (52, {"date": "07/08/2026", "activity": "Walk the dog", "category": "Chores",
              "minutes": "20", "effort": "", "notes": "day-first date, no effort"}),
    ]
    for index, row in broken:
        rows.insert(min(index, len(rows)), row)

    out = Path(__file__).resolve().parents[1] / "data" / "sample_effort_log.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date", "activity", "category", "minutes", "effort", "notes"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
