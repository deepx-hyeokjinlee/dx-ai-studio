"""Single source of truth for studio/suite/runtime roots and path-safety.
Env vars are honored; fallbacks derive from this file's location."""
import os
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent.parent          # dx-ai-studio/
SUITE_ROOT = STUDIO_ROOT.parent                                # dx-all-suite/

def _root(env, *rel):
    v = os.environ.get(env)
    return Path(v) if v else SUITE_ROOT.joinpath(*rel)

DX_RUNTIME_ROOT = _root("DX_RUNTIME_ROOT", "dx-runtime")
DX_APP_ROOT = _root("DX_APP_ROOT", "dx-runtime", "dx_app")
DX_COMPILER_ROOT = _root("DX_COMPILER_ROOT", "dx-compiler")

def is_safe_path(target, roots) -> bool:
    try:
        rt = Path(target).resolve()
    except OSError:
        return False
    for r in roots:
        try:
            rt.relative_to(Path(r).resolve()); return True
        except ValueError:
            continue
    return False
