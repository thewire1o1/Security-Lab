from __future__ import annotations

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
            }
        )


class RemoteAgent(base.RemoteAgent):
    def __init__(self, config: base.Config) -> None:
        self.config = config
        self.client = base.GitHubClient(config)
        self.runner = TaskRunner(config, self.client)
        self._stop_requested = False


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
