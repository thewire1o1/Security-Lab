from __future__ import annotations

import asyncio
import json
import os

from mcp import Client

from security_lab.common import ROOT


async def probe() -> int:
    port = int(os.environ.get("DPSR_MCP_PORT", "8766"))
    url = os.environ.get("DPSR_MCP_URL", f"http://127.0.0.1:{port}/mcp")
    probe_path = "artifacts/mcp-roundtrip.txt"
    probe_file = ROOT / probe_path
    probe_value = "dpsr-mcp-roundtrip"

    try:
        async with Client(url) as client:
            tools = await client.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            health = await client.call_tool("health", {})
            repo_status = await client.call_tool("repo_status", {})
            command = await client.call_tool(
                "run_project_command",
                {"command": "dpsr", "args": ["help"], "timeout_seconds": 30},
            )
            write_result = await client.call_tool(
                "repo_write",
                {"path": probe_path, "content": probe_value},
            )
            read_result = await client.call_tool(
                "repo_read",
                {"path": probe_path, "start_line": 1, "end_line": 10},
            )

            read_content = read_result.structured_content or {}
            content = read_content.get("content", "") if isinstance(read_content, dict) else ""
            checks = {
                "health": not health.is_error,
                "repo_status": not repo_status.is_error,
                "project_command": not command.is_error,
                "repo_write": not write_result.is_error,
                "repo_read": not read_result.is_error and content == probe_value,
            }
            payload = {
                "ok": bool(names) and all(checks.values()),
                "url": url,
                "tools": names,
                "tool_count": len(names),
                "checks": checks,
                "health": health.structured_content,
            }
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
            return 0 if payload["ok"] else 1
    finally:
        probe_file.unlink(missing_ok=True)


def main() -> int:
    return asyncio.run(probe())


if __name__ == "__main__":
    raise SystemExit(main())
