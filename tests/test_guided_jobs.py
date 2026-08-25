from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security_lab.platform import guided_jobs
from security_lab.platform.models import CommandSpec, Project


class GuidedProjectJobTests(unittest.TestCase):
    def test_android_build_workflow_uploads_installable_apk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = root / ".github" / "workflows" / "android.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "jobs:\n  build:\n    steps:\n      - run: gradle assembleDebug\n",
                encoding="utf-8",
            )
            project = Project(
                name="demo",
                path=root,
                profile="android",
                runner="github-actions",
                commands={"build": CommandSpec(("gradle", "assembleDebug"), cwd="app")},
                services={},
                metadata={},
            )

            guided_jobs._ensure_artifact_workflow(project)
            text = workflow.read_text(encoding="utf-8")

        self.assertIn(f"actions/upload-artifact@{guided_jobs.UPLOAD_ARTIFACT_SHA}", text)
        self.assertIn("name: android-apk", text)
        self.assertIn("app/app/build/outputs/apk/debug/*.apk", text)
        self.assertNotIn("actions/upload-artifact@v4", text)

    def test_unbound_cloud_project_is_published_before_job(self) -> None:
        project = Project(
            name="demo",
            path=Path("/tmp/demo"),
            profile="nextjs",
            runner="github-actions",
            commands={"test": CommandSpec(("npm", "test"), cwd=".")},
            services={},
            metadata={},
        )
        with (
            mock.patch.object(guided_jobs, "get_project", side_effect=[project, project]),
            mock.patch.object(
                guided_jobs.github_actions,
                "repository_binding",
                return_value={"full_name": "", "branch": "main", "workflow": ""},
            ),
            mock.patch.object(guided_jobs.github_actions, "publish_project") as publish_mock,
        ):
            prepared = guided_jobs.prepare_project("demo", "test")

        publish_mock.assert_called_once_with(project, "", "private")
        self.assertEqual(prepared.name, "demo")

    def test_artifact_listing_filters_expired_and_invalid_entries(self) -> None:
        payload = json.dumps(
            {
                "artifacts": [
                    {"id": 1, "name": "android-apk", "size_in_bytes": 123, "expired": False},
                    {"id": 2, "name": "expired-apk", "size_in_bytes": 456, "expired": True},
                    {"id": 0, "name": "invalid", "size_in_bytes": 1, "expired": False},
                ]
            }
        )
        external = {"repository": "octocat/demo", "run_id": 99}
        with (
            mock.patch.object(guided_jobs.github_actions, "require_auth"),
            mock.patch.object(guided_jobs.github_actions, "_validate_repository", return_value="octocat/demo"),
            mock.patch.object(
                guided_jobs.github_actions,
                "_gh",
                return_value={"returncode": 0, "stdout": payload, "stderr": ""},
            ),
        ):
            rows = guided_jobs._list_run_artifacts(external)

        self.assertEqual(rows, [{"id": 1, "name": "android-apk", "size_in_bytes": 123, "expired": False}])

    def test_materialize_returns_downloaded_apk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            job = {
                "id": "job-demo",
                "state": "succeeded",
                "external": {"repository": "octocat/demo", "run_id": 77},
                "artifacts": [{"id": 5, "name": "android-apk", "size_in_bytes": 10, "expired": False}],
            }

            def fake_gh(*args, **_kwargs):
                directory = Path(args[args.index("--dir") + 1])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "demo-debug.apk").write_bytes(b"apk")
                return {"returncode": 0, "stdout": "", "stderr": ""}

            with (
                mock.patch.object(guided_jobs.base_jobs, "STATE_ROOT", state),
                mock.patch.object(guided_jobs, "refresh_job", return_value=job),
                mock.patch.object(guided_jobs.github_actions, "_validate_repository", return_value="octocat/demo"),
                mock.patch.object(guided_jobs.github_actions, "_gh", side_effect=fake_gh),
            ):
                path = guided_jobs.materialize_artifact("job-demo", "android-apk")

            self.assertEqual(path.name, "demo-debug.apk")
            self.assertEqual(path.read_bytes(), b"apk")


if __name__ == "__main__":
    unittest.main()
