from __future__ import annotations

import argparse
import json
from pathlib import Path

from security_lab.common import ROOT

from .github_actions import auth_status as github_actions_auth_status
from .github_actions import publish_project as publish_github_project
from .github_actions import repository_binding
from .jobs import list_jobs, refresh_job, run_job
from .mobile import MOBILE_PROFILES, init_mobile_project, refresh_mobile_build_files
from .profiles import get_profile, load_profiles
from .registry import delete_managed_project, get_project, list_projects, register_project, unregister_project
from .runners import RUNNERS
from .scaffold import init_project


def _project_row(project) -> dict[str, object]:
    binding = repository_binding(project)
    return {
        "name": project.name,
        "profile": project.profile,
        "runner": project.runner,
        "path": str(project.path),
        "commands": sorted(project.commands),
        "services": project.services,
        "repository": binding["full_name"] or None,
        "branch": binding["branch"] if binding["full_name"] else None,
        "workflow": binding["workflow"] or None,
    }


def cmd_status(_args: argparse.Namespace) -> int:
    profiles = load_profiles()
    projects = list_projects()
    payload = {
        "platform": "APOTHEON ONE",
        "root": str(ROOT),
        "profiles": len(profiles),
        "projects": len(projects),
        "runners": {
            "local": sorted(RUNNERS),
            "external": ["github-actions", "codespace"],
            "github_actions": github_actions_auth_status(),
        },
        "jobs": len(list_jobs(500)),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    profiles = load_profiles()
    if args.profile_command == "list":
        for profile in profiles.values():
            stack = ", ".join(profile.stack)
            print(f"{profile.name}\t{profile.category}\t{profile.runner}\t{stack}")
        return 0
    profile = get_profile(args.name)
    print(json.dumps({
        "name": profile.name,
        "title": profile.title,
        "category": profile.category,
        "description": profile.description,
        "runner": profile.runner,
        "stack": profile.stack,
        "capabilities": profile.capabilities,
        "commands": sorted(profile.commands),
        "services": profile.services,
        "scaffold": profile.scaffold,
    }, indent=2, sort_keys=True))
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    action = args.project_command
    if action == "list":
        print(json.dumps([_project_row(row) for row in list_projects()], indent=2, sort_keys=True))
        return 0
    if action == "show":
        print(json.dumps(_project_row(get_project(args.name)), indent=2, sort_keys=True))
        return 0
    if action == "register":
        project = register_project(Path(args.path))
        print(json.dumps(_project_row(project), indent=2, sort_keys=True))
        return 0
    if action == "remove":
        if not unregister_project(args.name):
            raise ValueError(f"Unknown project: {args.name}")
        print(f"Removed project registry entry: {args.name}")
        return 0
    if action == "delete":
        project = delete_managed_project(args.name)
        print(json.dumps({
            "deleted": True,
            "name": project.name,
            "path": str(project.path),
            "profile": project.profile,
        }, indent=2, sort_keys=True))
        return 0
    if action == "init":
        target = Path(args.path).expanduser() if args.path else None
        if args.profile in MOBILE_PROFILES:
            project = init_mobile_project(args.name, args.profile, target)
        else:
            project = init_project(args.name, args.profile, target)
        print(json.dumps(_project_row(project), indent=2, sort_keys=True))
        return 0
    if action == "refresh-template":
        project = refresh_mobile_build_files(get_project(args.name))
        print(json.dumps(_project_row(project), indent=2, sort_keys=True))
        return 0
    if action == "publish":
        project = get_project(args.name)
        result = publish_github_project(project, args.repo or "", args.visibility)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if action == "verify":
        project = get_project(args.name)
        if project.runner not in RUNNERS:
            raise ValueError(
                f"Project '{args.name}' uses external runner '{project.runner}'; publish it and use `dpsr job run` to dispatch its remote workflow."
            )
        selected = [name for name in ("lint", "test", "build") if name in project.commands]
        if not selected:
            raise ValueError(f"Project '{args.name}' defines none of lint, test, or build.")
        failed = False
        for name in selected:
            job = run_job(args.name, name)
            print(f"{job['id']}\t{name}\t{job['state']}")
            failed = failed or job["state"] != "succeeded"
        return 1 if failed else 0
    raise ValueError(f"Unsupported project action: {action}")


def cmd_job(args: argparse.Namespace) -> int:
    if args.job_command == "list":
        print(json.dumps(list_jobs(args.limit), indent=2, sort_keys=True))
        return 0
    if args.job_command in {"show", "refresh"}:
        print(json.dumps(refresh_job(args.id), indent=2, sort_keys=True))
        return 0
    job = run_job(args.project, args.command_name)
    print(json.dumps(job, indent=2, sort_keys=True))
    return 1 if job["state"] == "failed" else 0


def cmd_runner(args: argparse.Namespace) -> int:
    if args.runner_command == "list":
        for name in sorted(RUNNERS):
            print(name)
        print("github-actions\texternal")
        print("codespace\texternal")
        return 0
    if args.runner_command == "status":
        print(json.dumps({
            "local": sorted(RUNNERS),
            "github_actions": github_actions_auth_status(),
        }, indent=2, sort_keys=True))
        return 0
    raise ValueError(f"Unsupported runner action: {args.runner_command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APOTHEON ONE development platform control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("list")
    profile_show = profile_sub.add_parser("show")
    profile_show.add_argument("name")

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_sub.add_parser("list")
    project_show = project_sub.add_parser("show")
    project_show.add_argument("name")
    project_register = project_sub.add_parser("register")
    project_register.add_argument("path")
    project_remove = project_sub.add_parser("remove")
    project_remove.add_argument("name")
    project_delete = project_sub.add_parser("delete")
    project_delete.add_argument("name")
    project_init = project_sub.add_parser("init")
    project_init.add_argument("name")
    project_init.add_argument("--profile", required=True)
    project_init.add_argument("--path")
    project_refresh = project_sub.add_parser("refresh-template")
    project_refresh.add_argument("name")
    project_publish = project_sub.add_parser("publish")
    project_publish.add_argument("name")
    project_publish.add_argument("--repo")
    project_publish.add_argument("--visibility", choices=("private", "public"), default="private")
    project_verify = project_sub.add_parser("verify")
    project_verify.add_argument("name")

    job = sub.add_parser("job")
    job_sub = job.add_subparsers(dest="job_command", required=True)
    job_list = job_sub.add_parser("list")
    job_list.add_argument("--limit", type=int, default=50)
    job_show = job_sub.add_parser("show")
    job_show.add_argument("id")
    job_refresh = job_sub.add_parser("refresh")
    job_refresh.add_argument("id")
    job_run = job_sub.add_parser("run")
    job_run.add_argument("project")
    job_run.add_argument("command_name")

    runner = sub.add_parser("runner")
    runner_sub = runner.add_subparsers(dest="runner_command", required=True)
    runner_sub.add_parser("list")
    runner_sub.add_parser("status")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "status":
            return cmd_status(args)
        if args.command == "profile":
            return cmd_profile(args)
        if args.command == "project":
            return cmd_project(args)
        if args.command == "job":
            return cmd_job(args)
        if args.command == "runner":
            return cmd_runner(args)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dpsr: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())