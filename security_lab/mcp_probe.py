from __future__ import annotations

import asyncio
import json
import os

from mcp import Client


async def probe() -> int:
    port = int(os.environ.get("DPSR_MCP_PORT", "8766"))
    url = os.environ.get("DPSR_MCP_URL", f"http://127.0.0.1:{port}/mcp")
    async with Client(url) as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)
        health = await client.call_tool("health", {})
        payload = {
            "ok": not health.is_error,
            "url": url,
            "tools": names,
            "tool_count": len(names),
            "health": health.structured_content,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0 if payload["ok"] and names else 1


def main() -> int:
    return asyncio.run(probe())


if __name__ == "__main__":
    raise SystemExit(main())
