#!/usr/bin/env python3
"""Exhaustive dx_stream Pipeline-BUILDER streaming verification.

Runs every meaningful (model x structure) combination through the SAME path the
GUI Pipeline Builder uses — ``core.pipeline.pipeline_json_to_gst(builder_json)``
— then streams it headlessly (gst-launch -> JPEG frame on fd 1) and records
PASS/FAIL/SKIP. A produced JPEG frame proves the full chain actually ran on the
NPU (decode -> dxpreprocess -> dxinfer -> dxpostprocess -> dxosd -> encode).

WHY per-combo service restart:
  Tearing a pipeline down can crash/destabilise the dxrtd daemon, and NPU
  Device 1 (FW v2.7.0) intermittently hits "Firmware Timeout / Device not
  response" under load. To get UNCONTAMINATED per-combo truth we restart
  dxrt.service before each run (needs passwordless `sudo systemctl restart
  dxrt.service`). Without this, a single bad combo cascades into false failures.

PRECONDITIONS (run only when BOTH NPUs are free — no other agent using them):
  - `sudo -n systemctl restart dxrt.service` must work (passwordless), OR pass
    --no-restart to skip isolation (results then subject to cascade noise).
  - dx-runtime/dx_stream built; models in samples/models; postproc libs in
    /usr/local/share/gstdxstream/lib; NPU present (/dev/dxrt*).

USAGE:
  python3 verify_all_streaming.py --full          # every (model x structure) ~120 combos, ~80 min
  python3 verify_all_streaming.py --quick         # representative ~20 combos
  python3 verify_all_streaming.py --no-restart    # skip per-combo dxrt restart (faster, noisier)
  python3 verify_all_streaming.py --timeout 30    # first-frame timeout per combo (s)

OUTPUT: writes a timestamped report (md + csv) next to this script.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DX_STREAM = HERE.parent
sys.path.insert(0, str(DX_STREAM))

from core import mjpeg                                      # noqa: E402
from core.pipeline import pipeline_json_to_gst, detect_encoder  # noqa: E402
from core.config import VIDEOS_DIR, MODELS_DIR             # noqa: E402
from core.mjpeg import get_sink_str, build_mjpeg_pipeline  # noqa: E402

LIB = "/usr/local/share/gstdxstream/lib"

# ── model -> (postproc, task, input_size) ────────────────────────────────────
# postproc is either ("lib", "<lib_basename>", "<func>") or ("config", "<dir>", None)
M = {
    "yolo26n.dxnn":          (("lib", "yolo26od", "PostProcess"),     "od",       (640, 640)),
    "YOLOV11N.dxnn":         (("lib", "yolov11", "PostProcess"),      "od",       (640, 640)),
    "YoloV5S.dxnn":          (("lib", "yolov5s_6", "PostProcess"),    "od",       (640, 640)),
    "YoloV7.dxnn":           (("lib", "yolov7", "PostProcess"),       "od",       (640, 640)),
    "YoloV8N.dxnn":          (("lib", "yolov8n", "PostProcess"),      "od",       (640, 640)),
    "YoloV9S.dxnn":          (("lib", "yolov9s", "PostProcess"),      "od",       (640, 640)),
    "YoloXS.dxnn":           (("lib", "yoloxs", "PostProcess"),       "od",       (640, 640)),
    "YOLOv5s_Face.dxnn":     (("lib", "yolov5s_face", "PostProcess"), "face",     (640, 640)),
    "SCRFD500M.dxnn":        (("lib", "scrfd500m", "PostProcess"),    "face",     (640, 640)),
    "yolo26n-pose.dxnn":     (("lib", "yolo26pose", "PostProcess"),   "pose",     (640, 640)),
    "yolov8m_pose.dxnn":     (("lib", "yolov8m_pose", "PostProcess"), "pose",     (640, 640)),
    "yolo26n-seg.dxnn":      (("lib", "yolo26seg", "PostProcess"),    "seg",      (640, 640)),
    "EfficientNet_Lite0.dxnn": (("lib", "object_class", "PostProcess"), "cls",    (224, 224)),
    "YoloV5S_PPU.dxnn":      (("config", "YoloV5S_PPU", None),        "od-ppu",   None),
    "SCRFD500M_PPU.dxnn":    (("lib", "ppu", "SCRFD500M_PPU"),        "face-ppu", (640, 640)),
    "YOLOV5Pose_PPU.dxnn":   (("lib", "ppu", "YOLOV5Pose_PPU"),       "pose-ppu", (640, 640)),
}

VIDS = sorted(f"file://{p}" for p in VIDEOS_DIR.glob("*.mp4")) or [
    f"file://{VIDEOS_DIR}/boat.mp4"]
V0 = VIDS[0]


# ── builder-JSON helpers (mirror the GUI Pipeline Builder node/edge shape) ────
def _nodes_edges(seq):
    nodes, edges = [], []
    for i, (t, p) in enumerate(seq):
        nid = f"n{i}"
        nodes.append({"id": nid, "type": t, "properties": p})
        if i:
            edges.append({"from": f"n{i-1}", "to": nid})
    return nodes, edges


def _infer_block(model):
    """Return the [pre, infer, post] node specs for a model (standard or PPU-config)."""
    pp, task, size = M[model]
    if pp[0] == "config":
        cfg = pp[1]
        return [
            ("DxPreprocess", {"config-file-path": f"{cfg}/preprocess_config.json"}),
            ("DxInfer", {"config-file-path": f"{cfg}/inference_config.json"}),
            ("DxPostprocess", {"config-file-path": f"{cfg}/postprocess_config.json"}),
        ], task
    w, h = size
    _, lib, func = pp
    return [
        ("DxPreprocess", {"preprocess-id": 1, "resize-width": w, "resize-height": h}),
        ("DxInfer", {"preprocess-id": 1, "inference-id": 1, "model-path": str(MODELS_DIR / model)}),
        ("DxPostprocess", {"inference-id": 1,
                           "library-file-path": f"{LIB}/libpostprocess_{lib}.so",
                           "function-name": func}),
    ], task


# ── structure builders: each returns builder-JSON {nodes, edges} ─────────────
def s_linear(model, tail=None):
    blk, _ = _infer_block(model)
    seq = [("urisourcebin", {"uri": V0}), ("decodebin", {})] + blk + [("DxOsd", {})] + (tail or [])
    n, e = _nodes_edges(seq)
    return {"nodes": n, "edges": e}


def s_tracker(model):
    blk, _ = _infer_block(model)
    seq = [("urisourcebin", {"uri": V0}), ("decodebin", {})] + blk + \
          [("DxTracker", {"config-file-path": "tracker_config.json"}), ("DxOsd", {})]
    n, e = _nodes_edges(seq)
    return {"nodes": n, "edges": e}


def s_multi(model, ch):
    nodes, edges = [], []
    for i in range(ch):
        pfx = f"s{i}_"
        blk, _ = _infer_block(model)
        seq = [("urisourcebin", {"uri": VIDS[i % len(VIDS)]}), ("decodebin", {})] + blk + \
              [("DxOsd", {}), ("DxScale", {"width": 640, "height": 360})]
        for j, (t, p) in enumerate(seq):
            nid = f"{pfx}{j}"
            nodes.append({"id": nid, "type": t, "properties": p})
            if j:
                edges.append({"from": f"{pfx}{j-1}", "to": nid})
        edges.append({"from": f"{pfx}{len(seq)-1}", "to": "comp"})
    nodes.append({"id": "comp", "type": "compositor", "properties": {}})
    return {"nodes": nodes, "edges": edges}


def build_matrix(full):
    """Yield (label, builder_json). `full` -> every model x structure; else representative."""
    combos = []
    models = list(M.keys())
    rep_models = ["yolo26n.dxnn", "YoloV5S_PPU.dxnn", "YOLOv5s_Face.dxnn",
                  "SCRFD500M_PPU.dxnn", "yolo26n-pose.dxnn", "yolo26n-seg.dxnn",
                  "EfficientNet_Lite0.dxnn"]
    use = models if full else rep_models

    # 1) linear per model
    for m in use:
        combos.append((f"linear::{m}", s_linear(m)))
    # 2) tail variants (scale/rate/convert) per model
    if full:
        for m in use:
            combos.append((f"linear+scale::{m}", s_linear(m, [("DxScale", {"width": 960, "height": 540})])))
            combos.append((f"linear+rate::{m}", s_linear(m, [("DxRate", {"rate": 15})])))
            combos.append((f"linear+convert::{m}", s_linear(m, [("DxConvert", {})])))
    else:
        combos.append(("linear+scale::yolo26n.dxnn", s_linear("yolo26n.dxnn", [("DxScale", {"width": 960, "height": 540})])))
        combos.append(("linear+rate::yolo26n.dxnn", s_linear("yolo26n.dxnn", [("DxRate", {"rate": 15})])))
    # 3) tracker (detection models)
    for m in (use if full else ["YoloV5S_PPU.dxnn"]):
        if M[m][1] in ("od", "od-ppu", "face", "face-ppu"):
            combos.append((f"tracker::{m}", s_tracker(m)))
    # 4) multistream 2ch + 4ch
    for m in (use if full else ["YoloV5S_PPU.dxnn", "yolo26n.dxnn"]):
        combos.append((f"multi2ch::{m}", s_multi(m, 2)))
        if full:
            combos.append((f"multi4ch::{m}", s_multi(m, 4)))
    return combos


# ── runner ───────────────────────────────────────────────────────────────────
def restart_service():
    try:
        subprocess.run(["sudo", "-n", "systemctl", "restart", "dxrt.service"],
                       check=False, capture_output=True, timeout=30)
    except Exception:
        return False
    # wait for active
    for _ in range(20):
        r = subprocess.run(["systemctl", "is-active", "dxrt.service"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "active":
            time.sleep(4)
            return True
        time.sleep(1)
    return False


def run_combo(label, defn, timeout, restart):
    try:
        gst = pipeline_json_to_gst(defn)
    except Exception as e:
        return ("BUILD_FAIL", str(e)[:300], None)
    src_req = sum(1 for n in defn["nodes"] if n["type"] in ("urisourcebin", "rtspsrc"))
    src_got = gst.count("urisourcebin") + gst.count("rtspsrc")
    struct = "" if src_req == src_got else f" [STRUCT {src_got}/{src_req} src]"
    run_str = gst + " ! " + get_sink_str() if "fdsink" not in gst and "sink" not in gst.split()[-1] \
        else build_mjpeg_pipeline(gst)
    if restart:
        restart_service()
    t0 = time.time()
    mjpeg.start(run_str)
    ready, error = mjpeg.wait_until_ready(timeout=timeout, require_frame=True)
    lat = round(time.time() - t0, 1)
    mjpeg.stop()
    status = "PASS" if ready else "FAIL"
    detail = (f"{lat}s" if ready else (error or "no frame")[:300]) + struct
    return (status, detail, lat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="every model x structure (~120)")
    ap.add_argument("--quick", action="store_true", help="representative subset (~20)")
    ap.add_argument("--no-restart", action="store_true", help="skip per-combo dxrt restart")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()
    full = args.full or not args.quick

    combos = build_matrix(full)
    restart = not args.no_restart
    print(f"== exhaustive streaming verification: {len(combos)} combos, "
          f"restart={'on' if restart else 'OFF'}, timeout={args.timeout}s ==", flush=True)

    results = []
    for i, (label, defn) in enumerate(combos, 1):
        print(f"[{i}/{len(combos)}] {label} ...", flush=True)
        status, detail, lat = run_combo(label, defn, args.timeout, restart)
        results.append((label, status, detail))
        print(f"    {status} — {detail}", flush=True)

    # report
    stamp = time.strftime("%Y%m%d-%H%M%S")
    md = HERE / f"report-{stamp}.md"
    csv = HERE / f"report-{stamp}.csv"
    npass = sum(1 for _, s, _ in results if s == "PASS")
    lines = [f"# dx_stream streaming verification — {stamp}", "",
             f"{npass}/{len(results)} PASS  (restart={'on' if restart else 'off'})", "",
             "| # | combo | result | detail |", "|---|---|---|---|"]
    for i, (label, status, detail) in enumerate(results, 1):
        lines.append(f"| {i} | `{label}` | {status} | {detail} |")
    md.write_text("\n".join(lines))
    csv.write_text("combo,result,detail\n" +
                   "\n".join(f'"{l}",{s},"{d}"' for l, s, d in results))
    print(f"\n{npass}/{len(results)} PASS", flush=True)
    print(f"report: {md}", flush=True)


if __name__ == "__main__":
    main()
