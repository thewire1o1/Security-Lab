from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from security_lab.common import ROOT, run_command, utc_timestamp
from security_lab.platform import api as platform_api
from security_lab.remote_agent import Config, GitHubClient
from security_lab.remote_agent_ext import TaskRunner

MCP_PORT = int(os.environ.get("DPSR_MCP_PORT", "8766"))
MAX_READ_BYTES = 1_000_000
MAX_WRITE_BYTES = 250_000
MAX_LIST_ENTRIES = 500
SAFE_COMMAND = re.compile(r"^[A-Za-z0-9._-]+$")
PROTECTED_TASKS = frozenset({"bridge-reload", "codespace-retire-current", "mcp-stop"})
PROTECTED_COMMANDS = frozenset({"remote-agent", "mcp-control"})
SENSITIVE_NAMES = frozenset({".env", "secrets", ".git"})
SENSITIVE_SUFFIXES = (".key", ".pem", ".p12", ".pfx", ".kdbx")

mcp = MCPServer(
    "Digital Paragon Security Research",
    instructions=(
        "Control the DPSR development and security platform. Prefer structured project, job, repository, "
        "and service tools over generic command execution. The GitHub recovery bridge remains an independent "
        "fallback control path."
    ),
)


def _runner() -> TaskRunner:
    config = Config()
    return TaskRunner(config, GitHubClient(config))


def _safe_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    try:
        rel = candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Path escapes the repository root.") from exc

    lowered_parts = {part.lower() for part in rel.parts}
    if lowered_parts & SENSITIVE_NAMES:
        raise ValueError("Sensitive repository path is not exposed through MCP.")
    if candidate.name.lower().startswith(".env") or candidate.suffix.lower() in SENSITIVE_SUFFIXES:
        raise ValueError("Sensitive repository path is not exposed through MCP.")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str, timeout: float = 30) -> dict[str, Any]:
    return run_command(("git", "-C", str(ROOT), *args), timeout=timeout)


@mcp.tool()
def health() -> dict[str, Any]:
    """Return MCP server, Codespace, repository, and runtime health information."""
    head = _git("rev-parse", "--short", "HEAD")
    return {
        "status": "ok",
        "server": "dpsr-mcp",
        "transport": "streamable-http",
        "endpoint": f"http://127.0.0.1:{MCP_PORT}/mcp",
        "codespace": os.environ.get("CODESPACE_NAME", ""),
        "repository": os.environ.get("GITHUB_REPOSITORY", "thewire1o1/Security-Lab"),
        "git_head": head.get("stdout", "").strip(),
        "utc": utc_timestamp(),
    }


@mcp.tool()
def platform_status(job_limit: int = 20) -> dict[str, Any]:
    """Return DPSR platform profiles, registered projects, runner inventory, and recent jobs."""
    return platform_api.snapshot(max(1, min(job_limit, 100)))


@mcp.tool()
def platform_profile(name: str) -> dict[str, Any]:
    """Return one development or security profile by name."""
    return platform_api.profile(name)


@mcp.tool()
def platform_project(name: str) -> dict[str, Any]:
    """Return one registered DPSR project by name."""
    return platform_api.project(name)


@mcp.tool()
def platform_project_init(name: str, profile_name: str) -> dict[str, Any]:
    """Create and register a project in the managed DPSR project workspace using a built-in profile."""
    return platform_api.create_project(name, profile_name)


@mcp.tool()
def platform_project_refresh_template(name: str) -> dict[str, Any]:
    """Refresh DPSR-managed mobile build and CI files without overwriting application source."""
    return platform_api.refresh_project_template(name)


@mcp.tool()
def platform_project_delete(name: str) -> dict[str, Any]:
    """Delete one registered project only when it resides inside the managed DPSR project workspace."""
    return platform_api.delete_project(name)


@mcp.tool()
def platform_job(job_id: str) -> dict[str, Any]:
    """Return one persisted DPSR job by id."""
    return platform_api.job(job_id)


@mcp.tool()
def platform_job_run(project_name: str, command_name: str) -> dict[str, Any]:
    """Execute one bounded manifest command as a persisted DPSR job."""
    return platform_api.execute_job(project_name, command_name)


@mcp.tool()
def list_tasks() -> list[str]:
    """List remote-agent task names available to the MCP control plane."""
    return sorted(task for task in _runner().allowed_tasks if task not in PROTECTED_TASKS)


@mcp.tool()
def run_task(task: str) -> dict[str, Any]:
    """Run one allowlisted DPSR task and return its exit code and bounded output."""
    runner = _runner()
    if task in PROTECTED_TASKS:
        return {"ok": False, "task": task, "error": "Task is reserved for the fallback control plane."}
    if task not in runner.allowed_tasks:
        return {"ok": False, "task": task, "error": "Task is not allowlisted."}
    returncode, output = runner.run(task)
    return {"ok": returncode == 0, "task": task, "returncode": returncode, "output": output}


