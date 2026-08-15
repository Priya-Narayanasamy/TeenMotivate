"""Regenerate the README's points-rules section from POINTS_CONFIG.

    uv run python scripts/update_readme.py

The app's "How points work" panel is generated at render time, so it can never
be stale. The README is a file, so it needs this. Run it after changing
POINTS_CONFIG.
"""

from pathlib import Path

from effort.points import POINTS_CONFIG, rules_markdown

README = Path(__file__).resolve().parents[1] / "README.md"
START = "<!-- points-rules:start -->"
END = "<!-- points-rules:end -->"
NOTE = "<!-- Generated from POINTS_CONFIG. Run: uv run python scripts/update_readme.py -->"


def main() -> int:
    text = README.read_text(encoding="utf-8")

    if START not in text or END not in text:
        print(f"Could not find {START} / {END} in README.md")
        return 1

    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)

    body = rules_markdown(POINTS_CONFIG)
    updated = f"{before}{START}\n{NOTE}\n\n{body}\n\n{END}{after}"

    if updated == text:
        print("README.md already up to date.")
        return 0

    README.write_text(updated, encoding="utf-8")
    print("README.md points-rules section updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
