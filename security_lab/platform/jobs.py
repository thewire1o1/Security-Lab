from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import STATE_ROOT
from .registry import get_project
from .runners import get_runner

JOBS_ROOT = STATE_ROOT / "jobs"
VALID_STATES = {"queued", "running", "succeeded", "failed"}


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _job_path(job_id: str) -> Path:
    if not job_id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in job_id.lower()):
        raise ValueError("Invalid job id.")
    return JOBS_ROOT / f"{job_id}.json"


def _write(job: dict[str, Any]) -> None:
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    path = _job_path(str(job["id"]))
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def create_job(project: str, command: str) -> dict[str, Any]:
    job = {
        "id": f"job-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}",
        "project": project,
        "command": command,
        "state": "queued",
        "created_at": _utc(),
        "started_at": None,
        "finished_at": None,
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }
    _write(job)
    return job


def get_job(job_id: str) -> dict[str, Any]:
    path = _job_path(job_id)
    if not path.exists():
        raise ValueError(f"Unknown job: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    if not JOBS_ROOT.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(JOBS_ROOT.glob("job-*.json"), reverse=True)[: max(1, min(limit, 500))]:
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def run_job(project_name: str, command_name: str) -> dict[str, Any]:
    project = get_project(project_name)
    try:
        command = project.commands[command_name]
    except KeyError as exc:
        available = ", ".join(sorted(project.commands)) or "none"
        raise ValueError(f"Project '{project_name}' has no command '{command_name}'. Available: {available}") from exc

    job = create_job(project_name, command_name)
    job["state"] = "running"
    job["started_at"] = _utc()
    _write(job)

    try:
        result = get_runner(project.runner).run(project, command)
        job["returncode"] = result.returncode
        job["stdout"] = result.stdout[-200_000:]
        job["stderr"] = result.stderr[-200_000:]
        job["state"] = "succeeded" if result.ok else "failed"
    except Exception as exc:
        job["returncode"] = 1
        job["stderr"] = str(exc)
        job["state"] = "failed"
    job["finished_at"] = _utc()
    _write(job)
    return job
