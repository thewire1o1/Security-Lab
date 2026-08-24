from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from security_lab.common import ROOT

from .models import CommandSpec, Profile

PROFILE_ROOT = ROOT / "platform" / "profiles"


def _profile_from_dict(data: dict[str, Any]) -> Profile:
    meta = data.get("profile") or {}
    name = str(meta.get("name", "")).strip()
    if not name:
        raise ValueError("Profile is missing profile.name.")
    commands = {
        str(key): CommandSpec.from_value(value)
        for key, value in (data.get("commands") or {}).items()
    }
    services: dict[str, int] = {}
    for key, value in (data.get("services") or {}).items():
        services[str(key)] = int(value)
    return Profile(
        name=name,
        title=str(meta.get("title", name)),
        category=str(meta.get("category", "development")),
        description=str(meta.get("description", "")),
        runner=str(meta.get("runner", "local")),
        stack=tuple(str(item) for item in meta.get("stack", [])),
        capabilities=tuple(str(item) for item in meta.get("capabilities", [])),
        commands=commands,
        services=services,
        scaffold=str(meta.get("scaffold", "generic")),
    )


def load_profiles(root: Path = PROFILE_ROOT) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    if not root.exists():
        return profiles
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = _profile_from_dict(data)
        if profile.name in profiles:
            raise ValueError(f"Duplicate profile name: {profile.name}")
        profiles[profile.name] = profile
    return profiles


def get_profile(name: str) -> Profile:
    profiles = load_profiles()
    try:
        return profiles[name]
    except KeyError as exc:
        available = ", ".join(sorted(profiles)) or "none"
        raise ValueError(f"Unknown profile '{name}'. Available: {available}") from exc
