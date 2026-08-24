from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from security_lab.platform import api, mobile, registry
from security_lab.platform.models import Project


class MobilePlatformTests(unittest.TestCase):
    def _registry_patches(self, state: Path):
        return (
            mock.patch.object(registry, "STATE_ROOT", state),
            mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
        )

    def test_flutter_provisioning_rewrites_flutter_binary_and_generates_ci(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "flutter-app"
            state = base / "state"
            flutter = base / "sdk" / "bin" / "flutter"
            flutter.parent.mkdir(parents=True)
            flutter.write_text("", encoding="utf-8")
            calls: list[tuple[str, ...]] = []

            def fake_run(argv, **_kwargs):
                command = tuple(str(item) for item in argv)
                calls.append(command)
                target = Path(command[-1])
                (target / "lib").mkdir(parents=True)
                (target / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
                (target / "lib" / "main.dart").write_text("void main() {}\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "created", "stderr": "", "command": list(command)}

            state_patch, registry_patch = self._registry_patches(state)
            with (
                state_patch,
                registry_patch,
                mock.patch.object(mobile, "_ensure_flutter", return_value=flutter),
                mock.patch.object(mobile, "run_command", side_effect=fake_run),
            ):
                project = mobile.init_mobile_project("flutter-app", "flutter", project_root)

            self.assertEqual(project.profile, "flutter")
            self.assertEqual(project.runner, "local")
            self.assertTrue((project_root / ".github" / "workflows" / "flutter.yml").is_file())
            manifest = (project_root / "dpsr.toml").read_text(encoding="utf-8")
            self.assertIn(str(flutter), manifest)
            create = calls[0]
            self.assertIn("--platforms=android,ios,web", create)
            self.assertIn("--empty", create)

    def test_react_native_provisioning_is_explicit_and_noninteractive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "rn-app"
            state = base / "state"
            calls: list[tuple[str, ...]] = []

            def fake_run(argv, **_kwargs):
                command = tuple(str(item) for item in argv)
                calls.append(command)
                directory = Path(command[command.index("--directory") + 1])
                directory.mkdir(parents=True)
                (directory / "android").mkdir()
                (directory / "ios").mkdir()
                (directory / "package.json").write_text("{}\n", encoding="utf-8")
                return {"returncode": 0, "stdout": "created", "stderr": "", "command": list(command)}

            state_patch, registry_patch = self._registry_patches(state)
            with (
                state_patch,
                registry_patch,
                mock.patch.object(mobile, "_ensure_react_native_node"),
                mock.patch.object(mobile, "run_command", side_effect=fake_run),
            ):
                project = mobile.init_mobile_project("rn-app", "react-native", project_root)

            self.assertEqual(project.profile, "react-native")
            self.assertTrue((project_root / ".github" / "workflows" / "react-native.yml").is_file())
            command = calls[0]
            self.assertEqual(command[:4], ("npx", "--yes", "@react-native-community/cli@latest", "init"))
            self.assertIn("--directory", command)
            self.assertEqual(command[command.index("--pm") + 1], "npm")
            self.assertEqual(command[command.index("--install-pods") + 1], "false")
            self.assertEqual(command[command.index("--skip-git-init") + 1], "true")

    def test_react_native_rejects_old_node(self) -> None:
        result = {"returncode": 0, "stdout": "v22.12.0\n", "stderr": "", "command": ["node", "--version"]}
        with mock.patch.object(mobile, "run_command", return_value=result):
            with self.assertRaisesRegex(ValueError, "Node.js 22.13 or newer"):
                mobile._ensure_react_native_node()

    def test_android_template_targets_available_sdk_and_external_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "android-app"
            state = base / "state"
            state_patch, registry_patch = self._registry_patches(state)
            with state_patch, registry_patch:
                project = mobile.init_mobile_project("android-app", "android", project_root)

            self.assertEqual(project.runner, "github-actions")
            root_gradle = (project_root / "app" / "build.gradle.kts").read_text(encoding="utf-8")
            module_gradle = (project_root / "app" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
            workflow = (project_root / ".github" / "workflows" / "android.yml").read_text(encoding="utf-8")
            self.assertIn('id("com.android.application") version "9.3.0"', root_gradle)
            self.assertNotIn("org.jetbrains.kotlin.android", root_gradle)
            self.assertIn("compileSdk = 36", module_gradle)
            self.assertIn("targetSdk = 36", module_gradle)
            self.assertIn("platforms;android-36", workflow)
            self.assertIn("build-tools;36.0.0", workflow)
            self.assertIn("gradle-version: '9.5.0'", workflow)
            self.assertIn("ubuntu-latest", workflow)

    def test_ios_template_generates_info_plist_on_macos_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project_root = base / "ios-app"
            state = base / "state"
            state_patch, registry_patch = self._registry_patches(state)
            with state_patch, registry_patch:
                project = mobile.init_mobile_project("ios-app", "ios", project_root)

            self.assertEqual(project.runner, "github-actions")
            self.assertTrue((project_root / "app" / "Sources" / "DpsrApp.swift").is_file())
            spec = (project_root / "app" / "project.yml").read_text(encoding="utf-8")
            workflow = (project_root / ".github" / "workflows" / "ios.yml").read_text(encoding="utf-8")
            self.assertIn("GENERATE_INFOPLIST_FILE: YES", spec)
            self.assertIn("INFOPLIST_KEY_CFBundleDisplayName", spec)
            self.assertIn("runs-on: macos-15", workflow)
            self.assertIn("xcodegen generate --spec app/project.yml", workflow)
            self.assertIn("CODE_SIGNING_ALLOWED=NO", workflow)

    def test_mobile_refresh_updates_build_files_without_overwriting_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            managed = base / "managed"
            project_root = managed / "android-app"
            state = base / "state"
            with (
                mock.patch.object(mobile, "PROJECTS_ROOT", managed),
                mock.patch.object(registry, "STATE_ROOT", state),
                mock.patch.object(registry, "REGISTRY_PATH", state / "projects.json"),
            ):
                project = mobile.init_mobile_project("android-app", "android", project_root)
                source = next((project_root / "app" / "app" / "src" / "main" / "java").rglob("MainActivity.kt"))
                source.write_text("custom application source\n", encoding="utf-8")
                module = project_root / "app" / "app" / "build.gradle.kts"
                module.write_text("compileSdk = 37\n", encoding="utf-8")
                refreshed = mobile.refresh_mobile_build_files(project)

            self.assertEqual(refreshed.name, "android-app")
            self.assertEqual(source.read_text(encoding="utf-8"), "custom application source\n")
            self.assertIn("compileSdk = 36", module.read_text(encoding="utf-8"))

    def test_api_routes_mobile_profiles_to_mobile_engine(self) -> None:
        project = Project(
            name="demo",
            path=Path("/tmp/demo"),
            profile="flutter",
            runner="local",
            commands={},
            services={},
            metadata={},
        )
        with mock.patch.object(api, "init_mobile_project", return_value=project) as init_mock:
            row = api.create_project("demo", "flutter")
        init_mock.assert_called_once_with("demo", "flutter")
        self.assertEqual(row["profile"], "flutter")

    def test_api_refresh_routes_existing_mobile_project(self) -> None:
        project = Project(
            name="demo",
            path=Path("/tmp/demo"),
            profile="ios",
            runner="github-actions",
            commands={},
            services={},
            metadata={},
        )
        with (
            mock.patch.object(api, "get_project", return_value=project),
            mock.patch.object(api, "refresh_mobile_build_files", return_value=project) as refresh_mock,
        ):
            row = api.refresh_project_template("demo")
        refresh_mock.assert_called_once_with(project)
        self.assertEqual(row["profile"], "ios")


if __name__ == "__main__":
    unittest.main()
