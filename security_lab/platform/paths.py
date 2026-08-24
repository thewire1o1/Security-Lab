from __future__ import annotations

import os
from pathlib import Path

WORKSPACES = Path("/workspaces")
PERSISTENT_ROOT = WORKSPACES if WORKSPACES.is_dir() else Path.home()
STATE_ROOT = Path(
    os.environ.get("DPSR_PLATFORM_STATE", str(PERSISTENT_ROOT / ".dpsr" / "platform"))
).expanduser()
PROJECTS_ROOT = Path(
    os.environ.get("DPSR_PROJECTS_ROOT", str(PERSISTENT_ROOT / "dpsr-projects"))
).expanduser()
