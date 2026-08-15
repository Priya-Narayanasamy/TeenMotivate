"""Turning raw text rows into typed, trustworthy ones.

The rule for the whole app: a bad row is set aside and explained, never fatal.
:func:`validate` splits the log into rows the points engine can trust and a
table of problems the UI shows in a panel.

Messages are written for a parent and a 12-year-old reading them together, so
they say what is wrong and what to type instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from .config import CATEGORIES, DATE_FORMATS, EFFORT_LEVELS, MAX_SENSIBLE_MINUTES

_CATEGORY_BY_LOWER = {name.lower(): name for name in CATEGORIES}

VALID_DTYPES = {
    "date": "datetime64[ns]",
    "activity": "string",
    "category": "string",
    "minutes": "int64",
    "effort": "int64",
    "notes": "string",
}

PROBLEM_COLUMNS = ("line", "date", "activity", "problem")


@dataclass(frozen=True)
class ValidationResult:
    """Rows that passed, and an explanation for every row that did not."""

    valid: pd.DataFrame
    problems: pd.DataFrame

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def problem_count(self) -> int:
        """Number of *rows* set aside (a row can have more than one problem)."""
        if self.problems.empty:
            return 0
        return int(self.problems["line"].nunique())

    @property
    def is_clean(self) -> bool:
        return self.problems.empty


def _empty(columns, dtypes=None) -> pd.DataFrame:
    frame = pd.DataFrame({name: pd.Series(dtype="object") for name in columns})
    if dtypes:
        frame = frame.astype(dtypes)
    return frame


def parse_date(text: str):
    """Return a ``date`` for any format we accept, else ``None``."""
    text = str(text).strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_int(text: str):
    """Return an ``int`` for a whole number, else ``None``. Accepts "30.0"."""
    text = str(text).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number != int(number):
        return None
    return int(number)


def canonical_category(text: str):
    """Match a category ignoring case and spacing. ``None`` if it is not one of ours."""
    return _CATEGORY_BY_LOWER.get(str(text).strip().lower())


def validate(raw: pd.DataFrame) -> ValidationResult:
    """Split a raw log into usable rows and explained problems."""
    good: list[dict] = []
    problems: list[dict] = []

    for row in raw.to_dict("records"):
        line = row.get("_line", "?")
        faults: list[str] = []

        day = parse_date(row["date"])
        if day is None:
            raw_date = str(row["date"]).strip()
            faults.append(
                "The date is empty — every entry needs one, like 2026-08-15."
                if not raw_date
                else f'"{raw_date}" is not a date we recognise. Try 2026-08-15 or 15/08/2026.'
            )

        activity = str(row["activity"]).strip()
        if not activity:
            faults.append("The activity is empty — write what she actually did, like \"Maths homework\".")

        category = canonical_category(row["category"])
        if category is None:
            raw_category = str(row["category"]).strip()
            faults.append(
                f'"{raw_category}" is not one of the categories. '
                f"Use one of: {', '.join(CATEGORIES)}."
                if raw_category
                else f"The category is empty. Use one of: {', '.join(CATEGORIES)}."
            )

        minutes = parse_int(row["minutes"])
        if minutes is None:
            faults.append(f'"{str(row["minutes"]).strip()}" is not a whole number of minutes.')
        elif minutes <= 0:
            faults.append(f"{minutes} minutes is not something that can be logged — it needs to be above 0.")
        elif minutes > MAX_SENSIBLE_MINUTES:
            faults.append(f"{minutes} minutes is longer than a day. Check for a typo.")

        effort = parse_int(row["effort"])
        if effort is None or effort not in EFFORT_LEVELS:
            shown = str(row["effort"]).strip() or "(empty)"
            faults.append(
                f'Effort is "{shown}". It has to be 1, 2 or 3 — how hard she had to try.'
            )

        if faults:
            for fault in faults:
                problems.append({
                    "line": line,
                    "date": str(row["date"]).strip(),
                    "activity": activity or "(none)",
                    "problem": fault,
                })
            continue

        good.append({
            "date": pd.Timestamp(day),
            "activity": activity,
            "category": category,
            "minutes": minutes,
            "effort": effort,
            "notes": str(row["notes"]).strip(),
        })

    valid = pd.DataFrame(good).astype(VALID_DTYPES) if good else _empty(tuple(VALID_DTYPES), VALID_DTYPES)
    if good:
        valid = valid.sort_values("date", kind="stable").reset_index(drop=True)

    problem_frame = pd.DataFrame(problems) if problems else _empty(PROBLEM_COLUMNS)
    return ValidationResult(valid=valid, problems=problem_frame)
