"""The rewards catalogue and the redemption ledger.

Two files, both gitignored because they are hers:

- ``data/rewards.json`` — what she can spend points on, and what each costs.
- ``data/ledger.csv``   — append-only. One line per redemption, never edited.

Redeeming spends against a balance; it does not touch points earned. The
earned total only ever goes up, which is the promise the whole app makes.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import LEDGER_CSV, REWARDS_JSON

DEFAULT_REWARDS = [
    {"name": "Pick the Friday movie", "cost": 60},
    {"name": "Extra 30 minutes screen time", "cost": 80},
    {"name": "Choose Saturday dinner", "cost": 100},
    {"name": "Bake something together", "cost": 120},
    {"name": "A new book", "cost": 250},
    {"name": "Friend over for a sleepover", "cost": 400},
]

LEDGER_COLUMNS = ("redeemed_at", "reward", "cost")


def load_rewards(path: Path = REWARDS_JSON) -> pd.DataFrame:
    """The catalogue, falling back to sensible defaults on a missing or broken file.

    A corrupt file must not stop her seeing her balance, so this never raises.
    """
    rewards = DEFAULT_REWARDS
    if Path(path).exists():
        try:
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(loaded, list) and loaded:
                rewards = loaded
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            rewards = DEFAULT_REWARDS

    frame = pd.DataFrame(rewards)
    for column, default in (("name", ""), ("cost", 0)):
        if column not in frame.columns:
            frame[column] = default

    frame = frame.loc[:, ["name", "cost"]]
    frame["name"] = frame["name"].astype("string").fillna("")
    frame["cost"] = (
        pd.to_numeric(frame["cost"], errors="coerce").fillna(0).clip(lower=0).astype("int64")
    )
    return frame.reset_index(drop=True)


def save_rewards(frame: pd.DataFrame, path: Path = REWARDS_JSON) -> pd.DataFrame:
    """Write the catalogue back, dropping blank rows and negative costs."""
    clean = frame.copy()
    clean["name"] = clean["name"].astype("string").fillna("").str.strip()
    clean["cost"] = (
        pd.to_numeric(clean["cost"], errors="coerce").fillna(0).clip(lower=0).astype("int64")
    )
    clean = clean.loc[clean["name"] != ""].reset_index(drop=True)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(clean.to_dict("records"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return clean


def load_ledger(path: Path = LEDGER_CSV) -> pd.DataFrame:
    """Every redemption so far, oldest first. Missing or broken file reads as empty."""
    empty = pd.DataFrame({
        "redeemed_at": pd.Series(dtype="datetime64[ns]"),
        "reward": pd.Series(dtype="string"),
        "cost": pd.Series(dtype="int64"),
    })

    path = Path(path)
    if not path.exists():
        return empty

    try:
        frame = pd.read_csv(path, encoding="utf-8")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeDecodeError):
        return empty

    if not set(LEDGER_COLUMNS).issubset(frame.columns):
        return empty

    frame = frame.loc[:, list(LEDGER_COLUMNS)]
    frame["redeemed_at"] = pd.to_datetime(frame["redeemed_at"], errors="coerce", format="mixed")
    frame["reward"] = frame["reward"].astype("string").fillna("")
    frame["cost"] = pd.to_numeric(frame["cost"], errors="coerce").fillna(0).clip(lower=0).astype("int64")
    return frame.dropna(subset=["redeemed_at"]).reset_index(drop=True)


def total_redeemed(ledger: pd.DataFrame) -> int:
    if ledger.empty:
        return 0
    return int(ledger["cost"].sum())


def balance(earned: int, ledger: pd.DataFrame) -> int:
    """Points available to spend. Never below zero."""
    return max(0, int(earned) - total_redeemed(ledger))


def redeem(name: str, cost: int, path: Path = LEDGER_CSV) -> None:
    """Append one redemption. The ledger is only ever added to."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(LEDGER_COLUMNS)
        writer.writerow([datetime.now().isoformat(timespec="seconds"), name, int(cost)])
