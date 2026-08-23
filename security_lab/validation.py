from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from security_lab.common import REPORTS, SEVERITIES, newest_directories, read_json, write_json_atomic


def find_previous_run(current: Path, reports: Path = REPORTS) -> Path | None:
    for candidate in newest_directories(reports, "defense-*"):
        if candidate.resolve() == current.resolve():
            continue
        if (candidate / "summary.json").is_file():
            return candidate
    return None


def compare_runs(current: Path, previous: Path | None) -> dict[str, Any]:
    current_summary = read_json(current / "summary.json", None)
    if not isinstance(current_summary, dict):
        raise ValueError(f"Missing or invalid summary: {current / 'summary.json'}")

    previous_summary = read_json(previous / "summary.json", {}) if previous else {}
    current_severity = current_summary.get("severity") or {}
    previous_severity = previous_summary.get("severity") or {}

    delta: dict[str, dict[str, int]] = {}
    for level in SEVERITIES:
        before = int(previous_severity.get(level, 0))
        after = int(current_severity.get(level, 0))
        delta[level] = {"before": before, "after": after, "change": after - before}

    result = {
        "current": current.name,
        "previous": previous.name if previous else None,
        "severity_delta": delta,
        "regression": any(delta[level]["change"] > 0 for level in ("critical", "high")),
        "improved": any(delta[level]["change"] < 0 for level in SEVERITIES),
    }
    write_json_atomic(current / "validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the latest defensive findings with a prior run.")
    parser.add_argument("current", nargs="?", type=Path)
    args = parser.parse_args()

    if args.current:
        current = args.current.resolve()
    else:
        runs = newest_directories(REPORTS, "defense-*")
        if not runs:
            parser.error("no defensive review run found")
        current = runs[0]

    previous = find_previous_run(current)
    try:
        result = compare_runs(current, previous)
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
