from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security_lab.platform import api, cli, jobs, registry
from security_lab.platform.models import CommandSpec, Project, load_project_manifest
from security_lab.platform.profiles import load_profiles
from security_lab.platform.runners import get_runner


class PlatformCoreTests(unittest.TestCase):
    def test_builtin_profiles_cover_core_domains(self) -> None:
        profiles = load_profiles()
        expected = {
            "security",
            "fullstack-web",
            "nextjs",
            "fastapi",
            "flutter",
            "react-native",
            "android",
            "ios",
        }
        self.assertTrue(expected.issubset(profiles))
        self.assertEqual(profiles["ios"].runner, "github-actions")

    def test_manifest_rejects_cwd_escape_at_runner_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "dpsr.toml").write_text(
                """
[project]
name = "demo"
profile = "fastapi"
[runner]
type = "local"
[commands.bad]
argv = ["python3", "-c", "print('x')"]
cwd = "../"
""".strip() + "\n",
                encoding="utf-8",
            )
            project = load_project_manifest(root)
            with self.assertRaises(ValueError):
                get_runner("local").run(project, project.commands["bad"])

    def test_registry_and_local_job_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "project"
            state = base / "state"
            project_root.mkdir()
            (project_root / "dpsr.toml").write_text(
                """
[project]
name = "demo"
profile = "generic"
[runner]
type = "local"
[commands.test]
argv = ["python3", "-c", "print('platform-ok')"]
cwd = "."
timeout = 30
""".strip() + "\n",
                encoding="utf-8",
            )

            with (
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
                mock.patch.object(jobs, "STATE_ROOT", state),
                mock.patch.object(jobs, "JOBS_ROOT", state / "jobs"),
            ):
                registered = registry.register_project(project_root)
                self.assertEqual(registered.name, "demo")
                result = jobs.run_job("demo", "test")
                self.assertEqual(result["state"], "succeeded")
                self.assertIn("platform-ok", result["stdout"])
                self.assertEqual(jobs.get_job(result["id"])["returncode"], 0)

    def test_job_run_parser_preserves_top_level_subcommand(self) -> None:
        args = cli.build_parser().parse_args(["job", "run", "demo", "lint"])
        self.assertEqual(args.command, "job")
        self.assertEqual(args.job_command, "run")
        self.assertEqual(args.project, "demo")
        self.assertEqual(args.command_name, "lint")

    def test_structured_job_rejects_long_running_command(self) -> None:
        project = Project(
            name="demo",
            path=Path("/tmp/demo"),
            profile="generic",
            runner="local",
            commands={"dev": CommandSpec(("python3",), timeout=86400)},
            services={},
            metadata={},
        )
        with mock.patch.object(api, "get_project", return_value=project):
            with self.assertRaisesRegex(ValueError, "not eligible for synchronous MCP execution"):
                api.execute_job("demo", "dev")

    def test_command_string_is_tokenized_without_shell(self) -> None:
        command = CommandSpec.from_value("python3 -c 'print(123)'")
        self.assertEqual(command.argv[0], "python3")
        self.assertNotIn("shell", command.argv)


if __name__ == "__main__":
    unittest.main()
