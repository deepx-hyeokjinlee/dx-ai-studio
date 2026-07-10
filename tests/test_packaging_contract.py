import importlib
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]

def test_pyproject_exists():
    assert (REPO / "pyproject.toml").exists()

def test_core_subpackages_import_qualified():
    for app in ["dx_app","dx_modelzoo","dx_stream","dx_compiler",
                "dx_benchmark","dx_monitor","dx_planner","dx_agent_dev"]:
        assert importlib.import_module(f"{app}.core") is not None

def test_shared_importable():
    import shared  # noqa
