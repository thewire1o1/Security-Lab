from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from mcp import Client


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _jsonable(model_dump(mode="json"))
    return str(value)


async def _list_tools(url: str) -> dict[str, Any]:
    async with Client(url) as client:
        result = await client.list_tools()
        tools = []
        for tool in result.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": _jsonable(tool.input_schema),
                }
            )
        return {"ok": True, "url": url, "tool_count": len(tools), "tools": tools}


async def _call_tool(url: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(url) as client:
        listed = await client.list_tools()
        names = sorted(tool.name for tool in listed.tools)
        if tool_name not in names:
            return {
                "ok": False,
                "url": url,
                "tool": tool_name,
                "error": "MCP tool is not currently advertised by the server.",
                "available_tools": names,
            }

        result = await client.call_tool(tool_name, arguments)
        return {
            "ok": not result.is_error,
            "url": url,
            "tool": tool_name,
            "arguments": arguments,
            "structured_content": _jsonable(result.structured_content),
            "content": _jsonable(result.content),
        }


def _url() -> str:
    port = int(os.environ.get("DPSR_MCP_PORT", "8766"))
    return os.environ.get("DPSR_MCP_URL", f"http://127.0.0.1:{port}/mcp")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DPSR MCP bridge client.")
    parser.add_argument("--list", action="store_true", dest="list_tools")
    parser.add_argument("--tool")
    parser.add_argument("--args-json", default="{}")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.list_tools:
            payload = asyncio.run(_list_tools(_url()))
        else:
            if not args.tool:
                raise ValueError("--tool is required unless --list is used.")
            arguments = json.loads(args.args_json)
            if not isinstance(arguments, dict):
                raise ValueError("--args-json must decode to a JSON object.")
            payload = asyncio.run(_call_tool(_url(), args.tool, arguments))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"ok": False, "error": str(exc)}
    except Exception as exc:
        payload = {"ok": False, "error": f"MCP client error: {exc}"}

    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
