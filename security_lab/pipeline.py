from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from security_lab.common import ROOT, read_json, run_command, write_json_atomic

_RUNTIME_DIRS = {".git", "reports", "artifacts", "loot"}


def _source_file_count(root: Path) -> int:
    count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _RUNTIME_DIRS for part in path.relative_to(root).parts):
            continue
        count += 1
    return count


def collect_inventory(output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    compose = root / "lab" / "docker-compose.yml"
    inventory = {
        "timestamp": int(time.time()),
        "git": run_command(["git", "status", "--short", "--branch"], cwd=root),
        "compose": run_command(
            ["docker", "compose", "-f", str(compose), "--profile", "operator", "config", "--services"],
            cwd=root,
        ),
        "source_files": _source_file_count(root),
    }
    write_json_atomic(output_dir / "inventory.json", inventory)
    return inventory


def _external_review_status(output_dir: Path) -> str:
    rc_path = output_dir / "external-review.rc"
    if not rc_path.is_file():
        return "not-configured"
    try:
        return "complete" if int(rc_path.read_text(encoding="utf-8").strip()) == 0 else "failed"
    except (OSError, ValueError):
        return "failed"


def finalize_pipeline(output_dir: Path) -> dict[str, Any]:
    summary = read_json(output_dir / "summary.json", {})
    validation = read_json(output_dir / "validation.json", {})
    fuzz = read_json(output_dir / "fuzz" / "summary.json", {})

    review_complete = (
        isinstance(summary, dict)
        and bool(summary)
        and bool((summary.get("coverage") or {}).get("complete", False))
    )
    review_status = "complete" if review_complete else ("partial" if summary else "failed")

    if isinstance(validation, dict) and validation:
        validation_status = "complete" if validation.get("previous") else "no-baseline"
    else:
        validation_status = "failed"

    pipeline = {
        "run": output_dir.name,
        "stages": {
            "inventory": "complete" if (output_dir / "inventory.json").is_file() else "failed",
            "review": review_status,
            "validation": validation_status,
            "fuzz": "complete" if (output_dir / "fuzz" / "summary.json").is_file() else "failed",
            "external_review": _external_review_status(output_dir),
        },
        "findings": summary.get("severity", {}) if isinstance(summary, dict) else {},
        "scan_coverage": summary.get("coverage", {}) if isinstance(summary, dict) else {},
        "regression": bool(validation.get("regression", False)) if isinstance(validation, dict) else False,
        "fuzz_results": int(fuzz.get("total_results", 0)) if isinstance(fuzz, dict) else 0,
    }
    write_json_atomic(output_dir / "pipeline.json", pipeline)
    return pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DPSR defensive pipeline helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inventory", "finalize"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("output_dir", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = collect_inventory(output_dir) if args.command == "inventory" else finalize_pipeline(output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
