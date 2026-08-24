from __future__ import annotations

import re

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_INVALID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def normalize_slug(raw: str) -> str:
    candidate = _INVALID_RE.sub("-", raw.strip()).strip("-")
    if not _SLUG_RE.fullmatch(candidate):
        raise ValueError("name must start with an alphanumeric character and contain only letters, digits, '.', '_' or '-'")
    return candidate
