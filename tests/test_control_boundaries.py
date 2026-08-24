from __future__ import annotations

import unittest

from security_lab.remote_agent import Config, GitHubClient
from security_lab.remote_agent_ext import BridgeGitHubClient, TaskRunner


class ControlBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config()

    def test_mcp_runner_excludes_recovery_and_codespace_tasks(self) -> None:
        runner = TaskRunner(self.config, GitHubClient(self.config))
        forbidden = {
            "bridge-reload",
            "bridge-auth-start",
            "bridge-auth-status",
            "bridge-auth-stop",
            "bridge-credential-status",
            "supervisor-start",
            "supervisor-status",
            "supervisor-restart",
            "supervisor-selftest",
            "codespace-list",
            "codespace-create",
            "codespace-retire-current",
        }
        self.assertTrue(forbidden.isdisjoint(runner.allowed_tasks))

    def test_fallback_runner_keeps_only_permanent_recovery_controls(self) -> None:
        runner = TaskRunner(self.config, BridgeGitHubClient(self.config))
        expected = {
            "bridge-reload",
            "bridge-credential-status",
            "supervisor-start",
            "supervisor-status",
            "supervisor-restart",
        }
        removed = {
            "bridge-auth-start",
            "bridge-auth-status",
            "bridge-auth-stop",
            "supervisor-selftest",
            "codespace-list",
            "codespace-create",
            "codespace-retire-current",
        }
        self.assertTrue(expected.issubset(runner.allowed_tasks))
        self.assertTrue(removed.isdisjoint(runner.allowed_tasks))


if __name__ == "__main__":
    unittest.main()
