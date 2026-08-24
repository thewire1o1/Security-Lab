from __future__ import annotations

import re
import shutil
from pathlib import Path

from security_lab.common import run_command

from .models import CommandSpec, Profile
from .paths import PERSISTENT_ROOT, PROJECTS_ROOT
from .profiles import get_profile
from .registry import register_project

MOBILE_PROFILES = frozenset({"flutter", "react-native", "android", "ios"})
PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")
NODE_VERSION = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?")
REACT_NATIVE_MIN_NODE = (22, 13, 0)
TOOLCHAINS_ROOT = PERSISTENT_ROOT / ".dpsr" / "toolchains"
FLUTTER_ROOT = TOOLCHAINS_ROOT / "flutter"
ANDROID_AGP = "9.3.0"
ANDROID_GRADLE = "9.5.0"
ANDROID_KOTLIN = "2.2.0"
ANDROID_COMPILE_SDK = 37


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_command(name: str, spec: CommandSpec) -> str:
    argv = ", ".join(_toml_string(item) for item in spec.argv)
    return (
        f"[commands.{name}]\n"
        f"argv = [{argv}]\n"
        f"cwd = {_toml_string(spec.cwd)}\n"
        f"timeout = {spec.timeout}\n"
    )


def _render_manifest(name: str, profile: Profile) -> str:
    lines = [
        "# DPSR project manifest",
        "[project]",
        f"name = {_toml_string(name)}",
        f"profile = {_toml_string(profile.name)}",
        f"category = {_toml_string(profile.category)}",
        "",
        "[runner]",
        f"type = {_toml_string(profile.runner)}",
        "",
    ]
    if profile.services:
        lines.append("[services]")
        for service, port in sorted(profile.services.items()):
            lines.append(f"{service} = {port}")
        lines.append("")
    for command_name, command in sorted(profile.commands.items()):
        lines.append(_render_command(command_name, command).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _profile_with_binary(profile: Profile, command: str, binary: Path) -> Profile:
    commands: dict[str, CommandSpec] = {}
    for name, spec in profile.commands.items():
        argv = spec.argv
        if argv and argv[0] == command:
            argv = (str(binary), *argv[1:])
        commands[name] = CommandSpec(argv=argv, cwd=spec.cwd, timeout=spec.timeout)
    return Profile(
        name=profile.name,
        title=profile.title,
        category=profile.category,
        description=profile.description,
        runner=profile.runner,
        stack=profile.stack,
        capabilities=profile.capabilities,
        commands=commands,
        services=profile.services,
        scaffold=profile.scaffold,
    )


def _write_metadata(destination: Path, name: str, profile: Profile) -> None:
    (destination / "dpsr.toml").write_text(_render_manifest(name, profile), encoding="utf-8")
    readme = destination / "README.md"
    marker = f"\n## DPSR\n\nManaged profile: `{profile.name}`.\n\n{profile.description}\n"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace").rstrip()
        if "## DPSR" not in text:
            readme.write_text(text + marker, encoding="utf-8")
    else:
        readme.write_text(f"# {name}\n" + marker, encoding="utf-8")


def _command_failure(label: str, result: dict[str, object]) -> ValueError:
    stderr = str(result.get("stderr") or "").strip()
    stdout = str(result.get("stdout") or "").strip()
    detail = stderr or stdout or "no process output"
    return ValueError(f"{label} failed with exit code {result.get('returncode')}: {detail}")


def _node_version() -> tuple[int, int, int]:
    result = run_command(("node", "--version"), timeout=10)
    if result["returncode"] != 0:
        raise _command_failure("Node.js prerequisite check", result)
    match = NODE_VERSION.match(str(result["stdout"]).strip())
    if not match:
        raise ValueError(f"Unable to parse Node.js version: {result['stdout']!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def _ensure_react_native_node() -> None:
    version = _node_version()
    if version < REACT_NATIVE_MIN_NODE:
        actual = ".".join(str(part) for part in version)
        raise ValueError(f"React Native requires Node.js 22.13 or newer; found {actual}.")


def _pascal_name(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    value = "".join(part[:1].upper() + part[1:] for part in parts) or "DpsrApp"
    if value[0].isdigit():
        value = f"Dpsr{value}"
    return value


def _dart_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "dpsr_app"
    if value[0].isdigit():
        value = f"dpsr_{value}"
    return value


def _package_suffix(name: str) -> str:
    value = re.sub(r"[^a-z0-9]", "", name.lower()) or "app"
    if value[0].isdigit():
        value = f"app{value}"
    return value[:40]


def _managed_destination(destination: Path) -> bool:
    try:
        destination.relative_to(PROJECTS_ROOT.resolve())
        return True
    except ValueError:
        return False


def _ensure_flutter() -> Path:
    system = shutil.which("flutter")
    if system:
        return Path(system).resolve()

    binary = FLUTTER_ROOT / "bin" / "flutter"
    if not binary.is_file():
        TOOLCHAINS_ROOT.mkdir(parents=True, exist_ok=True)
        if FLUTTER_ROOT.exists():
            shutil.rmtree(FLUTTER_ROOT)
        clone = run_command(
            (
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "stable",
                "https://github.com/flutter/flutter.git",
                str(FLUTTER_ROOT),
            ),
            cwd=TOOLCHAINS_ROOT,
            timeout=1800,
            stdout_limit=20_000,
            stderr_limit=12_000,
        )
        if clone["returncode"] != 0:
            raise _command_failure("Flutter SDK installation", clone)

    version = run_command((str(binary), "--version"), cwd=FLUTTER_ROOT, timeout=900)
    if version["returncode"] != 0:
        raise _command_failure("Flutter SDK initialization", version)
    analytics = run_command((str(binary), "config", "--no-analytics"), cwd=FLUTTER_ROOT, timeout=60)
    if analytics["returncode"] != 0:
        raise _command_failure("Flutter analytics configuration", analytics)
    return binary


def _provision_flutter(destination: Path, name: str, profile: Profile) -> Profile:
    flutter = _ensure_flutter()
    app = destination / "app"
    destination.mkdir(parents=True, exist_ok=True)
    result = run_command(
        (
            str(flutter),
            "create",
            "--empty",
            "--platforms=android,ios,web",
            "--org",
            "com.digitalparagon",
            "--project-name",
            _dart_name(name),
            str(app),
        ),
        cwd=destination,
        timeout=1200,
        stdout_limit=20_000,
        stderr_limit=12_000,
    )
    if result["returncode"] != 0:
        raise _command_failure("Flutter provisioning", result)
    if not (app / "pubspec.yaml").is_file() or not (app / "lib" / "main.dart").is_file():
        raise ValueError("Flutter provisioning completed without the expected application layout.")
    return _profile_with_binary(profile, "flutter", flutter)


def _provision_react_native(destination: Path, name: str, profile: Profile) -> Profile:
    _ensure_react_native_node()
    destination.mkdir(parents=True, exist_ok=True)
    app = destination / "app"
    app_name = _pascal_name(name)
    package = f"com.digitalparagon.{_package_suffix(name)}"
    result = run_command(
        (
            "npx",
            "--yes",
            "@react-native-community/cli@latest",
            "init",
            app_name,
            "--version",
            "latest",
            "--directory",
            str(app),
            "--title",
            app_name,
            "--pm",
            "npm",
            "--package-name",
            package,
            "--skip-git-init",
            "true",
            "--install-pods",
            "false",
        ),
        cwd=destination,
        timeout=1800,
        stdout_limit=24_000,
        stderr_limit=16_000,
    )
    if result["returncode"] != 0:
        raise _command_failure("React Native provisioning", result)
    required = (app / "package.json", app / "android", app / "ios")
    if not required[0].is_file() or not required[1].is_dir() or not required[2].is_dir():
        raise ValueError("React Native provisioning completed without the expected Android/iOS application layout.")
    return profile


def _write_android_project(destination: Path, name: str) -> None:
    app = destination / "app"
    source = app / "app" / "src" / "main"
    package_suffix = _package_suffix(name)
    package = f"com.digitalparagon.{package_suffix}"
    package_path = source / "java" / "com" / "digitalparagon" / package_suffix
    values = source / "res" / "values"
    package_path.mkdir(parents=True, exist_ok=True)
    values.mkdir(parents=True, exist_ok=True)

    (app / "settings.gradle.kts").write_text(
        'pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n'
        'dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\n'
        'rootProject.name = "DpsrAndroid"\n'
        'include(":app")\n',
        encoding="utf-8",
    )
    (app / "build.gradle.kts").write_text(
        "plugins {\n"
        f'    id("com.android.application") version "{ANDROID_AGP}" apply false\n'
        f'    id("org.jetbrains.kotlin.android") version "{ANDROID_KOTLIN}" apply false\n'
        "}\n",
        encoding="utf-8",
    )
    module = app / "app"
    module.mkdir(parents=True, exist_ok=True)
    (module / "build.gradle.kts").write_text(
        "plugins {\n"
        '    id("com.android.application")\n'
        '    id("org.jetbrains.kotlin.android")\n'
        "}\n\n"
        "android {\n"
        f'    namespace = "{package}"\n'
        f"    compileSdk = {ANDROID_COMPILE_SDK}\n\n"
        "    defaultConfig {\n"
        f'        applicationId = "{package}"\n'
        "        minSdk = 24\n"
        f"        targetSdk = {ANDROID_COMPILE_SDK}\n"
        "        versionCode = 1\n"
        '        versionName = "1.0"\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (source / "AndroidManifest.xml").write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <application android:theme="@style/AppTheme" android:label="@string/app_name">\n'
        '        <activity android:name=".MainActivity" android:exported="true">\n'
        '            <intent-filter>\n'
        '                <action android:name="android.intent.action.MAIN" />\n'
        '                <category android:name="android.intent.category.LAUNCHER" />\n'
        '            </intent-filter>\n'
        '        </activity>\n'
        '    </application>\n'
        '</manifest>\n',
        encoding="utf-8",
    )
    (values / "strings.xml").write_text(f'<resources><string name="app_name">{_pascal_name(name)}</string></resources>\n', encoding="utf-8")
    (values / "styles.xml").write_text(
        '<resources><style name="AppTheme" parent="android:style/Theme.Material.Light.NoActionBar" /></resources>\n',
        encoding="utf-8",
    )
    (package_path / "MainActivity.kt").write_text(
        f"package {package}\n\n"
        "import android.app.Activity\n"
        "import android.os.Bundle\n"
        "import android.widget.TextView\n\n"
        "class MainActivity : Activity() {\n"
        "    override fun onCreate(savedInstanceState: Bundle?) {\n"
        "        super.onCreate(savedInstanceState)\n"
        "        val view = TextView(this)\n"
        '        view.text = "DPSR Android"\n'
        "        view.textSize = 24f\n"
        "        setContentView(view)\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (app / "gradle.properties").write_text("org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8\n", encoding="utf-8")
    (app / ".gitignore").write_text(".gradle/\nlocal.properties\nbuild/\napp/build/\n", encoding="utf-8")


def _write_android_workflow(destination: Path) -> None:
    workflow = destination / ".github" / "workflows" / "android.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: Android\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-java@v4\n"
        "        with:\n"
        "          distribution: temurin\n"
        "          java-version: '17'\n"
        "      - uses: android-actions/setup-android@v3\n"
        "      - uses: gradle/actions/setup-gradle@v4\n"
        "        with:\n"
        f"          gradle-version: '{ANDROID_GRADLE}'\n"
        f"      - run: sdkmanager 'platforms;android-{ANDROID_COMPILE_SDK}' 'build-tools;36.0.0'\n"
        "      - run: gradle lint test assembleDebug\n"
        "        working-directory: app\n",
        encoding="utf-8",
    )


def _provision_android(destination: Path, name: str, profile: Profile) -> Profile:
    destination.mkdir(parents=True, exist_ok=True)
    _write_android_project(destination, name)
    _write_android_workflow(destination)
    return profile


def _write_ios_project(destination: Path, name: str) -> None:
    app = destination / "app"
    sources = app / "Sources"
    sources.mkdir(parents=True, exist_ok=True)
    app_name = _pascal_name(name)
    bundle = f"com.digitalparagon.{_package_suffix(name)}"
    (sources / "DpsrApp.swift").write_text(
        "import SwiftUI\n\n"
        "@main\n"
        "struct DpsrApp: App {\n"
        "    var body: some Scene {\n"
        "        WindowGroup { ContentView() }\n"
        "    }\n"
        "}\n\n"
        "struct ContentView: View {\n"
        "    var body: some View {\n"
        '        Text("DPSR iOS")\n'
        "            .font(.title)\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (app / "project.yml").write_text(
        f"name: {app_name}\n"
        "options:\n"
        "  deploymentTarget:\n"
        "    iOS: '17.0'\n"
        "targets:\n"
        f"  {app_name}:\n"
        "    type: application\n"
        "    platform: iOS\n"
        "    sources: [Sources]\n"
        "    settings:\n"
        "      base:\n"
        f"        PRODUCT_BUNDLE_IDENTIFIER: {bundle}\n"
        "        SWIFT_VERSION: 6.0\n"
        "        CODE_SIGN_STYLE: Automatic\n",
        encoding="utf-8",
    )
    workflow = destination / ".github" / "workflows" / "ios.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: iOS\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: macos-15\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: brew install xcodegen\n"
        "      - run: xcodegen generate --spec app/project.yml\n"
        "      - run: >-\n"
        f"          xcodebuild -project app/{app_name}.xcodeproj -scheme {app_name}\n"
        "          -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO\n",
        encoding="utf-8",
    )
    (destination / ".gitignore").write_text("app/*.xcodeproj/\nDerivedData/\n", encoding="utf-8")


def _provision_ios(destination: Path, name: str, profile: Profile) -> Profile:
    destination.mkdir(parents=True, exist_ok=True)
    _write_ios_project(destination, name)
    return profile


def _write_flutter_workflow(destination: Path) -> None:
    workflow = destination / ".github" / "workflows" / "flutter.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: Flutter\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  validate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: subosito/flutter-action@v2\n"
        "        with:\n"
        "          channel: stable\n"
        "          cache: true\n"
        "      - run: flutter pub get\n"
        "        working-directory: app\n"
        "      - run: flutter analyze\n"
        "        working-directory: app\n"
        "      - run: flutter test\n"
        "        working-directory: app\n"
        "      - run: flutter build web\n"
        "        working-directory: app\n",
        encoding="utf-8",
    )


def _write_react_native_workflow(destination: Path) -> None:
    workflow = destination / ".github" / "workflows" / "react-native.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: React Native\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  validate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-node@v4\n"
        "        with:\n"
        "          node-version: '22.13.0'\n"
        "          cache: npm\n"
        "          cache-dependency-path: app/package-lock.json\n"
        "      - uses: actions/setup-java@v4\n"
        "        with:\n"
        "          distribution: temurin\n"
        "          java-version: '17'\n"
        "      - uses: android-actions/setup-android@v3\n"
        "      - run: npm ci\n"
        "        working-directory: app\n"
        "      - run: npm run lint\n"
        "        working-directory: app\n"
        "      - run: npm test -- --runInBand\n"
        "        working-directory: app\n"
        "      - run: ./gradlew assembleDebug\n"
        "        working-directory: app/android\n",
        encoding="utf-8",
    )


