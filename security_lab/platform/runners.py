from __future__ import annotations

import os
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .models import CommandSpec, Project


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Runner:
    name = "base"

    def run(self, project: Project, command: CommandSpec) -> RunResult:
        raise NotImplementedError

    @staticmethod
    def _cwd(project: Project, relative: str) -> Path:
        target = (project.path / relative).resolve()
        try:
            target.relative_to(project.path)
        except ValueError as exc:
            raise ValueError("Command cwd escapes project root.") from exc
        if not target.is_dir():
            raise ValueError(f"Command cwd does not exist: {relative}")
        return target


class LocalRunner(Runner):
    name = "local"

    def run(self, project: Project, command: CommandSpec) -> RunResult:
        if not command.argv:
            raise ValueError("Command argv is empty.")
        result = subprocess.run(  # nosec B603
            list(command.argv),
            cwd=self._cwd(project, command.cwd),
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=command.timeout,
            check=False,
        )
        return RunResult(result.returncode, result.stdout, result.stderr)


class DockerRunner(Runner):
    name = "docker"

    def run(self, project: Project, command: CommandSpec) -> RunResult:
        runner = project.metadata.get("runner") or {}
        image = str(runner.get("image", "")).strip()
        if not image:
            raise ValueError("Docker runner requires runner.image in dpsr.toml.")
        if not command.argv:
            raise ValueError("Command argv is empty.")

        workdir = Path("/workspace") / command.cwd
        argv = [
            "docker",
            "run",
            "--rm",
            "--init",
            "-v",
            f"{project.path}:/workspace",
            "-w",
            str(workdir),
            image,
            *command.argv,
        ]
        result = subprocess.run(  # nosec B603
            argv,
            cwd=project.path,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=command.timeout,
            check=False,
        )
        return RunResult(result.returncode, result.stdout, result.stderr)


RUNNERS: Mapping[str, type[Runner]] = {
    LocalRunner.name: LocalRunner,
    DockerRunner.name: DockerRunner,
}


def get_runner(name: str) -> Runner:
    try:
        return RUNNERS[name]()
    except KeyError as exc:
        available = ", ".join(sorted(RUNNERS))
        raise ValueError(f"Runner '{name}' is not locally executable. Available: {available}") from exc
