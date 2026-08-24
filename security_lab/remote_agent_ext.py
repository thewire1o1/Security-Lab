from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from security_lab import remote_agent as base

MCP_TOOL_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
MCP_TOOL_FIELD = re.compile(r"^tool:[ \t]*([^\r\n]+?)[ \t]*$", re.MULTILINE)
MCP_ARGS_FIELD = re.compile(r"^args-json:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
MAX_MCP_ARGS_BYTES = 32_768
BLOCKED_REMOTE_TASKS = frozenset({"codespace-list", "codespace-create", "codespace-retire-current"})
DEFAULT_BRIDGE_TOKEN_FILE = Path("/workspaces/.dpsr/bridge-token")
LEGACY_BRIDGE_TOKEN_FILE = Path.home() / ".config" / "dpsr" / "bridge-token"


def parse_mcp_request(body: str) -> tuple[str, dict[str, Any]]:
    tools = MCP_TOOL_FIELD.findall(body)
    if len(tools) != 1:
        raise ValueError("mcp-call requires exactly one `tool:` field.")
    tool = tools[0].strip()
    if not MCP_TOOL_PATTERN.fullmatch(tool):
        raise ValueError("Invalid MCP tool name.")

    args_fields = MCP_ARGS_FIELD.findall(body)
    if len(args_fields) > 1:
        raise ValueError("mcp-call accepts at most one `args-json:` field.")
    raw = args_fields[0].strip() if args_fields else "{}"
    if len(raw.encode("utf-8")) > MAX_MCP_ARGS_BYTES:
        raise ValueError("MCP arguments exceed bridge limit.")
    try:
        arguments = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("`args-json:` must contain valid single-line JSON.") from exc
    if not isinstance(arguments, dict):
        raise ValueError("`args-json:` must decode to a JSON object.")
    return tool, arguments


class BridgeGitHubClient(base.GitHubClient):
    @staticmethod
    def _token_file() -> Path:
        configured = os.environ.get("SEC_BRIDGE_TOKEN_FILE", "").strip()
        return Path(configured).expanduser() if configured else DEFAULT_BRIDGE_TOKEN_FILE

    @classmethod
    def _read_dedicated_token(cls) -> str:
        target = cls._token_file()
        try:
            token = target.read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
        if token:
            return token

        if target == LEGACY_BRIDGE_TOKEN_FILE:
            return ""
        try:
            legacy = LEGACY_BRIDGE_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        if not legacy:
            return ""

        target.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(target.parent, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
        target.write_text(legacy + "\n", encoding="utf-8")
        os.chmod(target, 0o600)
        return legacy

    def resolve_token(self) -> str:
        if self._token:
            return self._token

        dedicated = os.environ.get("DPSR_BRIDGE_TOKEN", "").strip()
        if not dedicated:
            dedicated = self._read_dedicated_token()
        if not dedicated:
            raise base.GitHubError("Dedicated bridge credential is unavailable; refusing broader credential fallback.")

        self._token = dedicated
        return dedicated


class TaskRunner(base.TaskRunner):
    def __init__(self, config: base.Config, client: base.GitHubClient) -> None:
        super().__init__(config, client)
        root = str(config.root)
        mcp_python = f"{root}/.venv-mcp/bin/python"
        self.specs.update(
            {
                "gui": base.TaskSpec(("bash", f"{root}/bin/dashboard-control", "start"), 30),
                "gui-stop": base.TaskSpec(("bash", f"{root}/bin/dashboard-control", "stop"), 30),
                "gui-status": base.TaskSpec(("bash", f"{root}/bin/dashboard-control", "status"), 30),
                "mcp-install": base.TaskSpec(("bash", f"{root}/bin/mcp-control", "install"), 600),
                "mcp-start": base.TaskSpec(("bash", f"{root}/bin/mcp-control", "start"), 600),
                "mcp-stop": base.TaskSpec(("bash", f"{root}/bin/mcp-control", "stop"), 30),
                "mcp-status": base.TaskSpec(("bash", f"{root}/bin/mcp-control", "status"), 30),
                "mcp-test": base.TaskSpec(("bash", f"{root}/bin/mcp-control", "test"), 90),
                "mcp-tools": base.TaskSpec((mcp_python, "-m", "security_lab.mcp_bridge_client", "--list"), 30),
            }
        )
        if isinstance(client, BridgeGitHubClient):
            self.specs.update(
                {
                    "supervisor-start": base.TaskSpec(("bash", f"{root}/admin/control-plane-supervisor", "start"), 30),
                    "supervisor-status": base.TaskSpec(("bash", f"{root}/admin/control-plane-supervisor", "status"), 30),
                    "supervisor-restart": base.TaskSpec(("bash", f"{root}/admin/control-plane-supervisor", "restart"), 30),
                    "bridge-credential-status": base.TaskSpec(("bash", f"{root}/admin/bridge-credential-status"), 30),
                    "bridge-reload": base.TaskSpec(("bash", f"{root}/admin/bridge-reload"), 30),
                }
            )

    @property
    def allowed_tasks(self) -> frozenset[str]:
        return (super().allowed_tasks - BLOCKED_REMOTE_TASKS) | {"mcp-call"}

    def run_mcp_call(self, tool: str, arguments: dict[str, Any]) -> tuple[int, str]:
        root = str(self.config.root)
        canonical_args = json.dumps(arguments, separators=(",", ":"), sort_keys=True)
        spec = base.TaskSpec(
            (
                f"{root}/.venv-mcp/bin/python",
                "-m",
                "security_lab.mcp_bridge_client",
                "--tool",
                tool,
                "--args-json",
                canonical_args,
            ),
            3660,
        )
        return self._run_process(spec)


class RemoteAgent(base.RemoteAgent):
    def __init__(self, config: base.Config) -> None:
        self.config = config
        self.client = BridgeGitHubClient(config)
        self.runner = TaskRunner(config, self.client)
        self._stop_requested = False

    def start(self) -> int:
        pid = self._read_pid()
        if pid is not None and self._pid_is_agent(pid):
            print(f"remote-agent already running: {pid}")
            return 0
        self.config.pidfile.unlink(missing_ok=True)
        self.client.resolve_token()
        self.config.reports.mkdir(parents=True, exist_ok=True)
        with self.config.logfile.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "security_lab.remote_agent_ext", "run"],
                cwd=self.config.root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        self.config.pidfile.write_text(f"{process.pid}\n", encoding="utf-8")
        print(f"remote-agent started: {process.pid}")
        return 0

    def _process_issue(self, issue: dict[str, Any]) -> None:
        body = str(issue.get("body") or "")
        task = base.parse_task(body)
        if task != "mcp-call":
            super()._process_issue(issue)
            return

        title = str(issue.get("title") or "")
        author = str((issue.get("user") or {}).get("login") or "")
        if not title.startswith(base.TITLE_PREFIX) or author != self.config.owner:
            return

        try:
            number = int(issue.get("number") or 0)
        except (TypeError, ValueError):
            return
        if number <= 0:
            return
        if task not in self.runner.allowed_tasks:
            self._reject(number, task, f"Rejected: task `{task}` is not allowlisted.")
            return

        try:
            tool, arguments = parse_mcp_request(body)
        except ValueError as exc:
            self._reject(number, task, f"Rejected: {exc}")
            return

        try:
            self._set_title(number, f"[DPSR-RUNNING] mcp-call:{tool}")
            returncode, output = self.runner.run_mcp_call(tool, arguments)
            result = "OK" if returncode == 0 else "FAIL"
            indented_output = output.replace("\n", "\n    ")
            result_body = (
                f"Task: mcp-call\n"
                f"Tool: {tool}\n"
                f"Exit code: {returncode}\n"
                f"Codespace: {base._env('CODESPACE_NAME', 'unknown')}\n"
                f"UTC: {base.utc_timestamp()}\n\n"
                f"Output:\n\n    {indented_output}"
            )
            self._comment(number, result_body)
            self._close(number, f"[DPSR-{result}] mcp-call:{tool}")
        except base.GitHubError as exc:
            print(f"[{base.utc_timestamp()}] issue {number} failed: {exc}", flush=True)


def main() -> int:
    args = base.build_parser().parse_args()
    try:
        config = base.Config()
        if args.command == "delete-codespace":
            return base.delete_codespace(config, args.name, args.delay)

        agent = RemoteAgent(config)
        if args.command == "start":
            return agent.start()
        if args.command == "stop":
            return agent.stop()
        if args.command == "status":
            return agent.status()
        return agent.run_foreground()
    except (base.GitHubError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
