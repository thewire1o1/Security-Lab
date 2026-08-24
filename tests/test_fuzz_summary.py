from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from security_lab.fuzz_summary import summarize


class FuzzSummaryTests(unittest.TestCase):
    def test_counts_ffuf_results_and_harness_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "juice-shop.json").write_text(
                json.dumps({"results": [{"url": "/admin"}, {"url": "/api"}]}), encoding="utf-8"
            )
            (output / "dvwa.json").write_text(json.dumps({"results": []}), encoding="utf-8")
            (output / "harness-parser.log").write_text("ok\n", encoding="utf-8")

            summary = summarize(output)

            self.assertEqual(summary["targets"]["juice-shop"], 2)
            self.assertEqual(summary["total_results"], 2)
            self.assertEqual(summary["harness_logs"], 1)


if __name__ == "__main__":
    unittest.main()
