"""Legal fields the ModelZoo source omits but which are mechanically derivable
(copyright = source repo owner, license body = canonical SPDX text) must be filled,
without overwriting curated values. Every model should end up with a complete legal block.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "dx_modelzoo"))


def _models():
    from core import catalog as C
    return C.get_catalog()["models"]


def test_all_models_have_complete_legal_block():
    ms = _models()
    for key in ("license", "license_text", "copyright", "source_url"):
        missing = [m["id"] for m in ms if not (m.get("legal") or {}).get(key)]
        assert not missing, f"{key} missing for: {missing[:10]}"


def test_copyright_derived_from_source_repo_owner():
    ms = {m["id"]: m for m in _models()}
    assert ms["deitbase384_hug"]["legal"]["copyright"] == "Facebook"      # huggingface.co/facebook
    assert ms["yolov7_w6"]["legal"]["copyright"] == "WongKinYiu"          # curated, preserved
    assert ms["osnet0_25"]["legal"]["copyright"] == "KaiyangZhou"         # github owner


def test_license_text_is_canonical_reference():
    ms = {m["id"]: m for m in _models()}
    assert "apache.org/licenses/LICENSE-2.0" in ms["deitbase384_hug"]["legal"]["license_text"]
    assert "gpl-3.0" in ms["yolov7_w6"]["legal"]["license_text"]
