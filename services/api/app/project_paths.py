from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Locate the repository root or the equivalent root in a runtime image."""
    configured_root = os.getenv("AMBROSIA_PROJECT_ROOT")
    if configured_root:
        return Path(configured_root).expanduser().resolve()

    source = (start or Path(__file__)).resolve()
    current = source if source.is_dir() else source.parent
    for candidate in (current, *current.parents):
        if (candidate / "infra" / "db").is_dir():
            return candidate

    # A compact image installs this module at /app/app/project_paths.py. Keep
    # that layout usable even if a future image omits the repository markers.
    return current.parent if current.name == "app" else current


PROJECT_ROOT = find_project_root()
