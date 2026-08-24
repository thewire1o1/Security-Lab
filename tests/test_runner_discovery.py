from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security_lab.platform import jobs


class RunnerDiscoveryTests(unittest.TestCase):
    def test_discovery_filters_old_and_claimed_runs(self) -> None:
        external = {
            "provider": "github-actions",
            "repository": "octocat/demo",
            "workflow": "android.yml",
            "ref": "main",
            "command": "build",
            "dispatched_at": "2026-08-24T08:40:51Z",
            "run_id": None,
            "status": "submitted",
            "url": "",
        }
        rows = [
            {"id": 1, "created_at": "2026-08-24T08:40:30Z", "status": "completed", "conclusion": "success", "html_url": "old"},
            {"id": 2, "created_at": "2026-08-24T08:40:55Z", "status": "queued", "conclusion": "", "html_url": "claimed"},
            {"id": 3, "created_at": "2026-08-24T08:41:00Z", "status": "in_progress", "conclusion": "", "html_url": "selected"},
        ]
        job = {"id": "job-current"}
        result = {"returncode": 0, "stdout": json.dumps({"workflow_runs": rows}), "stderr": ""}
        with (
            mock.patch.object(jobs.github_actions, "require_auth", return_value={"safe": True}),
            mock.patch.object(jobs.github_actions, "_gh", return_value=result) as gh_mock,
            mock.patch.object(jobs, "_claimed_external_run_ids", return_value={2}),
        ):
            discovered = jobs._discover_github_actions_run(job, external)
        self.assertEqual(discovered["run_id"], 3)
        self.assertEqual(discovered["url"], "selected")
        self.assertEqual(discovered["status"], "in_progress")
        self.assertEqual(gh_mock.call_args.args[0], "api")
        self.assertIn("event=workflow_dispatch", gh_mock.call_args.args[1])
        self.assertIn("branch=main", gh_mock.call_args.args[1])

    def test_refresh_recovers_missing_run_id_before_status_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            job = {
                "id": "job-20260824084050-abc123",
                "project": "demo",
                "command": "build",
                "runner": "github-actions",
                "state": "running",
                "created_at": "2026-08-24T08:40:50Z",
                "started_at": "2026-08-24T08:40:50Z",
                "finished_at": None,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "external": {
                    "provider": "github-actions",
                    "repository": "octocat/demo",
                    "workflow": "android.yml",
                    "ref": "main",
                    "command": "build",
                    "dispatched_at": "2026-08-24T08:40:51Z",
                    "run_id": None,
                    "status": "submitted",
                    "url": "",
                },
            }
            discovered = {**job["external"], "run_id": 77, "status": "queued", "url": "run"}
            completed = {**discovered, "status": "completed", "conclusion": "success"}
            with (
                mock.patch.object(jobs, "JOBS_ROOT", state),
                mock.patch.object(jobs, "_discover_github_actions_run", return_value=discovered) as discover_mock,
                mock.patch.object(jobs, "refresh_github_actions", return_value=completed) as refresh_mock,
            ):
                jobs._write(job)
                refreshed = jobs.refresh_job(job["id"])
        discover_mock.assert_called_once()
        refresh_mock.assert_called_once_with(discovered)
        self.assertEqual(refreshed["state"], "succeeded")
        self.assertEqual(refreshed["returncode"], 0)
        self.assertEqual(refreshed["external"]["run_id"], 77)


if __name__ == "__main__":
    unittest.main()
