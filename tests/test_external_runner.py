from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security_lab.platform import github_actions, jobs, registry
from security_lab.platform.models import CommandSpec, Project, load_project_manifest


class GitHubActionsRunnerTests(unittest.TestCase):
    def test_auth_status_accepts_dedicated_repo_workflow_scopes(self) -> None:
        result = {
            "returncode": 0,
            "stdout": "",
            "stderr": "Logged in to github.com\n  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'\n",
        }
        with mock.patch.object(github_actions, "_gh", return_value=result):
            status = github_actions.auth_status()
        self.assertTrue(status["authenticated"])
        self.assertTrue(status["safe"])
        self.assertEqual(status["missing_scopes"], [])
        self.assertEqual(status["unexpected_scopes"], [])

    def test_auth_status_rejects_codespace_or_other_unexpected_scope(self) -> None:
        result = {
            "returncode": 0,
            "stdout": "",
            "stderr": "Logged in to github.com\n  - Token scopes: 'codespace', 'repo', 'workflow'\n",
        }
        with mock.patch.object(github_actions, "_gh", return_value=result):
            status = github_actions.auth_status()
        self.assertFalse(status["safe"])
        self.assertEqual(status["unexpected_scopes"], ["codespace"])

    def test_repository_table_roundtrip_is_structured_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "dpsr.toml").write_text(
                """
[project]
name = "demo"
profile = "ios"
[runner]
type = "github-actions"
[commands.build]
argv = ["xcodebuild", "build"]
cwd = "app"
timeout = 3600
""".strip() + "\n",
                encoding="utf-8",
            )
            github_actions._rewrite_repository_table(root, "octocat/demo", "main", "ios.yml")
            project = load_project_manifest(root)
        self.assertEqual(project.metadata["repository"]["full_name"], "octocat/demo")
        self.assertEqual(project.metadata["repository"]["branch"], "main")
        self.assertEqual(project.metadata["repository"]["workflow"], "ios.yml")

    def test_publish_refuses_unmanaged_project(self) -> None:
        project = Project(
            name="demo",
            path=Path("/tmp/unmanaged-dpsr-project"),
            profile="ios",
            runner="github-actions",
            commands={"build": CommandSpec(("xcodebuild", "build"), cwd="app")},
            services={},
            metadata={"repository": {}},
        )
        with mock.patch.object(github_actions, "PROJECTS_ROOT", Path("/workspaces/dpsr-projects")):
            with self.assertRaisesRegex(ValueError, "managed APOTHEON ONE projects"):
                github_actions.publish_project(project)

    def test_publish_creates_repo_binds_manifest_and_pushes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            managed = base / "managed"
            state = base / "state"
            root = managed / "demo-ios"
            (root / "app").mkdir(parents=True)
            (root / "dpsr.toml").write_text(
                """
[project]
name = "demo-ios"
profile = "ios"
[runner]
type = "github-actions"
[commands.build]
argv = ["xcodebuild", "build"]
cwd = "app"
timeout = 3600
""".strip() + "\n",
                encoding="utf-8",
            )
            project = load_project_manifest(root)
            with (
                mock.patch.object(github_actions, "PROJECTS_ROOT", managed),
                mock.patch.object(github_actions, "require_auth", return_value={"safe": True}),
                mock.patch.object(github_actions, "_authenticated_owner", return_value="octocat"),
                mock.patch.object(github_actions, "_repo_exists", return_value=False),
                mock.patch.object(github_actions, "_gh", return_value={"returncode": 0, "stdout": "", "stderr": ""}) as gh_mock,
                mock.patch.object(github_actions, "_ensure_git_repository") as push_mock,
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
            ):
                published = github_actions.publish_project(project)

            self.assertEqual(published["repository"], "octocat/demo-ios")
            self.assertTrue(published["created_repository"])
            rebound = load_project_manifest(root)
            self.assertEqual(rebound.metadata["repository"]["workflow"], "ios.yml")
            push_mock.assert_called_once()
            self.assertEqual(gh_mock.call_args.args[:3], ("repo", "create", "octocat/demo-ios"))

    def test_dispatch_records_remote_run_identity_through_rest_api(self) -> None:
        project = Project(
            name="demo",
            path=Path("/tmp/demo"),
            profile="android",
            runner="github-actions",
            commands={"build": CommandSpec(("./gradlew", "assembleDebug"), cwd="app")},
            services={},
            metadata={
                "repository": {
                    "full_name": "octocat/demo",
                    "branch": "main",
                    "workflow": "android.yml",
                }
            },
        )
        workflow_runs = json.dumps({
            "workflow_runs": [
                {
                    "id": 12345,
                    "created_at": "2026-08-24T08:00:00Z",
                    "status": "queued",
                    "conclusion": None,
                    "html_url": "https://github.com/octocat/demo/actions/runs/12345",
                }
            ]
        })
        responses = [
            {"returncode": 0, "stdout": "", "stderr": ""},
            {"returncode": 0, "stdout": workflow_runs, "stderr": ""},
        ]
        with (
            mock.patch.object(github_actions, "require_auth", return_value={"safe": True}),
            mock.patch.object(github_actions, "_utc", return_value="2026-08-24T08:00:00Z"),
            mock.patch.object(github_actions, "_gh", side_effect=responses) as gh_mock,
        ):
            external = github_actions.dispatch(project, "build")
        self.assertEqual(external["provider"], "github-actions")
        self.assertEqual(external["run_id"], 12345)
        self.assertEqual(external["workflow"], "android.yml")
        self.assertEqual(external["status"], "queued")
        self.assertEqual(gh_mock.call_args_list[1].args[0], "api")
        self.assertIn("event=workflow_dispatch", gh_mock.call_args_list[1].args[1])

    def test_external_job_dispatch_and_refresh_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            state = base / "state"
            (root / "app").mkdir(parents=True)
            (root / "dpsr.toml").write_text(
                """
[project]
name = "remote-demo"
profile = "ios"
[runner]
type = "github-actions"
[repository]
full_name = "octocat/remote-demo"
branch = "main"
workflow = "ios.yml"
[commands.build]
argv = ["xcodebuild", "build"]
cwd = "app"
timeout = 3600
""".strip() + "\n",
                encoding="utf-8",
            )
            external = {
                "provider": "github-actions",
                "repository": "octocat/remote-demo",
                "workflow": "ios.yml",
                "ref": "main",
                "command": "build",
                "run_id": 44,
                "url": "https://github.com/octocat/remote-demo/actions/runs/44",
                "status": "queued",
            }
            completed = {**external, "status": "completed", "conclusion": "success"}
            with (
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
                mock.patch.object(jobs, "STATE_ROOT", state),
                mock.patch.object(jobs, "JOBS_ROOT", state / "jobs"),
                mock.patch.object(jobs, "dispatch_github_actions", return_value=external),
                mock.patch.object(jobs, "refresh_github_actions", return_value=completed),
            ):
                registry.register_project(root)
                job = jobs.run_job("remote-demo", "build")
                self.assertEqual(job["state"], "running")
                self.assertEqual(job["runner"], "github-actions")
                self.assertEqual(job["external"]["run_id"], 44)
                refreshed = jobs.refresh_job(job["id"])

            self.assertEqual(refreshed["state"], "succeeded")
            self.assertEqual(refreshed["returncode"], 0)
            self.assertIsNotNone(refreshed["finished_at"])


if __name__ == "__main__":
    unittest.main()
