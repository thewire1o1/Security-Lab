from __future__ import annotations

import json
import os
import subprocess  # nosec B404
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SEVERITIES = ("critical", "high", "medium", "low", "info")


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def timestamp_slug() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path = ROOT,
    timeout: float | None = 15,
    stdout_limit: int = 12_000,
    stderr_limit: int = 6_000,
) -> dict[str, Any]:
    command = [str(part) for part in argv]
    try:
        completed = subprocess.run(  # nosec B603
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-stdout_limit:],
            "stderr": completed.stderr[-stderr_limit:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": command,
            "returncode": 124,
            "stdout": stdout[-stdout_limit:],
            "stderr": (stderr + f"\nTimed out after {timeout} seconds.").strip()[-stderr_limit:],
        }
    except OSError as exc:
        return {
            "command": command,
            "returncode": 126,
            "stdout": "",
            "stderr": str(exc)[-stderr_limit:],
        }


def newest_directories(base: Path, pattern: str) -> list[Path]:
    if not base.exists():
        return []
    directories = [path for path in base.glob(pattern) if path.is_dir()]
    return sorted(directories, key=lambda path: path.stat().st_mtime, reverse=True)
