from __future__ import annotations

import re
import shutil
from pathlib import Path

from security_lab.common import run_command

from .models import CommandSpec, Profile
from .paths import PROJECTS_ROOT
from .profiles import get_profile
from .registry import register_project

PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")
NODE_VERSION = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?")
MINIMUM_NEXT_NODE = (20, 9)


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


def render_manifest(name: str, profile: Profile) -> str:
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


def _ensure_next_prerequisites() -> None:
    version = _node_version()
    if version[:2] < MINIMUM_NEXT_NODE:
        actual = ".".join(str(part) for part in version)
        raise ValueError(f"Next.js requires Node.js 20.9 or newer; found {actual}.")


def _provision_nextjs(destination: Path) -> None:
    _ensure_next_prerequisites()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.rmdir()
    argv = (
        "npx",
        "--yes",
        "create-next-app@latest",
        str(destination),
        "--ts",
        "--eslint",
        "--tailwind",
        "--app",
        "--src-dir",
        "--turbopack",
        "--import-alias",
        "@/*",
        "--use-npm",
        "--disable-git",
        "--yes",
    )
    result = run_command(
        argv,
        cwd=destination.parent,
        timeout=1200,
        stdout_limit=24_000,
        stderr_limit=12_000,
    )
    if result["returncode"] != 0:
        raise _command_failure("Next.js provisioning", result)
    required = (destination / "package.json", destination / "src" / "app")
    if not required[0].is_file() or not required[1].is_dir():
        raise ValueError("Next.js provisioning completed without the expected package.json and src/app layout.")


def _write_fastapi_source(destination: Path) -> None:
    (destination / "src").mkdir(parents=True, exist_ok=True)
    (destination / "tests").mkdir(parents=True, exist_ok=True)
    (destination / "src" / "main.py").write_text(
        "from fastapi import FastAPI\n\n"
        "app = FastAPI(title=\"DPSR FastAPI Service\")\n\n"
        "@app.get(\"/health\")\n"
        "def health() -> dict[str, str]:\n"
        "    return {\"status\": \"ok\"}\n",
        encoding="utf-8",
    )
    (destination / "tests" / "test_health.py").write_text(
        "from fastapi.testclient import TestClient\n\n"
        "from src.main import app\n\n"
        "client = TestClient(app)\n\n"
        "def test_health() -> None:\n"
        "    response = client.get(\"/health\")\n"
        "    assert response.status_code == 200\n"
        "    assert response.json() == {\"status\": \"ok\"}\n",
        encoding="utf-8",
    )
    (destination / "requirements.txt").write_text(
        "fastapi>=0.116,<1\n"
        "uvicorn[standard]>=0.35,<1\n"
        "pytest>=8,<10\n"
        "httpx>=0.28,<1\n",
        encoding="utf-8",
    )
    (destination / ".gitignore").write_text(
        ".venv/\n__pycache__/\n.pytest_cache/\n*.py[cod]\n.env\n",
        encoding="utf-8",
    )


def _provision_fastapi(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    _write_fastapi_source(destination)
    venv = run_command(("python3", "-m", "venv", str(destination / ".venv")), cwd=destination, timeout=120)
    if venv["returncode"] != 0:
        raise _command_failure("FastAPI virtual environment creation", venv)
    pip = destination / ".venv" / "bin" / "python"
    install = run_command(
        (str(pip), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements.txt"),
        cwd=destination,
        timeout=600,
        stdout_limit=12_000,
        stderr_limit=12_000,
    )
    if install["returncode"] != 0:
        raise _command_failure("FastAPI dependency installation", install)


def _seed_layout(target: Path, profile: Profile) -> None:
    scaffold = profile.scaffold
    if scaffold == "fullstack-web":
        for relative in ("apps/web", "apps/api", "packages/shared", "infra"):
            (target / relative).mkdir(parents=True, exist_ok=True)
    elif scaffold in {"nextjs", "fastapi"}:
        (target / "src").mkdir(parents=True, exist_ok=True)
    elif scaffold in {"flutter", "react-native", "android", "ios"}:
        (target / "app").mkdir(parents=True, exist_ok=True)
    else:
        (target / "src").mkdir(parents=True, exist_ok=True)


def _write_platform_metadata(destination: Path, name: str, profile: Profile) -> None:
    (destination / "dpsr.toml").write_text(render_manifest(name, profile), encoding="utf-8")
    marker = f"\n## DPSR\n\nManaged profile: `{profile.name}`.\n\n{profile.description}\n"
    readme = destination / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace").rstrip()
        if "## DPSR" not in text:
            readme.write_text(text + marker, encoding="utf-8")
    else:
        readme.write_text(f"# {name}\n" + marker, encoding="utf-8")


def _managed_destination(destination: Path) -> bool:
    try:
        destination.relative_to(PROJECTS_ROOT.resolve())
        return True
    except ValueError:
        return False


def init_project(name: str, profile_name: str, target: Path | None = None):
    normalized = name.strip().lower()
    if not PROJECT_NAME.fullmatch(normalized):
        raise ValueError("Project name must be 2-63 lowercase letters, digits, dots, underscores, or hyphens.")
    profile = get_profile(profile_name)
    destination = (target or (PROJECTS_ROOT / normalized)).expanduser().resolve()
    existed = destination.exists()
    if existed and not destination.is_dir():
        raise ValueError(f"Project path is not a directory: {destination}")
    if existed and any(destination.iterdir()):
        raise ValueError(f"Project directory is not empty: {destination}")

    try:
        if profile.scaffold == "nextjs":
            _provision_nextjs(destination)
        elif profile.scaffold == "fastapi":
            _provision_fastapi(destination)
        else:
            destination.mkdir(parents=True, exist_ok=True)
            _seed_layout(destination, profile)
        _write_platform_metadata(destination, normalized, profile)
        return register_project(destination)
    except Exception:
        if not existed and _managed_destination(destination):
            shutil.rmtree(destination, ignore_errors=True)
        raise
