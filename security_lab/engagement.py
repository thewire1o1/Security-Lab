from __future__ import annotations

import argparse
from pathlib import Path

from security_lab.common import ROOT, utc_timestamp
from security_lab.naming import normalize_slug

BASE = ROOT / "engagements"


def create_engagement(raw_name: str) -> Path:
    name = normalize_slug(raw_name)
    directory = BASE / name
    for child in ("scope", "notes", "evidence", "reports", "loot"):
        (directory / child).mkdir(parents=True, exist_ok=True)

    readme = directory / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# {name}\n\n"
            f"Created: {utc_timestamp()}\n\n"
            "## Scope\n"
            "See `scope/targets.txt`.\n\n"
            "## Notes\n"
            "Use `notes/` for working notes and `reports/` for generated output.\n",
            encoding="utf-8",
        )

    (directory / "scope" / "targets.txt").touch()
    (directory / "notes" / "timeline.md").touch()
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(prog="dpsr new", description="Create an engagement workspace.")
    parser.add_argument("name")
    args = parser.parse_args()
    try:
        print(create_engagement(args.name))
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
