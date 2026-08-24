from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from security_lab.triage_summary import summarize


class TriageSummaryTests(unittest.TestCase):
    def test_hashes_sample_once_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sample = base / "sample.bin"
            output = base / "out"
            output.mkdir()
            sample.write_bytes(b"security-lab-test")
            (output / "file.txt").write_text("data\n", encoding="utf-8")

            summary = summarize(sample, output)

            expected = hashlib.sha256(b"security-lab-test").hexdigest()
            self.assertEqual(summary["sha256"], expected)
            self.assertIn("sha256.txt", summary["artifacts"])
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
