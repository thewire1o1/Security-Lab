from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .models import Project, load_project_manifest
from .paths import PROJECTS_ROOT, STATE_ROOT

REGISTRY_PATH = STATE_ROOT / "projects.json"


def _load_raw() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"version": 1, "projects": {}}
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Platform registry is invalid.")
    data.setdefault("version", 1)
    data.setdefault("projects", {})
    return data


def _write_raw(data: dict[str, Any]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    temp = REGISTRY_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(REGISTRY_PATH)


def register_project(path: Path) -> Project:
    project = load_project_manifest(path.resolve())
    data = _load_raw()
    projects = data["projects"]
    projects[project.name] = {
        "path": str(project.path),
        "profile": project.profile,
    }
    _write_raw(data)
    return project


def unregister_project(name: str) -> bool:
    data = _load_raw()
    removed = data["projects"].pop(name, None) is not None
    if removed:
        _write_raw(data)
    return removed


def list_projects() -> list[Project]:
    data = _load_raw()
    rows: list[Project] = []
    for _name, entry in sorted(data["projects"].items()):
        try:
            path = Path(str(entry["path"]))
            rows.append(load_project_manifest(path))
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            continue
    return rows


def get_project(name: str) -> Project:
    data = _load_raw()
    try:
        entry = data["projects"][name]
    except KeyError as exc:
        raise ValueError(f"Unknown project: {name}") from exc
    return load_project_manifest(Path(str(entry["path"])))


def delete_managed_project(name: str) -> Project:
    project = get_project(name)
    root = PROJECTS_ROOT.resolve()
    target = project.path.resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Only projects inside the managed DPSR project root can be deleted.") from exc
    if not relative.parts:
        raise ValueError("Refusing to delete the managed DPSR project root.")
    if not target.is_dir():
        raise ValueError(f"Managed project directory is missing: {target}")
    shutil.rmtree(target)
    if not unregister_project(name):
        raise ValueError(f"Project registry entry disappeared during deletion: {name}")
    return project