def init_mobile_project(name: str, profile_name: str, target: Path | None = None):
    normalized = name.strip().lower()
    if not PROJECT_NAME.fullmatch(normalized):
        raise ValueError("Project name must be 2-63 lowercase letters, digits, dots, underscores, or hyphens.")
    if profile_name not in MOBILE_PROFILES:
        raise ValueError(f"Unsupported mobile profile: {profile_name}")
    profile = get_profile(profile_name)
    destination = (target or (PROJECTS_ROOT / normalized)).expanduser().resolve()
    existed = destination.exists()
    if existed and not destination.is_dir():
        raise ValueError(f"Project path is not a directory: {destination}")
    if existed and any(destination.iterdir()):
        raise ValueError(f"Project directory is not empty: {destination}")

    try:
        if profile_name == "flutter":
            profile = _provision_flutter(destination, normalized, profile)
            _write_flutter_workflow(destination)
        elif profile_name == "react-native":
            profile = _provision_react_native(destination, normalized, profile)
            _write_react_native_workflow(destination)
        elif profile_name == "android":
            profile = _provision_android(destination, normalized, profile)
        else:
            profile = _provision_ios(destination, normalized, profile)
        _write_metadata(destination, normalized, profile)
        return register_project(destination)
    except Exception:
        if not existed and _managed_destination(destination):
            shutil.rmtree(destination, ignore_errors=True)
        raise
