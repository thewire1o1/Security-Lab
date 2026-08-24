from __future__ import annotations

import argparse
import json
from pathlib import Path

from security_lab.common import read_json, write_json_atomic


def summarize(output_dir: Path) -> dict[str, object]:
    targets: dict[str, int] = {}
    for path in sorted(output_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        data = read_json(path, None)
        if not isinstance(data, dict) or "results" not in data:
            continue
        results = data.get("results") or []
        targets[path.stem] = len(results) if isinstance(results, list) else 0

    summary = {
        "targets": targets,
        "total_results": sum(targets.values()),
        "harness_logs": sum(1 for path in output_dir.glob("harness-*.log") if path.is_file()),
    }
    write_json_atomic(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize bounded fuzzing results.")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = summarize(args.output_dir.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
