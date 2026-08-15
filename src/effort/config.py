"""The data contract and where files live.

The points rules are NOT here — they sit in a config dict at the top of
``points.py``, next to the engine that applies them.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

SAMPLE_LOG = DATA_DIR / "sample_effort_log.csv"
# Her real log, if it exists, is preferred over the sample. Gitignored, like
# every CSV that is not the sample.
LIVE_LOG = DATA_DIR / "Efforts_Logged.csv"
REWARDS_JSON = DATA_DIR / "rewards.json"
LEDGER_CSV = DATA_DIR / "ledger.csv"

COLUMNS = ("date", "activity", "category", "minutes", "effort", "notes")
# Effort is optional: points come from the category now, so a blank effort cell
# is not a mistake. The column is still read and kept, just not scored.
OPTIONAL_COLUMNS = ("notes", "effort")

# The category is the *type* of thing it was; the activity is what she actually
# did ("Swimming", "Geography"). The multiplier attaches to the category, so
# this list and POINTS_CONFIG["category_multipliers"] must stay in step.
CATEGORIES = (
    "School Work",
    "Tuition",
    "Sports",
    "Chores",
    "Painting",
    "Reading book",
    "Science with Appa",
)

EFFORT_LEVELS = (1, 2, 3)

# A single activity longer than this is almost certainly a typo (25 hours in a day).
MAX_SENSIBLE_MINUTES = 1440

# Tried in order. ISO first, then the day-first formats an Australian keyboard
# produces, so "07/08/2026" means 7 August and not 8 July.
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d")
