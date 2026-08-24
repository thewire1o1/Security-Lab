from __future__ import annotations

from typing import Any

from .github_actions import auth_status as github_actions_auth_status
from .github_actions import publish_project as publish_github_project
from .github_actions import repository_binding
from .jobs import list_jobs, refresh_job, refresh_pending_jobs, run_job
from .mobile import MOBILE_PROFILES, init_mobile_project, refresh_mobile_build_files
from .models import Profile, Project
from .profiles import get_profile, load_profiles
from .registry import delete_managed_project, get_project, list_projects
from .runners import RUNNERS
from .scaffold import init_project

EXTERNAL_RUNNERS = ("codespace", "github-actions")
MAX_STRUCTURED_JOB_TIMEOUT = 3600


def profile_row(profile: Profile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "title": profile.title,
        "category": profile.category,
        "description": profile.description,
        "runner": profile.runner,
        "stack": list(profile.stack),
        "capabilities": list(profile.capabilities),
        "commands": sorted(profile.commands),
        "services": profile.services,
        "scaffold": profile.scaffold,
    }


def project_row(project: Project) -> dict[str, Any]:
    binding = repository_binding(project)
    return {
        "name": project.name,
        "path": str(project.path),
        "profile": project.profile,
        "runner": project.runner,
        "commands": sorted(project.commands),
        "services": project.services,
        "repository": binding["full_name"] or None,
        "branch": binding["branch"] if binding["full_name"] else None,
        "workflow": binding["workflow"] or None,
    }


def profiles() -> list[dict[str, Any]]:
    return [profile_row(profile) for profile in load_profiles().values()]


def projects() -> list[dict[str, Any]]:
    return [project_row(project) for project in list_projects()]


def jobs(limit: int = 50) -> list[dict[str, Any]]:
    return list_jobs(max(1, min(limit, 500)))


def runner_status() -> dict[str, Any]:
    return {
        "local": sorted(RUNNERS),
        "external": list(EXTERNAL_RUNNERS),
        "github_actions": github_actions_auth_status(),
    }


def snapshot(job_limit: int = 20) -> dict[str, Any]:
    refresh_pending_jobs(min(max(job_limit, 1), 20))
    profile_rows = profiles()
    project_rows = projects()
    job_rows = jobs(job_limit)
    return {
        "platform": "Digital Paragon",
        "profiles": profile_rows,
        "projects": project_rows,
        "jobs": job_rows,
        "counts": {
            "profiles": len(profile_rows),
            "projects": len(project_rows),
            "jobs": len(list_jobs(500)),
        },
        "runners": runner_status(),
    }


def profile(name: str) -> dict[str, Any]:
    return profile_row(get_profile(name))


def project(name: str) -> dict[str, Any]:
    return project_row(get_project(name))


def create_project(name: str, profile_name: str) -> dict[str, Any]:
    if profile_name in MOBILE_PROFILES:
        return project_row(init_mobile_project(name, profile_name))
    return project_row(init_project(name, profile_name))


def refresh_project_template(name: str) -> dict[str, Any]:
    project_model = get_project(name)
    return project_row(refresh_mobile_build_files(project_model))


def publish_project(
    name: str,
    repository: str = "",
    visibility: str = "private",
) -> dict[str, Any]:
    return publish_github_project(get_project(name), repository, visibility)


def delete_project(name: str) -> dict[str, Any]:
    project_model = delete_managed_project(name)
    return {
        "ok": True,
        "name": project_model.name,
        "path": str(project_model.path),
        "profile": project_model.profile,
    }


def execute_job(project_name: str, command_name: str) -> dict[str, Any]:
    project_model = get_project(project_name)
    try:
        command = project_model.commands[command_name]
    except KeyError as exc:
        available = ", ".join(sorted(project_model.commands)) or "none"
        raise ValueError(
            f"Project '{project_name}' has no command '{command_name}'. Available: {available}"
        ) from exc
    if project_model.runner != "github-actions" and command.timeout > MAX_STRUCTURED_JOB_TIMEOUT:
        raise ValueError(
            f"Command '{command_name}' is long-running ({command.timeout}s) and is not eligible for synchronous MCP execution."
        )
    return run_job(project_name, command_name)


def job(job_id: str) -> dict[str, Any]:
    return refresh_job(job_id)
