from __future__ import annotations

import unittest
from unittest import mock

from security_lab import product_orchestrator


class ProductOrchestratorTests(unittest.TestCase):
    def test_mobile_build_metadata_names_the_actual_outcome(self) -> None:
        with mock.patch.object(
            product_orchestrator.platform_api,
            "project",
            return_value={"name": "demo", "profile": "android"},
        ):
            metadata, stages = product_orchestrator._project_metadata(
                "job:demo:build",
                ("bin/dpsr", "job", "run", "demo", "build"),
            )

        self.assertEqual(metadata["title"], "Build app: demo")
        self.assertEqual(metadata["target_label"], "demo")
        self.assertEqual([stage["id"] for stage in stages], ["prepare", "execute", "finish"])
        self.assertEqual(stages[1]["title"], "Build app")

    def test_failed_multistage_run_does_not_report_one_hundred_percent(self) -> None:
        manager = product_orchestrator.ProductActionManager(mock.Mock())
        manager._run = {
            "state": "failed",
            "progress": 0,
            "stages": [
                {"id": "prepare", "state": "completed"},
                {"id": "execute", "state": "failed"},
                {"id": "finish", "state": "pending"},
            ],
        }

        manager._recalculate_progress_locked()

        self.assertEqual(manager._run["progress"], 67)

    def test_successful_run_reports_complete(self) -> None:
        manager = product_orchestrator.ProductActionManager(mock.Mock())
        manager._run = {
            "state": "succeeded",
            "progress": 0,
            "stages": [
                {"id": "prepare", "state": "completed"},
                {"id": "execute", "state": "completed"},
                {"id": "finish", "state": "completed"},
            ],
        }

        manager._recalculate_progress_locked()

        self.assertEqual(manager._run["progress"], 100)


if __name__ == "__main__":
    unittest.main()
