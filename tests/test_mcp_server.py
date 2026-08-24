from __future__ import annotations

import unittest

from mcp import Client

from security_lab.mcp_server import mcp


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_discovery_and_health(self) -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            expected = {
                "health",
                "run_task",
                "repo_read",
                "repo_write",
                "run_project_command",
                "platform_status",
                "platform_profile",
                "platform_project",
                "platform_project_init",
                "platform_project_delete",
                "platform_job",
                "platform_job_run",
            }
            self.assertTrue(expected.issubset(names))

            health = await client.call_tool("health", {})
            self.assertFalse(health.is_error)
            self.assertIsNotNone(health.structured_content)

            platform = await client.call_tool("platform_status", {"job_limit": 5})
            self.assertFalse(platform.is_error)
            self.assertIsInstance(platform.structured_content, dict)
            self.assertEqual(platform.structured_content.get("platform"), "APOTHEON ONE")


if __name__ == "__main__":
    unittest.main()
