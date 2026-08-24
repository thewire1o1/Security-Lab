from __future__ import annotations

from typing import Any

from .jobs import get_job, list_jobs, run_job
from .models import Profile, Project
from .profiles import get_profile, load_profiles
from .registry import get_project, list_projects
from .runners import RUNNERS
from .scaffold import init_project

EXTERNAL_RUNNERS = ("codespace", "github-actions")


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
    return {
        "name": project.name,
        "path": str(project.path),
        "profile": project.profile,
        "runner": project.runner,
        "commands": sorted(project.commands),
        "services": project.services,
    }


def profiles() -> list[dict[str, Any]]:
    return [profile_row(profile) for profile in load_profiles().values()]


def projects() -> list[dict[str, Any]]:
    return [project_row(project) for project in list_projects()]


def jobs(limit: int = 50) -> list[dict[str, Any]]:
    return list_jobs(max(1, min(limit, 500)))


def snapshot(job_limit: int = 20) -> dict[str, Any]:
    profile_rows = profiles()
    project_rows = projects()
    job_rows = jobs(job_limit)
    return {
        "platform": "dpsr-v2",
        "profiles": profile_rows,
        "projects": project_rows,
        "jobs": job_rows,
        "counts": {
            "profiles": len(profile_rows),
            "projects": len(project_rows),
            "jobs": len(list_jobs(500)),
        },
        "runners": {
            "local": sorted(RUNNERS),
            "external": list(EXTERNAL_RUNNERS),
        },
    }


def profile(name: str) -> dict[str, Any]:
    return profile_row(get_profile(name))


def project(name: str) -> dict[str, Any]:
    return project_row(get_project(name))


def create_project(name: str, profile_name: str) -> dict[str, Any]:
    return project_row(init_project(name, profile_name))


def execute_job(project_name: str, command_name: str) -> dict[str, Any]:
    return run_job(project_name, command_name)


def job(job_id: str) -> dict[str, Any]:
    return get_job(job_id)
