from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security_lab.platform import api, cli, jobs, registry, scaffold
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

    def test_nextjs_provisioning_is_explicit_noninteractive_and_registered(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "demo-next"
            state = base / "state"
            calls: list[tuple[str, ...]] = []

            def fake_run(argv, **_kwargs):
                command = tuple(str(item) for item in argv)
                calls.append(command)
                if command[:2] == ("node", "--version"):
                    return {"returncode": 0, "stdout": "v22.18.0\n", "stderr": "", "command": list(command)}
                if command[:3] == ("npx", "--yes", "create-next-app@latest"):
                    target = Path(command[3])
                    (target / "src" / "app").mkdir(parents=True)
                    (target / "package.json").write_text('{"scripts":{"lint":"eslint","build":"next build"}}\n', encoding="utf-8")
                    (target / "README.md").write_text("# Next app\n", encoding="utf-8")
                    return {"returncode": 0, "stdout": "created", "stderr": "", "command": list(command)}
                raise AssertionError(f"unexpected command: {command}")

            with (
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
                mock.patch.object(scaffold, "run_command", side_effect=fake_run),
            ):
                project = scaffold.init_project("demo-next", "nextjs", project_root)

            self.assertEqual(project.profile, "nextjs")
            self.assertTrue((project_root / "dpsr.toml").is_file())
            create = calls[1]
            for expected in ("--ts", "--eslint", "--tailwind", "--app", "--src-dir", "--turbopack", "--use-npm", "--disable-git", "--yes"):
                self.assertIn(expected, create)
            self.assertNotIn("sh", create)

    def test_nextjs_rejects_unsupported_node_before_scaffolding(self) -> None:
        result = {"returncode": 0, "stdout": "v18.20.0\n", "stderr": "", "command": ["node", "--version"]}
        with mock.patch.object(scaffold, "run_command", return_value=result):
            with self.assertRaisesRegex(ValueError, "Node.js 20.9 or newer"):
                scaffold._ensure_next_prerequisites()

    def test_fastapi_provisioning_creates_isolated_app(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "demo-api"
            state = base / "state"
            calls: list[tuple[str, ...]] = []

            def fake_run(argv, **_kwargs):
                command = tuple(str(item) for item in argv)
                calls.append(command)
                if command[:3] == ("python3", "-m", "venv"):
                    (project_root / ".venv" / "bin").mkdir(parents=True)
                    return {"returncode": 0, "stdout": "", "stderr": "", "command": list(command)}
                if len(command) >= 4 and command[1:4] == ("-m", "pip", "install"):
                    return {"returncode": 0, "stdout": "", "stderr": "", "command": list(command)}
                raise AssertionError(f"unexpected command: {command}")

            with (
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
                mock.patch.object(scaffold, "run_command", side_effect=fake_run),
            ):
                project = scaffold.init_project("demo-api", "fastapi", project_root)

            self.assertEqual(project.profile, "fastapi")
            self.assertTrue((project_root / "src" / "main.py").is_file())
            self.assertTrue((project_root / "tests" / "test_health.py").is_file())
            self.assertTrue((project_root / "requirements.txt").is_file())
            self.assertTrue((project_root / "dpsr.toml").is_file())
            self.assertEqual(calls[0][:3], ("python3", "-m", "venv"))
            self.assertIn("requirements.txt", calls[1])

    def test_fullstack_provisioning_composes_proven_framework_provisioners(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "demo-stack"
            state = base / "state"

            def fake_next(target: Path) -> None:
                (target / "src" / "app").mkdir(parents=True)
                (target / "package.json").write_text("{}\n", encoding="utf-8")
                (target / "README.md").write_text("# Web\n", encoding="utf-8")

            def fake_api(target: Path) -> None:
                (target / "src").mkdir(parents=True)
                (target / "tests").mkdir(parents=True)
                (target / ".venv" / "bin").mkdir(parents=True)
                (target / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

            with (
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
                mock.patch.object(scaffold, "_provision_nextjs", side_effect=fake_next) as next_mock,
                mock.patch.object(scaffold, "_provision_fastapi", side_effect=fake_api) as api_mock,
            ):
                project = scaffold.init_project("demo-stack", "fullstack-web", project_root)

            self.assertEqual(project.profile, "fullstack-web")
            next_mock.assert_called_once_with(project_root / "apps" / "web")
            api_mock.assert_called_once_with(project_root / "apps" / "api")
            self.assertTrue((project_root / "compose.yaml").is_file())
            self.assertTrue((project_root / "apps" / "web" / "Dockerfile").is_file())
            self.assertTrue((project_root / "apps" / "api" / "Dockerfile").is_file())
            self.assertTrue((project_root / "apps" / "web" / "src" / "app" / "api" / "backend-health" / "route.ts").is_file())
            self.assertTrue((project_root / "tools" / "stack_check.py").is_file())
            self.assertTrue((project_root / ".env").is_file())
            self.assertTrue((project_root / ".env.example").is_file())
            self.assertTrue((project_root / "dpsr.toml").is_file())
            self.assertEqual(project.services, {"api": 8000, "web": 3000})

    def test_managed_delete_removes_only_project_root_children(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            managed = base / "managed"
            state = base / "state"
            project_root = managed / "delete-me"
            project_root.mkdir(parents=True)
            (project_root / "dpsr.toml").write_text(
                """
[project]
name = "delete-me"
profile = "generic"
[runner]
type = "local"
""".strip() + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(registry, "PROJECTS_ROOT", managed),
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
            ):
                registry.register_project(project_root)
                deleted = registry.delete_managed_project("delete-me")
                self.assertEqual(deleted.name, "delete-me")
                self.assertFalse(project_root.exists())
                with self.assertRaisesRegex(ValueError, "Unknown project"):
                    registry.get_project("delete-me")

    def test_managed_delete_refuses_registered_external_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            managed = base / "managed"
            external = base / "external"
            state = base / "state"
            managed.mkdir()
            external.mkdir()
            (external / "dpsr.toml").write_text(
                """
[project]
name = "external"
profile = "generic"
[runner]
type = "local"
""".strip() + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(registry, "PROJECTS_ROOT", managed),
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
            ):
                registry.register_project(external)
                with self.assertRaisesRegex(ValueError, "managed DPSR project root"):
                    registry.delete_managed_project("external")
                self.assertTrue(external.is_dir())
                self.assertEqual(registry.get_project("external").path, external.resolve())

    def test_command_string_is_tokenized_without_shell(self) -> None:
        command = CommandSpec.from_value("python3 -c 'print(123)'")
        self.assertEqual(command.argv[0], "python3")
        self.assertNotIn("shell", command.argv)


if __name__ == "__main__":
    unittest.main()
