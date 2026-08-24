from __future__ import annotations

import unittest

from mcp import Client

from security_lab.mcp_server import mcp


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_discovery_and_health(self) -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            self.assertIn("health", names)
            self.assertIn("run_task", names)
            self.assertIn("repo_read", names)
            self.assertIn("repo_write", names)
            self.assertIn("run_project_command", names)
            result = await client.call_tool("health", {})
            self.assertFalse(result.is_error)
            self.assertIsNotNone(result.structured_content)


if __name__ == "__main__":
    unittest.main()
