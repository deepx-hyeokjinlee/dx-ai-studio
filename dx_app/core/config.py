"""DX-APP Configuration — shared constants, paths, and state."""
import os,sys,re,json,time,base64,signal,shutil,hashlib,platform,tempfile
import subprocess,threading,webbrowser,mimetypes,collections
from http.server import HTTPServer,SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse,parse_qs
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed

SCRIPT_DIR  = Path(__file__).resolve().parent.parent   # dx_app/ (one level above core/)
_SHARED_DIR = SCRIPT_DIR.parent / "shared"
if _SHARED_DIR.is_dir() and str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
_NPU_STATS_BIN = SCRIPT_DIR / "dx_npu_stats"
_SUITE_ROOT = SCRIPT_DIR.parent.parent                 # dx-all-suite/
DX_APP_ROOT = Path(os.environ["DX_APP_ROOT"]) if os.environ.get("DX_APP_ROOT") \
    else _SUITE_ROOT / "dx-runtime" / "dx_app"
CPP_DIR     = DX_APP_ROOT/"src"/"cpp_example"
PY_DIR      = DX_APP_ROOT/"src"/"python_example"
ASSETS_DIR  = DX_APP_ROOT/"assets"
SAMPLE_DIR  = DX_APP_ROOT/"sample"
CONFIG_FILE = DX_APP_ROOT/"config"/"test_models.conf"
BUILD_DIR   = DX_APP_ROOT/"build_x86_64"/"src"/"cpp_example"
SCRIPTS_DIR = DX_APP_ROOT/"scripts"
SERVER_NAME = "DX App"
STATIC_DIR  = SCRIPT_DIR/"static"
TEMPLATES_DIR = SCRIPT_DIR/"templates"
OUTPUTS_DIR = SCRIPT_DIR/"outputs"
OUTPUTS_DIR.mkdir(parents=True,exist_ok=True)

SKIP_CAT={"common","build","sample","__pycache__","utils","factory"}
_HARDCODED_CATEGORIES=["object_detection","face_detection","pose_estimation","obb_detection",
 "classification","instance_segmentation","semantic_segmentation","depth_estimation",
 "image_denoising","super_resolution","image_enhancement","embedding","ppu",
 "face_alignment","hand_landmark","object_detection_x_semantic_segmentation"]
_VIRTUAL_CATEGORIES={"object_detection_x_semantic_segmentation"}

def _scan_categories():
    cats=set(_HARDCODED_CATEGORIES)
    for base in[CPP_DIR,PY_DIR]:
        if base.is_dir():
            for d in base.iterdir():
                if d.is_dir() and d.name not in SKIP_CAT:
                    cats.add(d.name)
    cats|=_VIRTUAL_CATEGORIES
    return sorted(cats)

CATEGORIES=_scan_categories()
print(f"[INFO] Dynamic scan: {len(CATEGORIES)} categories found: {', '.join(CATEGORIES)}")
_CAT_LABEL_OVERRIDES={"object_detection_x_semantic_segmentation":"ObjDet × SegSem",
 "ppu":"PPU","obb_detection":"OBB Detection"}
def _make_label(c):
    if c in _CAT_LABEL_OVERRIDES:return _CAT_LABEL_OVERRIDES[c]
    return c.replace("_"," ").title()
CAT_LABEL={c:_make_label(c) for c in CATEGORIES}
_DEFAULT_IMAGE="sample/img/sample_street.jpg"
_DEFAULT_VIDEO="assets/videos/dance-group.mov"
_CAT_IMAGE_OVERRIDES={"object_detection":"sample/img/sample_street.jpg",
 "face_detection":"sample/img/sample_face.jpg",
 "pose_estimation":"sample/img/sample_people.jpg","obb_detection":"sample/img/sample_parking.jpg",
 "classification":"sample/img/sample_dog.jpg","instance_segmentation":"sample/img/sample_street.jpg",
 "semantic_segmentation":"sample/img/sample_horse.jpg","depth_estimation":"sample/img/sample_kitchen.jpg",
 "image_denoising":"sample/img/sample_denoising.jpg","super_resolution":"sample/img/sample_superresolution.png",
 "image_enhancement":"sample/img/sample_lowlight.jpg","embedding":"sample/img/face_pair",
 "reid":"sample/img/person_pair",
 "ppu":"sample/img/sample_face.jpg","face_alignment":"sample/img/sample_face.jpg",
 "hand_landmark":"sample/img/sample_hand.jpg",
 "attribute_recognition":"sample/img/sample_person_a1.jpg",
 "object_detection_x_semantic_segmentation":"sample/img/sample_parking.jpg"}
