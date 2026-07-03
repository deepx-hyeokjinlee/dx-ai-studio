"""The 11 models the source left sparse now carry params/ops/accuracy, researched from
upstream (GitHub/HF/papers) or mirrored from an exact DEEPX sibling. Guards the values and
the CAS-ViT license correction (was wrongly Apache-2.0; the repo LICENSE is MIT)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "dx_modelzoo"))


def _ms():
    from core import catalog as C
    return {m["id"]: m for m in C.get_catalog()["models"]}


def _raw(m):
    return ((m.get("evaluation") or {}).get("raw") or {}).get("accuracy")


def test_casvit_license_is_mit_not_apache():
    ms = _ms()
    for v in ("casvit_xs", "casvit_s", "casvit_t", "casvit_m"):
        assert ms[v]["legal"]["license"] == "MIT", f"{v} license must be MIT (repo LICENSE)"


def test_sparse_cluster_has_params_ops_accuracy():
    ms = _ms()
    expect = {
        "casvit_xs": ("3.2", "0.56", "77.5"),
        "casvit_t": ("21.76", "3.6", "82.3"),
        "vitb32": ("88.22", "4.41", "75.912"),
        "efficientformerv2_l": ("26.1", "5.12", "83.5"),
        "yolov7_w6": ("70.4", "180", "54.6"),
    }
    for mid, (p, o, a) in expect.items():
        s = ms[mid].get("specification") or {}
        assert s.get("parameters") == p and s.get("operations") == o, mid
        assert _raw(ms[mid]) == a, mid


def test_yolov5pose_source_corrected_to_ti():
    # upstream is TI edgeai-yolov5 (yolo-pose), not ultralytics
    assert "TexasInstruments/edgeai-yolov5" in _ms()["yolov5pose_ppu"]["legal"]["source_url"]
