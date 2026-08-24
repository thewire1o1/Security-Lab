from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from security_lab.common import ROOT, read_json, utc_timestamp, write_json_atomic
from security_lab.naming import normalize_slug

BASE = ROOT / "cases"


def case_dir(raw_name: str) -> Path:
    return BASE / normalize_slug(raw_name)


def create_case(raw_name: str) -> Path:
    directory = case_dir(raw_name)
    (directory / "evidence").mkdir(parents=True, exist_ok=True)
    (directory / "output").mkdir(parents=True, exist_ok=True)
    metadata = directory / "case.json"
    if not metadata.exists():
        write_json_atomic(
            metadata,
            {"name": directory.name, "status": "open", "created": utc_timestamp()},
        )
        (directory / "notes.md").touch()
        (directory / "tasks.md").touch()
    return directory


def require_case(raw_name: str) -> Path:
    directory = case_dir(raw_name)
    if not (directory / "case.json").is_file():
        raise FileNotFoundError(f"Case not found: {directory.name}")
    return directory


def read_case_metadata(directory: Path) -> dict[str, object]:
    metadata_path = directory / "case.json"
    metadata = read_json(metadata_path, None)
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid case metadata: {metadata_path}")
    return metadata


def append_entry(raw_name: str, kind: str, text: str) -> None:
    directory = require_case(raw_name)
    filename = "notes.md" if kind == "note" else "tasks.md"
    with (directory / filename).open("a", encoding="utf-8") as handle:
        handle.write(f"- {utc_timestamp()} {text}\n")


def case_status(raw_name: str) -> dict[str, object]:
    directory = require_case(raw_name)
    metadata = read_case_metadata(directory)
    notes = (directory / "notes.md").read_text(encoding="utf-8", errors="replace").splitlines()
    tasks = (directory / "tasks.md").read_text(encoding="utf-8", errors="replace").splitlines()
    evidence = sum(1 for path in (directory / "evidence").rglob("*") if path.is_file())
    return {
        "case": metadata,
        "notes": len(notes),
        "tasks": len(tasks),
        "evidence_files": evidence,
    }


def close_case(raw_name: str) -> None:
    directory = require_case(raw_name)
    metadata_path = directory / "case.json"
    metadata = read_case_metadata(directory)
    metadata["status"] = "closed"
    metadata["closed"] = utc_timestamp()
    write_json_atomic(metadata_path, metadata)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sec research", description="Manage persistent research cases.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new = subparsers.add_parser("new")
    new.add_argument("name")

    for command in ("note", "task"):
        item = subparsers.add_parser(command)
        item.add_argument("name")
        item.add_argument("text", nargs="+")

    status = subparsers.add_parser("status")
    status.add_argument("name")

    subparsers.add_parser("list")

    close = subparsers.add_parser("close")
    close.add_argument("name")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "new":
            print(create_case(args.name))
        elif args.command in {"note", "task"}:
            append_entry(args.name, args.command, " ".join(args.text))
        elif args.command == "status":
            print(json.dumps(case_status(args.name), indent=2, sort_keys=True))
        elif args.command == "list":
            for directory in sorted(
                path for path in BASE.iterdir() if path.is_dir() and not path.name.startswith(".")
            ):
                print(directory.name)
        elif args.command == "close":
            close_case(args.name)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
