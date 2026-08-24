from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import github_actions
from .github_actions import dispatch as dispatch_github_actions
from .github_actions import external_state, refresh as refresh_github_actions
from .paths import STATE_ROOT
from .registry import get_project
from .runners import get_runner

JOBS_ROOT = STATE_ROOT / "jobs"
VALID_STATES = {"queued", "running", "submitted", "succeeded", "failed"}
ACTIVE_STATES = {"queued", "running", "submitted"}
DISCOVERY_SKEW_SECONDS = 5
DISCOVERY_WINDOW_MINUTES = 15


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("External job is missing its dispatch timestamp.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("External job has an invalid dispatch timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def create_job(project: str, command: str, runner: str = "local") -> dict[str, Any]:
    job = {
        "id": f"job-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}",
        "project": project,
        "command": command,
        "runner": runner,
        "state": "queued",
        "created_at": _utc(),
        "started_at": None,
        "finished_at": None,
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "external": None,
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


def _claimed_external_run_ids(current_job_id: str) -> set[int]:
    claimed: set[int] = set()
    for row in list_jobs(500):
        if str(row.get("id") or "") == current_job_id:
            continue
        external = row.get("external")
        if not isinstance(external, dict):
            continue
        try:
            run_id = int(external.get("run_id") or 0)
        except (TypeError, ValueError):
            continue
        if run_id > 0:
            claimed.add(run_id)
    return claimed


def _discover_github_actions_run(job: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
    github_actions.require_auth()
    repository = github_actions._validate_repository(str(external.get("repository", "")))
    workflow = str(external.get("workflow") or "").strip()
    branch = str(external.get("ref") or "main").strip() or "main"
    if not workflow:
        raise ValueError("External job is missing its GitHub Actions workflow.")

    dispatched = _parse_utc(str(external.get("dispatched_at") or ""))
    lower = dispatched - timedelta(seconds=DISCOVERY_SKEW_SECONDS)
    upper = dispatched + timedelta(minutes=DISCOVERY_WINDOW_MINUTES)
    excluded = _claimed_external_run_ids(str(job.get("id") or ""))

    result = github_actions._gh(
        "run",
        "list",
        "--repo",
        repository,
        "--workflow",
        workflow,
        "--event",
        "workflow_dispatch",
        "--branch",
        branch,
        "--limit",
        "20",
        "--json",
        "databaseId,createdAt,status,conclusion,url",
        timeout=30,
    )
    if result["returncode"] != 0:
        raise ValueError(f"GitHub Actions run discovery failed: {github_actions._detail(result)}")
    try:
        rows = json.loads(result["stdout"] or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub Actions returned invalid run-list metadata.") from exc

    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            run_id = int(row.get("databaseId") or 0)
        except (TypeError, ValueError):
            continue
        if run_id <= 0 or run_id in excluded:
            continue
        try:
            created = _parse_utc(str(row.get("createdAt") or ""))
        except ValueError:
            continue
        if lower <= created <= upper:
            candidates.append((created, row))

    if not candidates:
        raise ValueError("Dispatched GitHub Actions run is not visible yet.")

    _created, row = min(candidates, key=lambda item: item[0])
    return {
        **external,
        "run_id": int(row.get("databaseId") or 0),
        "status": str(row.get("status") or external.get("status") or "submitted"),
        "conclusion": str(row.get("conclusion") or external.get("conclusion") or ""),
        "url": str(row.get("url") or external.get("url") or ""),
        "discovered_at": _utc(),
    }


def _finish_external(job: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
    state, returncode = external_state(external)
    job["external"] = external
    job["state"] = state
    job["returncode"] = returncode
    if state in {"succeeded", "failed"}:
        job["finished_at"] = _utc()
    _write(job)
    return job


def run_job(project_name: str, command_name: str) -> dict[str, Any]:
    project = get_project(project_name)
    try:
        command = project.commands[command_name]
    except KeyError as exc:
        available = ", ".join(sorted(project.commands)) or "none"
        raise ValueError(f"Project '{project_name}' has no command '{command_name}'. Available: {available}") from exc

    job = create_job(project_name, command_name, project.runner)
    job["state"] = "running"
    job["started_at"] = _utc()
    _write(job)

    if project.runner == "github-actions":
        try:
            external = dispatch_github_actions(project, command_name)
            job["state"] = "submitted"
            _write(job)
            return _finish_external(job, external)
        except Exception as exc:
            job["returncode"] = 1
            job["stderr"] = str(exc)
            job["state"] = "failed"
            job["finished_at"] = _utc()
            _write(job)
            return job

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


def refresh_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    external = job.get("external")
    if job.get("runner") != "github-actions" or not isinstance(external, dict):
        return job
    if job.get("state") not in ACTIVE_STATES:
        return job
    try:
        if int(external.get("run_id") or 0) <= 0:
            external = _discover_github_actions_run(job, external)
            job["external"] = external
            job["stderr"] = ""
            _write(job)
        refreshed = refresh_github_actions(external)
        job["stderr"] = ""
        return _finish_external(job, refreshed)
    except Exception as exc:
        job["stderr"] = str(exc)
        _write(job)
        return job


def refresh_pending_jobs(limit: int = 20) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    for job in list_jobs(max(1, min(limit, 100))):
        if job.get("runner") == "github-actions" and job.get("state") in ACTIVE_STATES:
            refreshed.append(refresh_job(str(job["id"])))
    return refreshed
