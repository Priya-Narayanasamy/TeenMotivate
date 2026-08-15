"""Load and validate a log file, print what came back.

    uv run python scripts/check_data.py
    uv run python scripts/check_data.py path/to/other.csv

There is no UI yet — this is how you see phase 1 doing its job.
"""

import sys

from effort.loading import LogFileError, active_log_path, load_log
from effort.validation import validate


def main() -> int:
    # Same file the app would read, so the two can't disagree.
    path = sys.argv[1] if len(sys.argv) > 1 else active_log_path()

    try:
        raw = load_log(path)
    except LogFileError as exc:
        print(f"Cannot use this file:\n  {exc}")
        return 1

    result = validate(raw)

    print(f"File            {path}")
    print(f"Rows read       {len(raw)}")
    print(f"Rows usable     {result.valid_count}")
    print(f"Rows set aside  {result.problem_count}")

    if not result.is_clean:
        print("\nProblems")
        for row in result.problems.to_dict("records"):
            print(f"  line {row['line']:>3}  {row['activity'][:24]:<24}  {row['problem']}")

    if result.valid_count:
        valid = result.valid
        print(f"\nDates           {valid['date'].min().date()} to {valid['date'].max().date()}")
        print(f"Distinct days   {valid['date'].nunique()}")
        print(f"Total minutes   {int(valid['minutes'].sum())}")
        print("\nMinutes by category")
        by_category = valid.groupby("category", observed=True)["minutes"].agg(["count", "sum"])
        for name, row in by_category.sort_values("sum", ascending=False).iterrows():
            print(f"  {name:<10} {int(row['count']):>3} entries  {int(row['sum']):>5} min")
        print("\nFirst few usable rows")
        print(valid.head(5).to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
