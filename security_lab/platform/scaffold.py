from __future__ import annotations

import re
from pathlib import Path

from .models import CommandSpec, Profile
from .paths import PROJECTS_ROOT
from .profiles import get_profile
from .registry import register_project

PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")


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


def init_project(name: str, profile_name: str, target: Path | None = None):
    normalized = name.strip().lower()
    if not PROJECT_NAME.fullmatch(normalized):
        raise ValueError("Project name must be 2-63 lowercase letters, digits, dots, underscores, or hyphens.")
    profile = get_profile(profile_name)
    destination = (target or (PROJECTS_ROOT / normalized)).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Project directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    _seed_layout(destination, profile)
    (destination / "dpsr.toml").write_text(render_manifest(normalized, profile), encoding="utf-8")
    (destination / "README.md").write_text(
        f"# {normalized}\n\nDPSR profile: `{profile.name}`\n\n{profile.description}\n",
        encoding="utf-8",
    )
    return register_project(destination)
