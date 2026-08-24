from __future__ import annotations

import subprocess
import sys

from security_lab import remote_agent as base


class TaskRunner(base.TaskRunner):
    def __init__(self, config: base.Config, client: base.GitHubClient) -> None:
        super().__init__(config, client)
        root = str(config.root)
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
                "bridge-reload": base.TaskSpec(("bash", f"{root}/bin/bridge-reload"), 30),
            }
        )


class RemoteAgent(base.RemoteAgent):
    def __init__(self, config: base.Config) -> None:
        self.config = config
        self.client = base.GitHubClient(config)
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