_CAT_VIDEO_OVERRIDES={"face_detection":"assets/videos/dance-solo.mov",
 "pose_estimation":"assets/videos/dance-solo.mov","obb_detection":"assets/videos/dron-citry-road.mov",
 "semantic_segmentation":"assets/videos/blackbox-city-road.mp4",
 "face_alignment":"assets/videos/dance-solo.mov","hand_landmark":"assets/videos/dance-solo.mov",
 "object_detection_x_semantic_segmentation":"assets/videos/blackbox-city-road.mp4"}
CAT_IMAGE={c:_CAT_IMAGE_OVERRIDES.get(c,_DEFAULT_IMAGE) for c in CATEGORIES}
CAT_VIDEO={c:_CAT_VIDEO_OVERRIDES.get(c,_DEFAULT_VIDEO) for c in CATEGORIES}
_TASK_TYPES_EXCLUDE={"face_alignment","hand_landmark","object_detection_x_semantic_segmentation"}
TASK_TYPES=[c for c in CATEGORIES if c not in _TASK_TYPES_EXCLUDE]
POSTPROCESSORS={"object_detection":["yolov5","yolov7","yolov8","yolov9","yolov10","yolov11",
 "yolov12","yolov26","yolox","ssd","nanodet","damoyolo","centernet","efficientdet"],
 "classification":["efficientnet"],"semantic_segmentation":["bisenetv1","bisenetv2","deeplabv3","segformer"],
 "instance_segmentation":["yolov5seg","yolov8seg","yolact"],
 "pose_estimation":["yolov5pose","yolov8pose","centerpose"],
 "face_detection":["scrfd","retinaface","ulfg","yolov5face","yolov7face"],
 "obb_detection":["obb"],"depth_estimation":["fastdepth"],"image_denoising":["dncnn"],
 "super_resolution":["espcn"],"image_enhancement":["zero_dce"],
 "embedding":["arcface","clip_image","clip_text"],"ppu":["yolov5_ppu","yolov7_ppu","yolov5pose_ppu","scrfd_ppu"]}
for _cat in CATEGORIES:
    if _cat not in POSTPROCESSORS:
        POSTPROCESSORS[_cat]=[]
# ── State ─────────────────────────────────────────────────────────────────────
_running_proc=None; _proc_lock=threading.Lock()
_recent_runs=collections.deque(maxlen=50); _history_lock=threading.Lock()
_lab_sessions=collections.OrderedDict(); _lab_lock=threading.Lock()
_LAB_SESSION_MAX=256
_LAB_SESSION_TTL_SECONDS=8*60*60
_HEARTBEAT=time.time(); _HB_TIMEOUT=3600  # 1 hour — prevents premature shutdown during long sessions

# ── External module roots (diagnostics / cross-module references) ─────────────
DX_COMPILER_ROOT = Path(os.environ["DX_COMPILER_ROOT"]) if os.environ.get("DX_COMPILER_ROOT") \
    else _SUITE_ROOT / "dx-compiler"
DX_COMPILER_VENV = DX_COMPILER_ROOT / "venv-dx-compiler-local"
DX_RUNTIME_ROOT = Path(os.environ["DX_RUNTIME_ROOT"]) if os.environ.get("DX_RUNTIME_ROOT") \
    else _SUITE_ROOT / "dx-runtime"
