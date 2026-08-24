from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from security_lab.report import build_payload, generate_report, nuclei_findings


class ReportTests(unittest.TestCase):
    def test_findings_are_classified_and_html_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            scan = reports / "lab-20260101-000000"
            scan.mkdir()
            (scan / "nuclei.txt").write_text(
                "[critical] <script>alert(1)</script>\n[low] harmless\n", encoding="utf-8"
            )
            (scan / "nmap-local.nmap").write_text("<host>\n", encoding="utf-8")
            html_output = reports / "report.html"
            json_output = reports / "report.json"

            output = generate_report(reports, html_output, json_output)
            document = output.read_text(encoding="utf-8")

            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", document)
            self.assertNotIn("<script>alert(1)</script>", document)
            self.assertIn("&lt;host&gt;", document)
            self.assertTrue(json_output.is_file())

    def test_payload_counts_severities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scan = Path(tmp)
            (scan / "nuclei.txt").write_text("[high] one\n[high] two\n[info] three\n", encoding="utf-8")
            findings = nuclei_findings(scan)
            payload = build_payload(scan, findings)
            self.assertEqual(payload["counts"]["high"], 2)
            self.assertEqual(payload["counts"]["info"], 1)


if __name__ == "__main__":
    unittest.main()
