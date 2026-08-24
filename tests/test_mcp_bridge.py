from __future__ import annotations

import unittest

from security_lab.remote_agent_ext import parse_mcp_request


class MCPBridgeRequestTests(unittest.TestCase):
    def test_parses_tool_without_arguments(self) -> None:
        tool, arguments = parse_mcp_request("task: mcp-call\ntool: health")
        self.assertEqual(tool, "health")
        self.assertEqual(arguments, {})

    def test_parses_json_object_arguments(self) -> None:
        tool, arguments = parse_mcp_request(
            'task: mcp-call\ntool: repo_read\nargs-json: {"path":"README.md","start_line":1,"end_line":5}'
        )
        self.assertEqual(tool, "repo_read")
        self.assertEqual(arguments["path"], "README.md")
        self.assertEqual(arguments["end_line"], 5)

    def test_rejects_duplicate_tool_fields(self) -> None:
        with self.assertRaises(ValueError):
            parse_mcp_request("task: mcp-call\ntool: health\ntool: repo_status")

    def test_rejects_non_object_arguments(self) -> None:
        with self.assertRaises(ValueError):
            parse_mcp_request('task: mcp-call\ntool: health\nargs-json: [1,2,3]')

    def test_rejects_invalid_tool_name(self) -> None:
        with self.assertRaises(ValueError):
            parse_mcp_request("task: mcp-call\ntool: ../../bin/bash")


if __name__ == "__main__":
    unittest.main()
