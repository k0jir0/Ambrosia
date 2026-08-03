from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Do not let ignored developer/demo runtime state influence test collection.
_TEST_SIGNAL_STATE_PATH = Path(tempfile.gettempdir()) / f"ambrosia-signal-state-{os.getpid()}.json"
os.environ.setdefault("AMBROSIA_SIGNAL_STATE_PATH", str(_TEST_SIGNAL_STATE_PATH))


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    if os.getenv("AMBROSIA_SIGNAL_STATE_PATH") == str(_TEST_SIGNAL_STATE_PATH):
        _TEST_SIGNAL_STATE_PATH.unlink(missing_ok=True)
