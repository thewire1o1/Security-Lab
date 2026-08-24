from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from security_lab.pipeline import finalize_pipeline


class PipelineTests(unittest.TestCase):
    def test_partial_review_and_missing_baseline_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "defense-test"
            (output / "fuzz").mkdir(parents=True)
            (output / "inventory.json").write_text("{}\n", encoding="utf-8")
            (output / "summary.json").write_text(
                json.dumps(
                    {
                        "severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
                        "coverage": {"complete": False, "missing": ["trivy"]},
                    }
                ),
                encoding="utf-8",
            )
            (output / "validation.json").write_text(
                json.dumps({"previous": None, "regression": False}), encoding="utf-8"
            )
            (output / "fuzz" / "summary.json").write_text(
                json.dumps({"total_results": 0}), encoding="utf-8"
            )

            pipeline = finalize_pipeline(output)

            self.assertEqual(pipeline["stages"]["review"], "partial")
            self.assertEqual(pipeline["stages"]["validation"], "no-baseline")
            self.assertEqual(pipeline["stages"]["external_review"], "not-configured")

    def test_failed_external_review_is_not_reported_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "defense-test"
            (output / "fuzz").mkdir(parents=True)
            (output / "summary.json").write_text(
                json.dumps({"severity": {}, "coverage": {"complete": True}}), encoding="utf-8"
            )
            (output / "validation.json").write_text(
                json.dumps({"previous": "defense-old", "regression": False}), encoding="utf-8"
            )
            (output / "fuzz" / "summary.json").write_text("{}\n", encoding="utf-8")
            (output / "external-review.rc").write_text("7\n", encoding="utf-8")

            pipeline = finalize_pipeline(output)
            self.assertEqual(pipeline["stages"]["external_review"], "failed")


if __name__ == "__main__":
    unittest.main()
