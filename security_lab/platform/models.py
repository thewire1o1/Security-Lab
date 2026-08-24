from __future__ import annotations

import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str = "."
    timeout: int = 900

    @classmethod
    def from_value(cls, value: Any) -> "CommandSpec":
        if isinstance(value, str):
            return cls(tuple(shlex.split(value)))
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return cls(tuple(value))
        if isinstance(value, dict):
            raw_argv = value.get("argv", [])
            if isinstance(raw_argv, str):
                argv = tuple(shlex.split(raw_argv))
            elif isinstance(raw_argv, list) and all(isinstance(item, str) for item in raw_argv):
                argv = tuple(raw_argv)
            else:
                raise ValueError("Command argv must be a string or list of strings.")
            cwd = str(value.get("cwd", "."))
            timeout = int(value.get("timeout", 900))
            if timeout < 1 or timeout > 86400:
                raise ValueError("Command timeout must be between 1 and 86400 seconds.")
            return cls(argv=argv, cwd=cwd, timeout=timeout)
        raise ValueError("Unsupported command definition.")


@dataclass(frozen=True)
class Profile:
    name: str
    title: str
    category: str
    description: str
    runner: str
    stack: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    commands: dict[str, CommandSpec] = field(default_factory=dict)
    services: dict[str, int] = field(default_factory=dict)
    scaffold: str = "generic"


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    profile: str
    runner: str
    commands: dict[str, CommandSpec]
    services: dict[str, int]
    metadata: dict[str, Any]


def load_project_manifest(path: Path) -> Project:
    manifest_path = path / "dpsr.toml"
    with manifest_path.open("rb") as handle:
        data = tomllib.load(handle)

    project = data.get("project") or {}
    runner = data.get("runner") or {}
    repository = data.get("repository") or {}
    raw_commands = data.get("commands") or {}
    services = data.get("services") or {}

    name = str(project.get("name", "")).strip()
    profile = str(project.get("profile", "generic")).strip() or "generic"
    runner_type = str(runner.get("type", "local")).strip() or "local"
    if not name:
        raise ValueError(f"Project manifest at {manifest_path} has no project.name.")
    if not isinstance(repository, dict):
        raise ValueError("Project repository metadata must be a TOML table.")

    commands = {key: CommandSpec.from_value(value) for key, value in raw_commands.items()}
    normalized_services: dict[str, int] = {}
    for key, value in services.items():
        port = int(value)
        if port < 1 or port > 65535:
            raise ValueError(f"Invalid service port for {key}: {port}")
        normalized_services[str(key)] = port

    return Project(
        name=name,
        path=path.resolve(),
        profile=profile,
        runner=runner_type,
        commands=commands,
        services=normalized_services,
        metadata={"project": project, "runner": runner, "repository": repository},
    )
