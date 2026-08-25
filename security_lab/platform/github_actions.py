from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from .models import Project
from .paths import PERSISTENT_ROOT, PROJECTS_ROOT
from .registry import register_project

RUNNER_GH_CONFIG = Path(
    os.environ.get("DPSR_RUNNER_GH_CONFIG", str(PERSISTENT_ROOT / ".dpsr" / "runner-gh"))
).expanduser()
RUNNER_GIT_CONFIG = Path(
    os.environ.get("DPSR_RUNNER_GIT_CONFIG", str(PERSISTENT_ROOT / ".dpsr" / "runner-gitconfig"))
).expanduser()
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
RUNTIME_REQUIRED_SCOPES = frozenset({"repo"})
PUBLISH_REQUIRED_SCOPES = frozenset({"repo", "workflow"})
ALLOWED_SCOPES = frozenset({"repo", "workflow", "read:org", "gist", "codespace"})
WORKFLOW_BY_PROFILE = {
    "flutter": "flutter.yml",
    "react-native": "react-native.yml",
    "android": "android.yml",
    "ios": "ios.yml",
}
ACTIVE_RUN_STATES = frozenset({"queued", "in_progress", "pending", "requested", "waiting"})
RUN_DISCOVERY_SKEW_SECONDS = 5
RUN_DISCOVERY_WINDOW_MINUTES = 15


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("Missing GitHub Actions dispatch timestamp.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("Invalid GitHub Actions timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _credential_source() -> tuple[str, str]:
    dedicated = os.environ.get("DPSR_RUNNER_GITHUB_TOKEN", "").strip()
    if dedicated:
        return dedicated, "runner-secret"
    bridge = os.environ.get("DPSR_BRIDGE_TOKEN", "").strip()
    if bridge:
        return bridge, "codespace-bridge"
    return "", "isolated-config"


def _runner_env() -> dict[str, str]:
    RUNNER_GH_CONFIG.mkdir(parents=True, exist_ok=True)
    os.chmod(RUNNER_GH_CONFIG, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    token, _source = _credential_source()
    if token:
        env["GH_TOKEN"] = token
    env["GH_CONFIG_DIR"] = str(RUNNER_GH_CONFIG)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GIT_CONFIG_GLOBAL"] = str(RUNNER_GIT_CONFIG)
    return env


def _run(
    argv: tuple[str, ...] | list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    completed = subprocess.run(  # nosec B603
        [str(item) for item in argv],
        cwd=cwd,
        env=_runner_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _gh(*args: str, cwd: Path | None = None, timeout: int = 120) -> dict[str, Any]:
    return _run(("gh", *args), cwd=cwd, timeout=timeout)


def _git(project: Project, *args: str, timeout: int = 120) -> dict[str, Any]:
    return _run(("git", "-C", str(project.path), *args), cwd=project.path, timeout=timeout)


def _detail(result: dict[str, Any]) -> str:
    return str(result.get("stderr") or result.get("stdout") or "no process output").strip()


def _require_ok(label: str, result: dict[str, Any]) -> dict[str, Any]:
    if int(result.get("returncode", 1)) != 0:
        raise ValueError(f"{label} failed: {_detail(result)}")
    return result


def _parse_scopes(text: str) -> set[str]:
    match = re.search(r"Token scopes:\s*(.+)", text, re.IGNORECASE)
    if not match:
        return set()
    return {item.strip(" '\"\t") for item in match.group(1).split(",") if item.strip(" '\"\t")}


def auth_status(required_scopes: Iterable[str] = RUNTIME_REQUIRED_SCOPES) -> dict[str, Any]:
    result = _gh("auth", "status", "--hostname", "github.com", timeout=20)
    output = "\n".join(part for part in (result["stdout"].strip(), result["stderr"].strip()) if part)
    scopes = _parse_scopes(output)
    required = frozenset(str(scope).strip() for scope in required_scopes if str(scope).strip())
    missing = sorted(required - scopes)
    unexpected = sorted(scopes - ALLOWED_SCOPES)
    authenticated = result["returncode"] == 0
    safe = authenticated and not missing and not unexpected
    _token, source = _credential_source()
    return {
        "authenticated": authenticated,
        "safe": safe,
        "scopes": sorted(scopes),
        "missing_scopes": missing,
        "unexpected_scopes": unexpected,
        "credential_source": source,
        "config_dir": str(RUNNER_GH_CONFIG),
    }


def require_auth(required_scopes: Iterable[str] = RUNTIME_REQUIRED_SCOPES) -> dict[str, Any]:
    status = auth_status(required_scopes)
    if not status["authenticated"]:
        raise ValueError("Dedicated GitHub Actions runner credential is not authorized.")
    if status["missing_scopes"]:
        raise ValueError(
            "Dedicated runner credential is missing required scopes: "
            + ", ".join(status["missing_scopes"])
        )
    if status["unexpected_scopes"]:
        raise ValueError(
            "Dedicated runner credential has unexpected scopes and was rejected: "
            + ", ".join(status["unexpected_scopes"])
        )
    return status


def _validate_repository(full_name: str) -> str:
    normalized = full_name.strip()
    if not REPOSITORY_PATTERN.fullmatch(normalized):
        raise ValueError("Repository must use owner/name format.")
    return normalized


def _managed_project(project: Project) -> None:
    try:
        project.path.resolve().relative_to(PROJECTS_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Repository publishing is limited to managed APOTHEON ONE projects.") from exc


def _repository_metadata(project: Project) -> dict[str, Any]:
    raw = project.metadata.get("repository") or {}
    return raw if isinstance(raw, dict) else {}


def repository_binding(project: Project) -> dict[str, str]:
    raw = _repository_metadata(project)
    full_name = str(raw.get("full_name", "")).strip()
    branch = str(raw.get("branch", "main")).strip() or "main"
    workflow = str(raw.get("workflow", "")).strip()
    if full_name:
        _validate_repository(full_name)
    return {"full_name": full_name, "branch": branch, "workflow": workflow}


def workflow_for(project: Project) -> str:
    binding = repository_binding(project)
    if binding["workflow"]:
        return binding["workflow"]
    try:
        return WORKFLOW_BY_PROFILE[project.profile]
    except KeyError as exc:
        raise ValueError(f"Profile '{project.profile}' has no GitHub Actions workflow mapping.") from exc


def _rewrite_repository_table(path: Path, full_name: str, branch: str, workflow: str) -> None:
    manifest = path / "dpsr.toml"
    text = manifest.read_text(encoding="utf-8")
    lines = text.splitlines()
    kept: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() == "[repository]":
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith("["):
                index += 1
            continue
        kept.append(lines[index])
        index += 1
    rendered = "\n".join(kept).rstrip() + "\n\n[repository]\n"
    rendered += f'full_name = "{full_name}"\n'
    rendered += f'branch = "{branch}"\n'
    rendered += f'workflow = "{workflow}"\n'
    manifest.write_text(rendered, encoding="utf-8")


def _authenticated_owner() -> str:
    result = _require_ok("GitHub account lookup", _gh("api", "user", "--jq", ".login", timeout=30))
    owner = result["stdout"].strip()
    if not owner or not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise ValueError("Unable to resolve the authenticated GitHub account.")
    return owner


def _repo_exists(full_name: str) -> bool:
    result = _gh("repo", "view", full_name, "--json", "nameWithOwner", timeout=30)
    if result["returncode"] == 0:
        return True
    detail = _detail(result).lower()
    if "could not resolve to a repository" in detail or "not found" in detail or "http 404" in detail:
        return False
    raise ValueError(f"GitHub repository lookup failed: {_detail(result)}")


def _setup_git_credential_helper() -> None:
    RUNNER_GIT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _require_ok(
        "GitHub git credential setup",
        _gh("auth", "setup-git", "--hostname", "github.com", timeout=30),
    )
    if RUNNER_GIT_CONFIG.exists():
        os.chmod(RUNNER_GIT_CONFIG, 0o600)


def _ensure_git_repository(project: Project, full_name: str, branch: str) -> None:
    new_repository = not (project.path / ".git").is_dir()
    if new_repository:
        _require_ok("git init", _git(project, "init", "-b", branch, timeout=30))

    remote = _git(project, "remote", "get-url", "origin", timeout=10)
    expected = f"https://github.com/{full_name}.git"
    if remote["returncode"] == 0:
        current = remote["stdout"].strip().removesuffix("/")
        accepted = {
            expected.removesuffix("/"),
            f"https://github.com/{full_name}".removesuffix("/"),
            f"git@github.com:{full_name}.git",
        }
        if current not in accepted:
            raise ValueError(f"Project origin points to a different repository: {current}")
    else:
        _require_ok("git remote add", _git(project, "remote", "add", "origin", expected, timeout=10))

    _require_ok("git add", _git(project, "add", "-A", timeout=60))
    staged = _git(project, "diff", "--cached", "--quiet", timeout=30)
    if staged["returncode"] == 1:
        commit = _git(
            project,
            "-c",
            "user.name=APOTHEON ONE",
            "-c",
            "user.email=apotheon-one@localhost",
            "commit",
            "-m",
            "Initialize APOTHEON ONE project" if new_repository else "Update APOTHEON ONE project",
            timeout=120,
        )
        _require_ok("git commit", commit)
    elif staged["returncode"] != 0:
        raise ValueError(f"git staged-change check failed: {_detail(staged)}")

    _setup_git_credential_helper()
    _require_ok("git push", _git(project, "push", "-u", "origin", branch, timeout=600))


def publish_project(
    project: Project,
    repository: str = "",
    visibility: str = "private",
) -> dict[str, Any]:
    _managed_project(project)
    require_auth(PUBLISH_REQUIRED_SCOPES)
    if visibility not in {"private", "public"}:
        raise ValueError("Repository visibility must be private or public.")
    owner = _authenticated_owner()
    full_name = _validate_repository(repository or f"{owner}/{project.name}")
    if full_name.split("/", 1)[0].lower() != owner.lower():
        raise ValueError("Automatic repository creation is limited to the authenticated account.")

    binding = repository_binding(project)
    branch = binding["branch"] or "main"
    workflow = workflow_for(project) if project.runner == "github-actions" else binding["workflow"]

    exists = _repo_exists(full_name)
    if not exists:
        create_args = ["repo", "create", full_name, f"--{visibility}", "--description", f"APOTHEON ONE project: {project.name}"]
        _require_ok("GitHub repository creation", _gh(*create_args, timeout=60))
    elif binding["full_name"] and binding["full_name"].lower() != full_name.lower():
        raise ValueError("Project is already bound to a different GitHub repository.")

    _rewrite_repository_table(project.path, full_name, branch, workflow)
    bound = register_project(project.path)
    _ensure_git_repository(bound, full_name, branch)
    return {
        "name": bound.name,
        "repository": full_name,
        "branch": branch,
        "workflow": workflow,
        "visibility": visibility,
        "created_repository": not exists,
        "published": True,
    }


def discover_dispatched_run(
    repository: str,
    workflow: str,
    branch: str,
    dispatched_at: str,
    exclude_run_ids: Iterable[int] = (),
) -> dict[str, Any] | None:
    full_name = _validate_repository(repository)
    dispatched = _parse_utc(dispatched_at)
    lower = dispatched - timedelta(seconds=RUN_DISCOVERY_SKEW_SECONDS)
    upper = dispatched + timedelta(minutes=RUN_DISCOVERY_WINDOW_MINUTES)
    excluded = {int(value) for value in exclude_run_ids if int(value) > 0}
    endpoint = (
        f"repos/{full_name}/actions/workflows/{quote(workflow, safe='')}/runs"
        f"?event=workflow_dispatch&branch={quote(branch, safe='')}&per_page=20"
    )
    result = _gh("api", endpoint, timeout=30)
    if result["returncode"] != 0:
        raise ValueError(f"GitHub Actions run discovery failed: {_detail(result)}")
    try:
        payload = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub Actions returned invalid run-list metadata.") from exc
    rows = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        try:
            run_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if run_id <= 0 or run_id in excluded:
            continue
        try:
            created = _parse_utc(str(row.get("created_at") or ""))
        except ValueError:
            continue
        if lower <= created <= upper:
            candidates.append((created, row))
    if not candidates:
        return None
    _created, row = min(candidates, key=lambda item: item[0])
    return {
        "run_id": int(row.get("id") or 0),
        "status": str(row.get("status") or "submitted"),
        "conclusion": str(row.get("conclusion") or ""),
        "url": str(row.get("html_url") or ""),
        "created_at": str(row.get("created_at") or ""),
    }


def dispatch(project: Project, command_name: str) -> dict[str, Any]:
    require_auth()
    binding = repository_binding(project)
    full_name = binding["full_name"]
    if not full_name:
        raise ValueError("Project is not published to a GitHub repository.")
    workflow = workflow_for(project)
    branch = binding["branch"] or "main"
    started = _utc()
    _require_ok(
        "GitHub Actions dispatch",
        _gh("workflow", "run", workflow, "--repo", full_name, "--ref", branch, timeout=60),
    )

    discovered: dict[str, Any] | None = None
    for _attempt in range(8):
        discovered = discover_dispatched_run(full_name, workflow, branch, started)
        if discovered is not None:
            break
        time.sleep(2)

    return {
        "provider": "github-actions",
        "repository": full_name,
        "workflow": workflow,
        "ref": branch,
        "command": command_name,
        "dispatched_at": started,
        "run_id": discovered["run_id"] if discovered else None,
        "url": discovered["url"] if discovered else "",
        "status": discovered["status"] if discovered else "submitted",
        "conclusion": discovered["conclusion"] if discovered else "",
    }


def refresh(external: dict[str, Any]) -> dict[str, Any]:
    require_auth()
    repository = _validate_repository(str(external.get("repository", "")))
    run_id = int(external.get("run_id") or 0)
    if run_id <= 0:
        raise ValueError("External job has no GitHub Actions run id.")
    result = _require_ok(
        "GitHub Actions run lookup",
        _gh(
            "run",
            "view",
            str(run_id),
            "--repo",
            repository,
            "--json",
            "databaseId,status,conclusion,url,createdAt,updatedAt,workflowName,headBranch",
            timeout=30,
        ),
    )
    try:
        row = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub Actions returned invalid run metadata.") from exc
    status = str(row.get("status") or "unknown")
    conclusion = str(row.get("conclusion") or "")
    return {
        **external,
        "run_id": int(row.get("databaseId") or run_id),
        "status": status,
        "conclusion": conclusion,
        "url": str(row.get("url") or external.get("url") or ""),
        "updated_at": str(row.get("updatedAt") or ""),
        "workflow_name": str(row.get("workflowName") or ""),
        "head_branch": str(row.get("headBranch") or ""),
    }


def external_state(external: dict[str, Any]) -> tuple[str, int | None]:
    status = str(external.get("status") or "").lower()
    conclusion = str(external.get("conclusion") or "").lower()
    if status in ACTIVE_RUN_STATES or status == "submitted":
        return "running", None
    if status == "completed":
        if conclusion == "success":
            return "succeeded", 0
        return "failed", 1
    return "running", None