@mcp.tool()
def repo_status() -> dict[str, Any]:
    """Return the current Git branch and working-tree status."""
    result = _git("status", "--short", "--branch")
    return {
        "ok": result["returncode"] == 0,
        "returncode": result["returncode"],
        "status": result["stdout"],
        "error": result["stderr"],
    }


@mcp.resource("dpsr://repo/status")
def repo_status_resource() -> str:
    """Read the current Git working-tree status."""
    result = _git("status", "--short", "--branch")
    return result["stdout"] or result["stderr"]


@mcp.tool()
def repo_list(path: str = ".", max_entries: int = 200) -> list[dict[str, Any]]:
    """List files and directories beneath a repository-relative directory."""
    target = _safe_path(path)
    if not target.exists():
        raise ValueError("Path does not exist.")
    if not target.is_dir():
        raise ValueError("Path is not a directory.")
    limit = min(max(max_entries, 1), MAX_LIST_ENTRIES)
    rows: list[dict[str, Any]] = []
    for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:limit]:
        try:
            rel = child.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if child.name.lower() in SENSITIVE_NAMES or child.name.lower().startswith(".env"):
            continue
        if child.suffix.lower() in SENSITIVE_SUFFIXES:
            continue
        rows.append(
            {
                "path": rel,
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
        )
    return rows


@mcp.tool()
def repo_read(path: str, start_line: int = 1, end_line: int = 200) -> dict[str, Any]:
    """Read a bounded UTF-8 line range from a repository-relative text file."""
    target = _safe_path(path)
    if not target.is_file():
        raise ValueError("Path is not a file.")
    if target.stat().st_size > MAX_READ_BYTES:
        raise ValueError("File exceeds MCP read limit.")
    start = max(start_line, 1)
    end = min(max(end_line, start), start + 999)
    lines = target.read_text(encoding="utf-8").splitlines()
    selected = lines[start - 1 : end]
    return {
        "path": target.relative_to(ROOT).as_posix(),
        "start_line": start,
        "end_line": start + len(selected) - 1 if selected else start - 1,
        "sha256": _sha256(target),
        "content": "\n".join(selected),
    }


@mcp.tool()
def repo_write(path: str, content: str, expected_sha256: str = "") -> dict[str, Any]:
    """Create or replace a repository text file, optionally guarded by its current SHA-256."""
    target = _safe_path(path)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_WRITE_BYTES:
        raise ValueError("Content exceeds MCP write limit.")
    if target.exists() and not target.is_file():
        raise ValueError("Path is not a file.")
    if expected_sha256:
        if not target.exists():
            return {"ok": False, "path": path, "error": "Expected existing file is missing."}
        current = _sha256(target)
        if current != expected_sha256:
            return {"ok": False, "path": path, "error": "SHA-256 precondition failed.", "sha256": current}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": target.relative_to(ROOT).as_posix(),
        "bytes": len(encoded),
        "sha256": _sha256(target),
    }


@mcp.tool()
def run_project_command(command: str, args: list[str] | None = None, timeout_seconds: int = 300) -> dict[str, Any]:
    """Run a repository bin command directly without a shell."""
    if not SAFE_COMMAND.fullmatch(command) or command in PROTECTED_COMMANDS:
        return {"ok": False, "command": command, "error": "Command is not exposed through MCP."}
    executable = (ROOT / "bin" / command).resolve()
    try:
        executable.relative_to(ROOT / "bin")
    except ValueError:
        return {"ok": False, "command": command, "error": "Invalid command path."}
    if not executable.is_file():
        return {"ok": False, "command": command, "error": "Command does not exist."}
    argv = [str(executable), *(args or [])]
    timeout = min(max(timeout_seconds, 1), 3600)
    result = run_command(argv, timeout=timeout)
    return {
        "ok": result["returncode"] == 0,
        "command": command,
        "args": args or [],
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@mcp.tool()
def service_status() -> dict[str, Any]:
    """Return status for the fallback bridge, MCP server, and operations console."""
    services = {
        "bridge": ("bash", str(ROOT / "bin" / "remote-agent"), "status"),
        "mcp": ("bash", str(ROOT / "bin" / "mcp-control"), "status"),
        "gui": ("bash", str(ROOT / "bin" / "dashboard-control"), "status"),
    }
    output: dict[str, Any] = {}
    for name, argv in services.items():
        result = run_command(argv, timeout=10)
        output[name] = {
            "running": result["returncode"] == 0,
            "returncode": result["returncode"],
            "output": "\n".join(part for part in (result["stdout"].strip(), result["stderr"].strip()) if part),
        }
    return output


def _transport_security() -> TransportSecuritySettings:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    codespace = os.environ.get("CODESPACE_NAME", "").strip()
    if codespace:
        forwarded = f"{codespace}-{MCP_PORT}.app.github.dev"
        hosts.append(forwarded)
        origins.append(f"https://{forwarded}")
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=MCP_PORT,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(),
    )


if __name__ == "__main__":
    main()
