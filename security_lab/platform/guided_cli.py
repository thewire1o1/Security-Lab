from __future__ import annotations

import argparse
import json
import time

from . import guided_jobs
from . import jobs as base_jobs
from .registry import get_project

ACTIVE_STATES = {"queued", "running", "submitted"}


def _stage(stage_id: str, state: str, title: str, detail: str) -> None:
    print(f"APOTHEON_STAGE|{stage_id}|{state}|{title}|{detail}", flush=True)


def _command_copy(project_profile: str, command: str) -> tuple[str, str]:
    if command == "build":
        if project_profile in {"android", "ios", "flutter", "react-native"}:
            return "Build app", "Create the runnable or installable app package."
        return "Build project", "Create the runnable output for this project."
    if command == "test":
        return "Test project", "Run automated checks to make sure the project behaves as expected."
    if command == "lint":
        return "Check project quality", "Look for code problems before they become bugs."
    if command in {"dev", "start"}:
        return "Start preview", "Start the project so it can be viewed and tried."
    if command == "deploy":
        return "Publish project", "Prepare or send the project to its configured destination."
    if command == "scan":
        return "Check project security", "Check the project for security problems."
    if command == "review":
        return "Review project", "Review the project and summarize anything that needs attention."
    label = command.replace("-", " ").replace("_", " ").strip().title() or "Run project action"
    return label, f"Run the {label.lower()} automation for this project."


def _run(project_name: str, command_name: str) -> int:
    project = get_project(project_name)
    if command_name not in project.commands:
        available = ", ".join(sorted(project.commands)) or "none"
        raise ValueError(
            f"Project '{project_name}' has no command '{command_name}'. Available: {available}"
        )

    title, detail = _command_copy(project.profile, command_name)
    _stage(
        "prepare",
        "running",
        "Prepare project",
        "Make sure the project files, private cloud workspace, and automation are ready.",
    )
    prepared = guided_jobs.prepare_project(project_name, command_name)
    _stage(
        "prepare",
        "completed",
        "Project ready",
        "The project and its automation are ready for this action.",
    )

    _stage("execute", "running", title, detail)
    job = base_jobs.run_job(prepared.name, command_name)
    timeout = max(60, int(prepared.commands[command_name].timeout) + 120)
    deadline = time.monotonic() + timeout

    while str(job.get("state") or "") in ACTIVE_STATES:
        if time.monotonic() >= deadline:
            _stage(
                "execute",
                "failed",
                title,
                "The automation did not report a final result before the allowed time expired.",
            )
            _stage(
                "finish",
                "failed",
                "Result needs attention",
                "The remote task may still be running, but APOTHEON could not confirm a final result in time.",
            )
            print(json.dumps(job, indent=2, sort_keys=True), flush=True)
            return 1
        time.sleep(3)
        job = guided_jobs.refresh_job(str(job["id"]))

    if job.get("state") != "succeeded":
        _stage(
            "execute",
            "failed",
            title,
            "The requested action stopped before it completed successfully.",
        )
        _stage(
            "finish",
            "failed",
            "Result needs attention",
            "APOTHEON saved the failure details so the problem can be reviewed and corrected.",
        )
        print(json.dumps(job, indent=2, sort_keys=True), flush=True)
        return 1

    _stage("execute", "completed", title, "The requested project action completed successfully.")
    job = guided_jobs.refresh_job(str(job["id"]))
    artifacts = job.get("artifacts") or []
    finish_detail = (
        f"The result is ready with {len(artifacts)} downloadable build output{'s' if len(artifacts) != 1 else ''}."
        if artifacts
        else "The result is saved in project history and is ready to review."
    )
    _stage("finish", "running", "Collect result", "Organize the result and any downloadable output.")
    _stage("finish", "completed", "Result ready", finish_detail)
    print(json.dumps(job, indent=2, sort_keys=True), flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APOTHEON ONE guided project automation")
    sub = parser.add_subparsers(dest="job_command", required=True)
    job_list = sub.add_parser("list")
    job_list.add_argument("--limit", type=int, default=50)
    job_show = sub.add_parser("show")
    job_show.add_argument("id")
    job_refresh = sub.add_parser("refresh")
    job_refresh.add_argument("id")
    job_run = sub.add_parser("run")
    job_run.add_argument("project")
    job_run.add_argument("command_name")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.job_command == "list":
            print(json.dumps(guided_jobs.list_jobs(args.limit), indent=2, sort_keys=True))
            return 0
        if args.job_command in {"show", "refresh"}:
            print(json.dumps(guided_jobs.refresh_job(args.id), indent=2, sort_keys=True))
            return 0
        return _run(args.project, args.command_name)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"dpsr: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
