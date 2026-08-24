from __future__ import annotations

import re
import secrets
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


def _write_fullstack_bridge(web: Path) -> None:
    route = web / "src" / "app" / "api" / "backend-health" / "route.ts"
    route.parent.mkdir(parents=True, exist_ok=True)
    route.write_text(
        'import { NextResponse } from "next/server";\n\n'
        'export const dynamic = "force-dynamic";\n\n'
        "export async function GET() {\n"
        '  const baseUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";\n'
        "  try {\n"
        '    const response = await fetch(`${baseUrl}/health`, { cache: "no-store" });\n'
        "    const payload = await response.json();\n"
        "    return NextResponse.json({ ok: response.ok, api: payload }, { status: response.ok ? 200 : 502 });\n"
        "  } catch {\n"
        "    return NextResponse.json({ ok: false, api: null }, { status: 503 });\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )


def _write_fullstack_files(destination: Path) -> None:
    web = destination / "apps" / "web"
    api = destination / "apps" / "api"
    (destination / "packages" / "shared").mkdir(parents=True, exist_ok=True)
    (destination / "infra").mkdir(parents=True, exist_ok=True)
    (destination / "tools").mkdir(parents=True, exist_ok=True)
    _write_fullstack_bridge(web)

    (web / "Dockerfile").write_text(
        "FROM node:22-alpine AS deps\n"
        "WORKDIR /app\n"
        "COPY package*.json ./\n"
        "RUN npm ci\n\n"
        "FROM node:22-alpine AS builder\n"
        "WORKDIR /app\n"
        "COPY --from=deps /app/node_modules ./node_modules\n"
        "COPY . .\n"
        "RUN npm run build\n\n"
        "FROM node:22-alpine AS runtime\n"
        "ENV NODE_ENV=production\n"
        "WORKDIR /app\n"
        "COPY --from=builder /app ./\n"
        "EXPOSE 3000\n"
        'CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]\n',
        encoding="utf-8",
    )
    (web / ".dockerignore").write_text("node_modules\n.next\n.git\n", encoding="utf-8")

    (api / "Dockerfile").write_text(
        "FROM python:3.13-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt ./\n"
        "RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt\n"
        "COPY src ./src\n"
        "WORKDIR /app/src\n"
        "EXPOSE 8000\n"
        'CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]\n',
        encoding="utf-8",
    )
    (api / ".dockerignore").write_text(".venv\n__pycache__\n.pytest_cache\n.git\n", encoding="utf-8")

    (destination / "compose.yaml").write_text(
        "services:\n"
        "  postgres:\n"
        "    image: postgres:17-alpine\n"
        "    environment:\n"
        "      POSTGRES_DB: dpsr\n"
        "      POSTGRES_USER: dpsr\n"
        "      POSTGRES_PASSWORD: ${DPSR_DB_PASSWORD}\n"
        "    volumes:\n"
        "      - postgres-data:/var/lib/postgresql/data\n"
        "    healthcheck:\n"
        "      test: [\"CMD-SHELL\", \"pg_isready -U dpsr -d dpsr\"]\n"
        "      interval: 5s\n"
        "      timeout: 3s\n"
        "      retries: 12\n"
        "  api:\n"
        "    build: ./apps/api\n"
        "    environment:\n"
        "      DATABASE_URL: postgresql://dpsr:${DPSR_DB_PASSWORD}@postgres:5432/dpsr\n"
        "    ports:\n"
        "      - \"8000:8000\"\n"
        "    depends_on:\n"
        "      postgres:\n"
        "        condition: service_healthy\n"
        "  web:\n"
        "    build: ./apps/web\n"
        "    environment:\n"
        "      API_INTERNAL_URL: http://api:8000\n"
        "    ports:\n"
        "      - \"3000:3000\"\n"
        "    depends_on:\n"
        "      - api\n"
        "volumes:\n"
        "  postgres-data:\n",
        encoding="utf-8",
    )

    (destination / ".env").write_text(f"DPSR_DB_PASSWORD={secrets.token_urlsafe(24)}\n", encoding="utf-8")
    (destination / ".env.example").write_text("DPSR_DB_PASSWORD=\n", encoding="utf-8")
    (destination / ".gitignore").write_text(".env\n", encoding="utf-8")
    (destination / "packages" / "shared" / "README.md").write_text(
        "# Shared packages\n\nPlace cross-application schemas, generated clients, and shared types here.\n",
        encoding="utf-8",
    )

    (destination / "tools" / "stack_check.py").write_text(
        "from __future__ import annotations\n\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "WEB = ROOT / 'apps' / 'web'\n"
        "API = ROOT / 'apps' / 'api'\n"
        "API_PYTHON = str(API / '.venv' / 'bin' / 'python')\n\n"
        "def run(argv: list[str], cwd: Path) -> int:\n"
        "    completed = subprocess.run(argv, cwd=cwd, check=False)\n"
        "    return completed.returncode\n\n"
        "def main() -> int:\n"
        "    action = sys.argv[1] if len(sys.argv) == 2 else ''\n"
        "    steps: dict[str, list[tuple[list[str], Path]]] = {\n"
        "        'lint': [\n"
        "            (['npm', 'run', 'lint'], WEB),\n"
        "            ([API_PYTHON, '-m', 'compileall', '-q', 'src', 'tests'], API),\n"
        "        ],\n"
        "        'test': [([API_PYTHON, '-m', 'pytest', '-q'], API)],\n"
        "        'build': [\n"
        "            (['npm', 'run', 'build'], WEB),\n"
        "            (['docker', 'compose', 'config', '--quiet'], ROOT),\n"
        "        ],\n"
        "    }\n"
        "    selected = steps.get(action)\n"
        "    if selected is None:\n"
        "        print('usage: stack_check.py {lint|test|build}', file=sys.stderr)\n"
        "        return 2\n"
        "    for argv, cwd in selected:\n"
        "        result = run(argv, cwd)\n"
        "        if result != 0:\n"
        "            return result\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )


def _provision_fullstack(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    _provision_nextjs(destination / "apps" / "web")
    _provision_fastapi(destination / "apps" / "api")
    _write_fullstack_files(destination)


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
        elif profile.scaffold == "fullstack-web":
            _provision_fullstack(destination)
        else:
            destination.mkdir(parents=True, exist_ok=True)
            _seed_layout(destination, profile)
        _write_platform_metadata(destination, normalized, profile)
        return register_project(destination)
    except Exception:
        if not existed and _managed_destination(destination):
            shutil.rmtree(destination, ignore_errors=True)
        raise
