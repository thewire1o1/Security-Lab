from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from security_lab.validation import compare_runs


class ValidationTests(unittest.TestCase):
    def test_high_severity_increase_is_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            previous = base / "defense-old"
            current = base / "defense-new"
            previous.mkdir()
            current.mkdir()
            (previous / "summary.json").write_text(
                json.dumps({"severity": {"critical": 0, "high": 1, "medium": 2, "low": 0, "info": 0}}),
                encoding="utf-8",
            )
            (current / "summary.json").write_text(
                json.dumps({"severity": {"critical": 0, "high": 2, "medium": 1, "low": 0, "info": 0}}),
                encoding="utf-8",
            )

            result = compare_runs(current, previous)

            self.assertTrue(result["regression"])
            self.assertTrue(result["improved"])
            self.assertEqual(result["severity_delta"]["high"]["change"], 1)
            self.assertTrue((current / "validation.json").is_file())

    def test_first_run_uses_zero_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            current = Path(tmp) / "defense-new"
            current.mkdir()
            (current / "summary.json").write_text(
                json.dumps({"severity": {"critical": 0, "high": 0, "medium": 1, "low": 0, "info": 0}}),
                encoding="utf-8",
            )
            result = compare_runs(current, None)
            self.assertFalse(result["regression"])
            self.assertIsNone(result["previous"])


if __name__ == "__main__":
    unittest.main()
