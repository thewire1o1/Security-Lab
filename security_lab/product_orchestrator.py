from __future__ import annotations

import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from security_lab import dashboard as base
from security_lab import orchestrator as core
from security_lab.platform import guided_jobs
from security_lab.platform import api as platform_api

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_.-]+")


def _project_metadata(name: str, argv: tuple[str, ...]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if name.startswith("project-init:"):
        project_name = name.split(":", 1)[1] or "project"
        profile = "project"
        if "--profile" in argv:
            index = argv.index("--profile")
            if index + 1 < len(argv):
                profile = argv[index + 1]
        metadata = {
            "title": f"Creating {project_name}",
            "target_label": project_name,
            "description": "Set up the project structure and the automation it needs.",
            "action": name,
            "project": project_name,
            "project_profile": profile,
        }
        return metadata, [
            {
                "id": "execute",
                "title": "Create project",
                "detail": "Create the project files and register them in your APOTHEON workspace.",
                "state": "pending",
            }
        ]

    if name.startswith("project-publish:"):
        project_name = name.split(":", 1)[1] or "project"
        metadata = {
            "title": f"Saving {project_name} to GitHub",
            "target_label": project_name,
            "description": "Create or update the project's private GitHub repository.",
            "action": name,
            "project": project_name,
        }
        return metadata, [
            {
                "id": "execute",
                "title": "Save project",
                "detail": "Back up the project and its automation to a private GitHub repository.",
                "state": "pending",
            }
        ]

    if name.startswith("job:"):
        parts = name.split(":", 2)
        project_name = parts[1] if len(parts) > 1 and parts[1] else "project"
        command = parts[2] if len(parts) > 2 and parts[2] else "action"
        try:
            project = platform_api.project(project_name)
            profile = str(project.get("profile") or "project")
        except ValueError:
            profile = "project"
        if command == "build":
            action_title = "Build app" if profile in {"android", "ios", "flutter", "react-native"} else "Build project"
            description = "Create the runnable output for this project."
        elif command == "test":
            action_title = "Test project"
            description = "Run automated checks to make sure the project behaves as expected."
        elif command == "lint":
            action_title = "Check project quality"
            description = "Look for code problems before they become bugs."
        elif command in {"dev", "start"}:
            action_title = "Start preview"
            description = "Start the project so it can be viewed and tried."
        else:
            action_title = command.replace("-", " ").replace("_", " ").title() or "Run project action"
            description = f"Run the {action_title.lower()} automation for this project."
        metadata = {
            "title": f"{action_title}: {project_name}",
            "target_label": project_name,
            "description": description,
            "action": name,
            "project": project_name,
            "project_profile": profile,
            "command": command,
        }
        return metadata, [
            {
                "id": "prepare",
                "title": "Prepare project",
                "detail": "Make sure the project files, private cloud workspace, and automation are ready.",
                "state": "pending",
            },
            {
                "id": "execute",
                "title": action_title,
                "detail": description,
                "state": "pending",
            },
            {
                "id": "finish",
                "title": "Collect result",
                "detail": "Organize the result and any downloadable output.",
                "state": "pending",
            },
        ]

    return core._generic_metadata(name), [
        {
            "id": "execute",
            "title": core._generic_metadata(name)["title"],
            "detail": core._generic_metadata(name)["description"],
            "state": "pending",
        }
    ]


class ProductActionManager(core.OrchestratorActionManager):
    def submit(self, name: str, argv: tuple[str, ...]) -> bool:
        metadata, stages = _project_metadata(name, argv)
        return self.submit_run(name, argv, metadata, stages)

    def _recalculate_progress_locked(self) -> None:
        if self._run is None:
            return
        stages = self._run.get("stages", [])
        if not stages:
            self._run["progress"] = 0
            return
        consumed = sum(stage.get("state") in {"completed", "skipped", "failed"} for stage in stages)
        running = any(stage.get("state") == "running" for stage in stages)
        value = (consumed + (0.45 if running else 0.0)) / len(stages) * 100
        if self._run.get("state") == "succeeded":
            value = 100
        elif self._run.get("state") == "failed":
            value = min(95, value)
        self._run["progress"] = max(0, min(100, round(value)))

    def _worker_run(self, name: str, argv: tuple[str, ...]) -> None:
        super()._worker_run(name, argv)
        with self._run_lock:
            if self._run is None:
                return
            if self._run.get("state") == "succeeded":
                self._run["summary"] = "The requested action completed successfully."
            else:
                self._run["summary"] = "The requested action needs attention."
            self._recalculate_progress_locked()


class ProductDashboardState(core.OrchestratorDashboardState):
    pass


class ProductHandler(core.OrchestratorHandler):
    actions: ProductActionManager

    def _send_artifact(self, path: Path) -> None:
        filename = SAFE_FILENAME.sub("-", path.name).strip(".-") or "apotheon-output"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "private, no-store")
        self.end_headers()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/job-artifact":
            super().do_GET()
            return
        query = parse_qs(parsed.query, keep_blank_values=False)
        job_id = str((query.get("job") or [""])[0]).strip()
        artifact = str((query.get("artifact") or [""])[0]).strip()
        if not job_id or not artifact:
            self.send_json({"error": "job and artifact are required"}, 400)
            return
        try:
            path = guided_jobs.materialize_artifact(job_id, artifact)
            self._send_artifact(path)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 404)


def main() -> int:
    base.ActionManager = ProductActionManager
    base.DashboardState = ProductDashboardState
    base.Handler = ProductHandler
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
