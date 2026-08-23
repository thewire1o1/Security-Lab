from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from security_lab.common import write_json_atomic


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize(sample: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stat = sample.stat()
    digest = sha256_file(sample)
    (output_dir / "sha256.txt").write_text(f"{digest}  {sample}\n", encoding="utf-8")
    summary = {
        "name": sample.name,
        "size": stat.st_size,
        "sha256": digest,
        "artifacts": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
    }
    write_json_atomic(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize static triage artifacts.")
    parser.add_argument("sample", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = summarize(args.sample.resolve(strict=True), args.output_dir.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
