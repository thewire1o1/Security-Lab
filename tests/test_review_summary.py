from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from security_lab.review_summary import summarize_review


class ReviewSummaryTests(unittest.TestCase):
    def test_normalizes_scanner_severity_and_counts_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "semgrep.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {"extra": {"severity": "ERROR"}},
                            {"extra": {"severity": "WARNING"}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (output / "bandit.json").write_text(
                json.dumps({"results": [{"issue_severity": "LOW"}]}), encoding="utf-8"
            )
            (output / "gitleaks.json").write_text(
                json.dumps([{"RuleID": "test"}]), encoding="utf-8"
            )
            (output / "trivy.json").write_text(
                json.dumps(
                    {
                        "Results": [
                            {
                                "Vulnerabilities": [{"Severity": "CRITICAL"}],
                                "Misconfigurations": [{"Severity": "MEDIUM"}],
                                "Secrets": [{"RuleID": "private-key"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = summarize_review(output)

            self.assertEqual(summary["severity"]["critical"], 1)
            self.assertEqual(summary["severity"]["high"], 3)
            self.assertEqual(summary["severity"]["medium"], 2)
            self.assertEqual(summary["severity"]["low"], 1)
            self.assertEqual(summary["total"], 7)
            self.assertEqual(summary["tools"]["trivy"]["secrets"], 1)
            self.assertTrue(summary["coverage"]["complete"])
            self.assertTrue((output / "summary.json").is_file())

    def test_missing_scanner_files_produce_empty_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = summarize_review(Path(tmp))
            self.assertEqual(summary["total"], 0)
            self.assertEqual(sum(summary["severity"].values()), 0)

    def test_unavailable_scanner_is_reported_as_incomplete_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "trivy.unavailable").touch()
            summary = summarize_review(output)
            self.assertFalse(summary["coverage"]["complete"])
            self.assertIn("trivy", summary["coverage"]["missing"])
            self.assertNotIn("trivy", summary["coverage"]["available"])


if __name__ == "__main__":
    unittest.main()
