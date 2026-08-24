# MCP via Out-of-Band Bridge

> APOTHEON ONE · **Unified. Elevated.** · by Digital Paragon

The GitHub issue transport can invoke any tool currently advertised by the APOTHEON ONE MCP server without duplicating MCP tool definitions in the remote agent.

## Discover tools

```text
task: mcp-tools
```

## Invoke a tool

```text
task: mcp-call
tool: health
args-json: {}
```

Arguments are a single-line JSON object. Example:

```text
task: mcp-call
tool: repo_read
args-json: {"path":"README.md","start_line":1,"end_line":20}
```

The bridge validates the request envelope, connects to the local MCP endpoint, confirms that the requested tool is currently advertised, and forwards the arguments through MCP. Tool-specific authorization and validation remain inside the MCP server.

The remote bridge keeps its existing fixed recovery commands for operations that must remain available if MCP is unavailable, including MCP lifecycle management and bridge reload.
