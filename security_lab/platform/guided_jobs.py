from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from . import github_actions
from . import jobs as base_jobs
from .mobile import MOBILE_PROFILES, refresh_mobile_build_files
from .models import Project
from .registry import get_project

UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _workflow_path(project: Project) -> Path | None:
    workflow = github_actions.WORKFLOW_BY_PROFILE.get(project.profile)
    if not workflow:
        return None
    return project.path / ".github" / "workflows" / workflow


def _append_step(path: Path, marker: str, text: str) -> None:
    current = path.read_text(encoding="utf-8")
    if marker in current:
        return
    path.write_text(current.rstrip() + "\n" + text.rstrip() + "\n", encoding="utf-8")


def _ensure_artifact_workflow(project: Project) -> None:
    path = _workflow_path(project)
    if path is None or not path.is_file():
        return

    if project.profile == "android":
        _append_step(
            path,
            "name: android-apk",
            f"""      - uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}
        with:
          name: android-apk
          path: app/app/build/outputs/apk/debug/*.apk
          if-no-files-found: error""",
        )
        return

    if project.profile == "react-native":
        _append_step(
            path,
            "name: react-native-android-apk",
            f"""      - uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}
        with:
          name: react-native-android-apk
          path: app/android/app/build/outputs/apk/debug/*.apk
          if-no-files-found: error""",
        )
        return

    if project.profile == "flutter":
        _append_step(
            path,
            "flutter build apk --debug",
            """      - run: flutter build apk --debug
        working-directory: app""",
        )
        _append_step(
            path,
            "name: flutter-android-apk",
            f"""      - uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}
        with:
          name: flutter-android-apk
          path: app/build/app/outputs/flutter-apk/app-debug.apk
          if-no-files-found: error""",
        )
        _append_step(
            path,
            "name: flutter-web",
            f"""      - uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}
        with:
          name: flutter-web
          path: app/build/web
          if-no-files-found: error""",
        )
        return

    if project.profile == "ios":
        current = path.read_text(encoding="utf-8")
        if "-derivedDataPath app/build" not in current:
            current = current.replace(
                "          -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO",
                "          -destination 'generic/platform=iOS Simulator' -derivedDataPath app/build build CODE_SIGNING_ALLOWED=NO",
            )
            path.write_text(current, encoding="utf-8")
        _append_step(
            path,
            "name: ios-simulator-app",
            f"""      - uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}
        with:
          name: ios-simulator-app
          path: app/build/Build/Products/Debug-iphonesimulator/*.app
          if-no-files-found: error""",
        )


def prepare_project(project_name: str, command_name: str) -> Project:
    project = get_project(project_name)
    if command_name not in project.commands:
        available = ", ".join(sorted(project.commands)) or "none"
        raise ValueError(
            f"Project '{project_name}' has no command '{command_name}'. Available: {available}"
        )

    if project.profile in MOBILE_PROFILES and command_name == "build":
        project = refresh_mobile_build_files(project)
        _ensure_artifact_workflow(project)

    if project.runner == "github-actions":
        binding = github_actions.repository_binding(project)
        needs_publish = not binding["full_name"]
        needs_push = project.profile in MOBILE_PROFILES and command_name == "build"
        if needs_publish or needs_push:
            github_actions.publish_project(
                project,
                binding["full_name"] if binding["full_name"] else "",
                "private",
            )
            project = get_project(project_name)

    return project


def run_job(project_name: str, command_name: str) -> dict[str, Any]:
    prepare_project(project_name, command_name)
    return base_jobs.run_job(project_name, command_name)


def _list_run_artifacts(external: dict[str, Any]) -> list[dict[str, Any]]:
    github_actions.require_auth()
    repository = github_actions._validate_repository(str(external.get("repository", "")))
    run_id = int(external.get("run_id") or 0)
    if run_id <= 0:
        return []
    result = github_actions._gh(
        "api",
        f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
        timeout=30,
    )
    if result["returncode"] != 0:
        raise ValueError(f"GitHub artifact lookup failed: {github_actions._detail(result)}")
    try:
        payload = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub returned invalid artifact metadata.") from exc

    rows: list[dict[str, Any]] = []
    for item in payload.get("artifacts", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict) or bool(item.get("expired")):
            continue
        artifact_id = int(item.get("id") or 0)
        name = str(item.get("name") or "").strip()
        if artifact_id <= 0 or not ARTIFACT_NAME.fullmatch(name):
            continue
        rows.append(
            {
                "id": artifact_id,
                "name": name,
                "size_in_bytes": int(item.get("size_in_bytes") or 0),
                "expired": False,
            }
        )
    return rows


def refresh_job(job_id: str) -> dict[str, Any]:
    job = base_jobs.refresh_job(job_id)
    external = job.get("external")
    if (
        job.get("state") == "succeeded"
        and isinstance(external, dict)
        and "artifacts" not in job
    ):
        try:
            job["artifacts"] = _list_run_artifacts(external)
            job["artifact_error"] = ""
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            job["artifacts"] = []
            job["artifact_error"] = str(exc)
        base_jobs._write(job)
    return job


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    rows = base_jobs.list_jobs(limit)
    refreshed: list[dict[str, Any]] = []
    for row in rows:
        if row.get("state") in base_jobs.ACTIVE_STATES:
            refreshed.append(refresh_job(str(row["id"])))
        else:
            refreshed.append(row)
    return refreshed


def materialize_artifact(job_id: str, artifact_name: str) -> Path:
    if not ARTIFACT_NAME.fullmatch(artifact_name):
        raise ValueError("Invalid artifact name.")
    job = refresh_job(job_id)
    artifacts = job.get("artifacts") or []
    artifact = next(
        (row for row in artifacts if isinstance(row, dict) and row.get("name") == artifact_name),
        None,
    )
    if artifact is None:
        raise ValueError("Requested build output is not available for this job.")
    external = job.get("external")
    if not isinstance(external, dict):
        raise ValueError("This build does not have an external artifact source.")

    repository = github_actions._validate_repository(str(external.get("repository", "")))
    run_id = int(external.get("run_id") or 0)
    if run_id <= 0:
        raise ValueError("This build is missing its remote run id.")

    root = base_jobs.STATE_ROOT / "artifacts" / job_id / artifact_name
    root.mkdir(parents=True, exist_ok=True)
    files = [path for path in root.rglob("*") if path.is_file()]
    if not files:
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        result = github_actions._gh(
            "run",
            "download",
            str(run_id),
            "--repo",
            repository,
            "--name",
            artifact_name,
            "--dir",
            str(root),
            timeout=600,
        )
        if result["returncode"] != 0:
            raise ValueError(f"Build output download failed: {github_actions._detail(result)}")
        files = [path for path in root.rglob("*") if path.is_file()]
    if not files:
        raise ValueError("The build output downloaded without any files.")

    direct_extensions = {".apk", ".aab", ".ipa", ".zip"}
    if len(files) == 1 and files[0].suffix.lower() in direct_extensions:
        return files[0]

    archive_base = root.parent / artifact_name
    archive = Path(str(archive_base) + ".zip")
    if not archive.is_file():
        shutil.make_archive(str(archive_base), "zip", root_dir=root)
    return archive