DX_RT_ROOT = DX_RUNTIME_ROOT / "dx_rt"
DX_DRIVER_ROOT = DX_RUNTIME_ROOT / "dx_rt_npu_linux_driver"
for _name, _path in [("DX_APP_ROOT", DX_APP_ROOT), ("DX_COMPILER_ROOT", DX_COMPILER_ROOT),
                      ("DX_RUNTIME_ROOT", DX_RUNTIME_ROOT)]:
    if not _path.is_dir():
        print(f"[WARNING] {_name} not found: {_path}")
        print(f"[WARNING] Set {_name} environment variable to override")
# Generic background setup-step subprocess state (used by setup_steps.py — NOT compiler).
_comp_proc=None; _comp_lock=threading.Lock()
_comp_log=""; _comp_log_lock=threading.Lock()
_comp_done=False; _comp_exit_code=-1
_comp_dxnn_path=""; _comp_output_dir=""
_comp_stdin_proc=None  # process whose stdin we can write to

# ── dx_engine (optional) ───────────────────────────────────────────────────────
_DS=None; _dx_ok=False
def _load_dx():
    global _DS,_dx_ok
    for root in[DX_RUNTIME_ROOT/"venv-dx-runtime",
                _SUITE_ROOT/"venv-dx-runtime",
                DX_RT_ROOT/"python_package"/"src"]:
        if not(root and root.is_dir()):continue
        for sp in list(root.glob("lib/python*/site-packages"))+[root]:
            if sp.is_dir() and str(sp) not in sys.path:sys.path.insert(0,str(sp))
    try:
        from dx_engine.device_status import DeviceStatus
        _DS=DeviceStatus;_dx_ok=True;print("[OK] dx_engine loaded")
    except Exception:_dx_ok=False;print("[INFO] dx_engine unavailable — mock NPU data")
_load_dx()

# shared/hardware.py 초기화 — DX App 내 inference/developer에서 get_hw() 사용
from hardware import init_hw as _init_hw
_init_hw(ds=_DS, dx_ok=_dx_ok, npu_stats_bin=_NPU_STATS_BIN, app_root=DX_APP_ROOT)

# ── Runtime Python interpreter (numpy/cv2-capable > venv > system) ─────────────
def _find_runtime_python():
    # python_example scripts hard-depend on numpy+cv2. venv-dx-runtime is frequently an
    # empty venv (dx_engine is injected via PYTHONPATH, not pip-installed), so probe each
    # candidate and skip any interpreter missing numpy/cv2 — otherwise every python-variant
    # demo dies with ModuleNotFoundError. Fall back to the gui server's own python.
    cands=[]
    for root in[DX_RUNTIME_ROOT/"venv-dx-runtime",_SUITE_ROOT/"venv-dx-runtime"]:
        for name in["python3","python"]:
            p=root/"bin"/name
            if p.is_file():cands.append(str(p))
    cands.append(sys.executable)
    for name in ("python3", "python"):
        p = shutil.which(name)
        if p:
            cands.append(p)
    seen = set()
    for py in cands:
        if not py or py in seen:
            continue
        seen.add(py)
        try:
            if subprocess.run([py, "-c", "import numpy,cv2"],
                              capture_output=True, timeout=15).returncode == 0:
                return py
        except Exception:
            pass
    return shutil.which("python3") or sys.executable
_RUNTIME_PYTHON=_find_runtime_python()
print(f"[INFO] runtime python: {_RUNTIME_PYTHON}")

# dx_engine is NOT pip-installed — it lives under dx_rt/python_package/src and must be on
# PYTHONPATH for example subprocesses. The gui server injects it into its OWN sys.path at
# import (_load_dx), but that does not propagate to children, so export it explicitly.
_DX_POSTPROCESS_DIRS=[
    DX_APP_ROOT/"build"/"dx_postprocess",
    DX_APP_ROOT/"build_x86_64"/"dx_postprocess",
]
_RUNTIME_PYTHONPATH=os.pathsep.join(
    str(p) for p in [
        DX_RT_ROOT/"python_package"/"src",
        DX_RT_ROOT/"python_package",
        *_DX_POSTPROCESS_DIRS,
    ] if p.is_dir())
