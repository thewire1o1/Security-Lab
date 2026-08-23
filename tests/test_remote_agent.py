from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from security_lab.remote_agent import Config, GitHubClient, RemoteAgent, TaskRunner, parse_task


class FakeClient:
    def __init__(self) -> None:
        self._token = "github_pat_example_secret_value_1234567890"
        self.created_payload: dict[str, Any] | None = None

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        if method == "GET" and path.endswith("/codespaces/machines"):
            return {
                "machines": [
                    {"name": "broken", "cpus": 0, "memory_in_bytes": None, "storage_in_bytes": 0},
                    {"name": "large", "cpus": 4, "memory_in_bytes": 16, "storage_in_bytes": 64},
                    {"name": "small", "cpus": 2, "memory_in_bytes": 8, "storage_in_bytes": 32},
                ]
            }
        if method == "POST" and path.endswith("/codespaces"):
            self.created_payload = payload
            return {
                "name": "clean-lab",
                "display_name": "clean lab",
                "state": "Provisioning",
                "web_url": "https://clean-lab.github.dev",
                "machine": {"display_name": "2 cores, 8 GB RAM, 32 GB storage"},
            }
        raise AssertionError(f"unexpected request: {method} {path}")


class RemoteAgentTests(unittest.TestCase):
    def test_parse_task_requires_exactly_one_task(self) -> None:
        self.assertEqual(parse_task("task: doctor"), "doctor")
        self.assertIsNone(parse_task("no task here"))
        self.assertIsNone(parse_task("task: doctor\ntask: status"))

    def test_allowlist_has_no_arbitrary_shell_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = TaskRunner(Config(root=Path(tmp)), FakeClient())  # type: ignore[arg-type]
            self.assertIn("doctor", runner.allowed_tasks)
            self.assertNotIn("shell", runner.allowed_tasks)
            self.assertNotIn("exec", runner.allowed_tasks)

    def test_codespace_creation_ignores_malformed_machine_and_selects_smallest_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient()
            runner = TaskRunner(Config(root=Path(tmp)), client)  # type: ignore[arg-type]
            returncode, output = runner.run("codespace-create")
            self.assertEqual(returncode, 0)
            self.assertIsNotNone(client.created_payload)
            self.assertEqual(client.created_payload["machine"], "small")  # type: ignore[index]
            self.assertEqual(json.loads(output)["name"], "clean-lab")

    def test_output_redacts_known_token_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient()
            runner = TaskRunner(Config(root=Path(tmp)), client)  # type: ignore[arg-type]
            text = f"token={client._token} ghp_abcdefghijklmnopqrstuvwxyz1234567890"
            sanitized = runner._sanitize(text)
            self.assertNotIn(client._token, sanitized)
            self.assertNotIn("ghp_", sanitized)
            self.assertIn("[REDACTED]", sanitized)

    def test_client_rejects_absolute_url_as_api_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = GitHubClient(Config(root=Path(tmp)))
            with self.assertRaises(ValueError):
                client.request("GET", "https://example.com/steal")

    def test_stale_pidfile_for_unrelated_process_is_not_treated_as_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(root=Path(tmp))
            config.pidfile.write_text(f"{os.getpid()}\n", encoding="utf-8")
            agent = RemoteAgent(config)
            self.assertEqual(agent.status(), 1)
            self.assertFalse(config.pidfile.exists())

    def test_config_rejects_invalid_repository_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                Config(root=Path(tmp), repo="invalid", owner="thewire1o1")


if __name__ == "__main__":
    unittest.main()
