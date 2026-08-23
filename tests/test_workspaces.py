from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security_lab import engagement, research


class WorkspaceTests(unittest.TestCase):
    def test_engagement_cannot_escape_base_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(engagement, "BASE", Path(tmp)):
            with self.assertRaises(ValueError):
                engagement.create_engagement("..")

    def test_engagement_layout_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(engagement, "BASE", Path(tmp)):
            directory = engagement.create_engagement("client test")
            self.assertEqual(directory.name, "client-test")
            self.assertTrue((directory / "scope" / "targets.txt").is_file())
            self.assertTrue((directory / "notes" / "timeline.md").is_file())

    def test_research_case_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(research, "BASE", Path(tmp)):
            directory = research.create_case("parser bug")
            research.append_entry("parser bug", "note", "reproduced locally")
            research.append_entry("parser bug", "task", "write regression test")
            status = research.case_status("parser bug")
            self.assertEqual(status["notes"], 1)
            self.assertEqual(status["tasks"], 1)
            research.close_case("parser bug")
            self.assertEqual(research.case_status("parser bug")["case"]["status"], "closed")
            self.assertEqual(directory.name, "parser-bug")

    def test_malformed_case_metadata_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(research, "BASE", Path(tmp)):
            directory = research.create_case("corrupt case")
            metadata = directory / "case.json"
            metadata.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(ValueError):
                research.case_status("corrupt case")
            with self.assertRaises(ValueError):
                research.close_case("corrupt case")
            self.assertEqual(metadata.read_text(encoding="utf-8"), "{not-json")


if __name__ == "__main__":
    unittest.main()
