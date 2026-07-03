"""Import helpers for dx_stream tests — bare ``core`` namespace is shared across modules."""
from __future__ import annotations

import sys
from pathlib import Path

_STREAM_ROOT = str(Path(__file__).resolve().parent.parent.parent / "dx_stream")


def pin_stream_core() -> None:
    """Ensure ``core.*`` resolves to dx_stream, not another module's top-level core."""
    for mod_name in list(sys.modules):
        if mod_name == "core" or mod_name.startswith("core."):
            del sys.modules[mod_name]
    while _STREAM_ROOT in sys.path:
        sys.path.remove(_STREAM_ROOT)
    sys.path.insert(0, _STREAM_ROOT)
