"""dx_app tests import isolation."""
import sys
from pathlib import Path

_APP_ROOT = str(Path(__file__).resolve().parent.parent.parent / "dx_app")
_APP_CORE = str(Path(__file__).resolve().parent.parent.parent / "dx_app/core")


def _clear_bare_modules():
    for mod_name in list(sys.modules):
        if mod_name in ("core", "server", "config") or mod_name.startswith(("core.", "server.")):
            del sys.modules[mod_name]


def _remove_paths(paths):
    for path in paths:
        while path in sys.path:
            sys.path.remove(path)


def _pin_paths():
    for path in (_APP_CORE, _APP_ROOT):
        if path not in sys.path:
            sys.path.insert(0, path)
        elif sys.path[0] != path:
            sys.path.remove(path)
            sys.path.insert(0, path)


def pytest_runtest_setup(item):
    _clear_bare_modules()
    _pin_paths()


def pytest_runtest_teardown(item, nextitem):
    _clear_bare_modules()
    _remove_paths([_APP_ROOT, _APP_CORE])
