"""Reading the effort log off disk.

Nothing here interprets a value — that is validation's job — so a file full of
nonsense still loads fine. Every cell comes back as text, exactly as typed.

Only whole-file problems raise (missing file, unreadable, no usable header).
The app catches those and shows a friendly panel; bad *rows* never raise.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import COLUMNS, LIVE_LOG, OPTIONAL_COLUMNS, SAMPLE_LOG


class LogFileError(Exception):
    """The file as a whole cannot be used. The message is shown to the user."""


def active_log_path() -> Path:
    """Her real log if she has one, otherwise the sample that ships with the repo.

    Lives here so the app and the command line agree on which file is "the"
    log. They used to decide separately, which meant `check_data.py` could
    quietly report on the sample while the app was showing her real data.
    """
    return LIVE_LOG if LIVE_LOG.exists() else SAMPLE_LOG


def load_log(path: str | Path) -> pd.DataFrame:
    """Return the raw log as text columns, in file order.

    The result always has exactly the contract columns. Optional columns that
    are absent are filled with empty strings; extra columns are dropped.
    """
    path = Path(path)

    if not path.exists():
        raise LogFileError(f"No log file at {path}. Expected a CSV with columns: {', '.join(COLUMNS)}.")

    try:
        frame = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,  # an empty note is "", never NaN
            na_filter=False,
            skip_blank_lines=False,  # keep line numbers matching the file
            encoding="utf-8-sig",  # tolerate a BOM from Excel
        )
    except UnicodeDecodeError:
        raise LogFileError(f"{path.name} is not UTF-8 text. Re-save it as CSV UTF-8.") from None
    except pd.errors.EmptyDataError:
        raise LogFileError(f"{path.name} is empty. It needs a header row: {', '.join(COLUMNS)}.") from None
    except pd.errors.ParserError as exc:
        raise LogFileError(f"{path.name} is not valid CSV: {exc}") from None
    except OSError as exc:
        raise LogFileError(f"Could not read {path.name}: {exc}") from None

    frame.columns = [str(name).strip().lower() for name in frame.columns]

    missing = [name for name in COLUMNS if name not in frame.columns]
    required_missing = [name for name in missing if name not in OPTIONAL_COLUMNS]
    if required_missing:
        raise LogFileError(
            f"{path.name} is missing these columns: {', '.join(required_missing)}. "
            f"Expected: {', '.join(COLUMNS)}."
        )

    for name in missing:
        frame[name] = ""

    frame = frame.loc[:, list(COLUMNS)]

    # Row 0 of the frame is line 2 of the file (line 1 is the header). Carry the
    # real line number so problems can point at something the user can go and fix.
    frame = frame.reset_index(drop=True)
    frame["_line"] = frame.index + 2

    # A row where every contract cell is blank is a spacer, not a mistake.
    filled = frame.loc[:, list(COLUMNS)].map(lambda value: str(value).strip() != "")
    return frame.loc[filled.any(axis=1)].reset_index(drop=True)
