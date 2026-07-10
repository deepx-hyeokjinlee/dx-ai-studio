"""DX-APP Inference engine — run, stop, multi-model, pipeline."""

import os, sys, re, json, time, base64, subprocess, threading, tempfile, uuid, io, shutil, atexit
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import config
from config import (DX_APP_ROOT, CPP_DIR, PY_DIR, BUILD_DIR, ASSETS_DIR,
                    SAMPLE_DIR, OUTPUTS_DIR, SCRIPTS_DIR, CAT_IMAGE, CAT_VIDEO,
                    _RUNTIME_PYTHON, _RUNTIME_PYTHONPATH)
from dx_app_security import resolve_existing_file
from performance import _parse_perf, _cvt_video
from hardware import get_hw
from run_config import build_run_config

MAX_IMAGE_BASE64_BYTES = 20 * 1024 * 1024
RUN_UPLOAD_ROOTS = (DX_APP_ROOT, OUTPUTS_DIR, SAMPLE_DIR, ASSETS_DIR)
_PAIR_COMPARE_CATS = frozenset({"embedding", "reid"})
_STDOUT_TAG_CATS = frozenset({"classification", "attribute_recognition"})
_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp"})


def _count_images_in_dir(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(
        1 for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS
    )


def _python_script_path(category, model_name, variant):
    pf = PY_DIR / category / model_name / f"{model_name}_{variant}.py"
    return pf if pf.exists() else None


def _python_runtime_ready():
    try:
        return subprocess.run(
            [_RUNTIME_PYTHON, "-c", "import numpy,cv2"],
            capture_output=True, timeout=15,
        ).returncode == 0
    except Exception:
        return False


def _effective_run_lang(lang, category, model_name, variant, input_type):
    """Keep user-selected lang; C++ video omits --save to avoid stock VideoWriter SIGABRT."""
    return lang


def _err(error_key, error, **extra):
    payload = {"error": error, "error_key": error_key}
    payload.update(extra)
    return payload


_FALLBACK_BINARIES = {
    "classification":           ["mobilenetv2","resnet50","alexnet","efficientnet_b0","mobilenetv1"],
    "object_detection":         ["yolov5s","yolov8n","yolov7","yolox_s","damoyolo","ssd_mobilenetv1"],
    "face_detection":           ["retinaface_mobilenet0_25_640","blazeface","scrfd_500m"],
    "pose_estimation":          ["hrnet_w32_256x192","centerpose_regnetx_800mf","movenet"],
    "semantic_segmentation":    ["deeplabv3","bisenetv2","deeplabv3plusmobilenet"],
    "instance_segmentation":    ["yolact","mask_rcnn"],
}

def _find_fallback_binary(category, variant="sync"):
    """Find a compatible existing binary for custom models without their own binary."""
    candidates = _FALLBACK_BINARIES.get(category, _FALLBACK_BINARIES["classification"])
    for name in candidates:
        bp = BUILD_DIR / f"{name}_{variant}"
        if bp.exists():
            return bp
    pattern = f"*_{variant}"
    for bp in sorted(BUILD_DIR.glob(pattern)):
        if bp.is_file() and os.access(str(bp), os.X_OK):
            return bp
    return None


def _find_saved_video(stdout_text, save_dir=None):
    """Find the video file produced by C++ runners using --save."""
    candidates = []
    for line in (stdout_text or "").splitlines():
        m = re.search(r"Saving output video:\s*(.+?)(?:\s+\([^)]*\))?\s*$", line.strip())
        if m:
            candidates.append(Path(m.group(1).strip()))
    if save_dir:
        root = Path(save_dir)
        if root.exists():
            candidates.extend(
                p for p in root.rglob("output.*")
                if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}
            )
    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def _drain_dxrt_msgqueues():
    """Best-effort cleanup for stale dxrtd IPC messages before launching DXRT."""
    try:
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        ipc_nowait = 0x800
        msg_noerror = 0x1000
        buf = ctypes.create_string_buffer(8192)
        for key in (0x2a020467, 0x54020467):
            msqid = libc.msgget(key, 0)
            if msqid < 0:
                continue
            while libc.msgrcv(msqid, buf, 8000, 0, ipc_nowait | msg_noerror) >= 0:
                pass
    except Exception:
        pass

_xvfb_procs = {}             # slot_idx -> Xvfb proc
_xvfb_lock = threading.Lock()
_live_jobs = {}              # job_id -> {proc, log_file, start_time, slot_idx, ...}
_live_procs = {}             # slot_idx -> running inference proc
_live_procs_lock = threading.Lock()
# run_multi shares subprocess handles across concurrent worker threads. A single
# shared handle (config._running_proc) is clobbered when several runs are in flight,
# so a concurrent stop/restart would lose or double-handle a child. Track every
# in-flight multi child here under a lock and stop from a consistent snapshot.
_multi_procs = []            # list of live Popen handles owned by active run_multi calls
_multi_procs_lock = threading.Lock()
_capture_locks = {}          # slot_idx -> Lock (lazy)
_capture_locks_meta = threading.Lock()
_XVFB_BASE = 99
_XVFB_RES = "1280x720x24"

_UDP_BASE_PORT = 9100        # UDP ports 9100, 9101, 9102 ...
_cam_mux_proc = None         # ffmpeg tee process
_cam_mux_lock = threading.Lock()
_cam_mux_count = 0           # how many UDP streams are active


def _start_cam_mux(real_cam_idx, n_slots):
    """Start ffmpeg to fan out real camera to N local UDP streams (no sudo)."""
    global _cam_mux_proc, _cam_mux_count
    with _cam_mux_lock:
        if _cam_mux_proc and _cam_mux_proc.poll() is None:
            _cam_mux_proc.terminate()
            try: _cam_mux_proc.wait(timeout=3)
            except: _cam_mux_proc.kill()
            _cam_mux_proc = None

        real_dev = f"/dev/video{real_cam_idx}"
        if not Path(real_dev).exists():
            print(f"[CAM-MUX] Real camera not found: {real_dev}")
            return False

        # Build ffmpeg command: read from real camera, encode once to H.264,
        # then fan-out to N UDP mpegts streams using tee muxer (single encode)
        tee_parts = []
        for i in range(n_slots):
            port = _UDP_BASE_PORT + i
            tee_parts.append(f"[f=mpegts]udp://127.0.0.1:{port}?pkt_size=1316")
        tee_output = "|".join(tee_parts)

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning",
               "-f", "v4l2", "-input_format", "mjpeg",
               "-video_size", "640x480", "-framerate", "30",
               "-i", real_dev,
               "-map", "0:v",
               "-c:v", "libx264", "-preset", "ultrafast",
               "-tune", "zerolatency", "-g", "30",
               "-f", "tee", tee_output]

        print(f"[CAM-MUX] Starting ffmpeg: {' '.join(cmd)}")
        _cam_mux_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            close_fds=True)
        _cam_mux_count = n_slots
        time.sleep(1.5)  # let UDP streams initialize
        if _cam_mux_proc.poll() is not None:
            stderr = _cam_mux_proc.stderr.read().decode(errors="replace")
            print(f"[CAM-MUX] ffmpeg exited immediately: {stderr[:500]}")
            _cam_mux_proc = None
            return False
        print(f"[CAM-MUX] ffmpeg running PID={_cam_mux_proc.pid}, {n_slots} UDP streams")
        return True


def _stop_cam_mux():
    """Stop ffmpeg camera multiplexer."""
    global _cam_mux_proc, _cam_mux_count
    with _cam_mux_lock:
        if _cam_mux_proc and _cam_mux_proc.poll() is None:
            _cam_mux_proc.terminate()
            try: _cam_mux_proc.wait(timeout=3)
            except: _cam_mux_proc.kill()
            print("[CAM-MUX] ffmpeg stopped")
        _cam_mux_proc = None
        _cam_mux_count = 0

def _get_capture_lock(slot_idx):
    with _capture_locks_meta:
        if slot_idx not in _capture_locks:
            _capture_locks[slot_idx] = threading.Lock()
        return _capture_locks[slot_idx]


def _crop_roi(imgp, roi):
    try:
        import cv2; img = cv2.imread(str(imgp))
        if img is None:
            print(f"[ROI] Failed to read image: {imgp}")
            return None
        ih, iw = img.shape[:2]
        x = max(0, min(int(roi["x"]), iw - 1))
        y = max(0, min(int(roi["y"]), ih - 1))
        w = max(1, min(int(roi["w"]), iw - x))
        h = max(1, min(int(roi["h"]), ih - y))
        print(f"[ROI] Crop: x={x},y={y},w={w},h={h} from image {iw}x{ih}")
        cropped = img[y:y+h, x:x+w]
        if cropped.size == 0:
            print(f"[ROI] Empty crop result")
            return None
        tmp = tempfile.mktemp(suffix=".jpg", dir="/tmp")
        cv2.imwrite(tmp, cropped)
        print(f"[ROI] Saved crop to {tmp} ({w}x{h})")
        return tmp
    except Exception as e:
        print(f"[ROI] Error: {e}")
        return None


def list_cameras():
    """Scan /dev/video* and return available camera devices."""
    cams = []
    import glob
    for dev in sorted(glob.glob("/dev/video*")):
        idx = dev.replace("/dev/video", "")
        try:
            idx_int = int(idx)
        except ValueError:
            continue
        try:
            import cv2
            cap = cv2.VideoCapture(idx_int)
            ok = cap.isOpened()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if ok else 0
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if ok else 0
            cap.release()
            cams.append({"index": idx_int, "device": dev, "available": ok, "width": w, "height": h})
        except Exception:
            cams.append({"index": idx_int, "device": dev, "available": False, "width": 0, "height": 0})
    return cams


def run_inference(model_name, category, model_file, lang="cpp", variant="sync",
                  input_type="image", image_path=None, video_path=None,
                  device_id=None, conf_threshold=None, nms_threshold=None,
                  config_overrides=None,
                  upload_path=None, timeout=120, loop=None,
                  camera_id=None, rtsp_url=None,
                  save_output=True, image_base64=None, _multi=False):
    if not model_file: return _err("no_model_file", "No model file configured")
    # Multi-model support: if model_file starts with '-', it contains custom CLI args
    is_multi_model = model_file.startswith("-")
    if is_multi_model:
        import shlex
        model_args = shlex.split(model_file)
        for i, arg in enumerate(model_args):
            if not arg.startswith("-") and arg.endswith(".dxnn"):
                mfp = DX_APP_ROOT / arg
                if not mfp.exists():
                    return _err("model_not_found", f"Model file not found: {arg}")
                model_args[i] = str(mfp)
    else:
        mp = DX_APP_ROOT / model_file
        if not mp.exists(): return _err("model_not_found", f"Model file not found: {model_file}")
    _b64_tmp = None
    if input_type == "image" and image_base64:
        try:
            raw = image_base64.split(",", 1)[-1] if "," in image_base64 else image_base64
            if len(raw) > MAX_IMAGE_BASE64_BYTES:
                return _err("image_base64_too_large", "image_base64 too large")
            img_bytes = base64.b64decode(raw, validate=True)
        except Exception:
            return _err("invalid_image_base64", "Invalid image_base64")
        fd, _b64_tmp = tempfile.mkstemp(prefix="dxapp_upload_", suffix=".jpg", dir="/tmp")
        os.close(fd)
        Path(_b64_tmp).write_bytes(img_bytes)
        upload_path = _b64_tmp
    _is_live = input_type in ("camera", "rtsp")
    if _is_live:
        if input_type == "camera":
            _cam_idx = int(camera_id) if camera_id is not None else 0
            inp = Path(f"/dev/video{_cam_idx}")
            if not inp.exists(): return _err("camera_not_found", f"Camera device not found: {inp}")
        else:  # rtsp
            if not rtsp_url: return _err("rtsp_required", "RTSP URL is required")
            inp = Path(rtsp_url)  # placeholder — not a real path, used as string
    elif _b64_tmp and upload_path == _b64_tmp:
        inp = Path(upload_path)
    elif upload_path:
        try:
            inp = resolve_existing_file(upload_path, RUN_UPLOAD_ROOTS, None)
        except ValueError as e:
            return _err("path_outside_allowed_roots", f"Path is outside allowed roots: {upload_path}")
    elif input_type == "image": inp = DX_APP_ROOT / (image_path or CAT_IMAGE.get(category, "sample/img/sample_street.jpg"))
    else: inp = DX_APP_ROOT / (video_path or CAT_VIDEO.get(category, "assets/videos/dance-group.mov"))
    if not _is_live and not inp.exists(): return _err("input_not_found", f"Input not found: {inp}")
    # DXAPP_SAVE_IMAGE forces per-frame render even with --no-display; skip for video (perf + no still needed).
    res_img = None if input_type == "video" else tempfile.mktemp(suffix=".jpg", dir="/tmp")
    # Merge model config.json with UI overrides (schema-aligned; no per-model hardcoding)
    merged_cfg = build_run_config(
        category, model_name, config_overrides, conf_threshold, nms_threshold,
    )
    tmp_config = None
    if merged_cfg is not None:
        tmp_config = tempfile.mktemp(suffix=".json", dir="/tmp")
        Path(tmp_config).write_text(json.dumps(merged_cfg))
    _lib_dirs = ["/usr/local/lib", "/usr/lib",
                 str(DX_APP_ROOT.parent / "dx_rt" / "build_x86_64" / "lib"),
                 str(DX_APP_ROOT.parent / "dx_rt" / "lib")]
    _existing = [d for d in _lib_dirs if os.path.isdir(d)]
    _ld = ":".join(_existing)
    if os.environ.get("LD_LIBRARY_PATH"): _ld = os.environ["LD_LIBRARY_PATH"] + ":" + _ld
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "LD_LIBRARY_PATH": _ld}
    if res_img:
        env["DXAPP_SAVE_IMAGE"] = res_img
    # dx_engine lives on PYTHONPATH (not pip-installed); the python_example subprocess needs it.
    if _RUNTIME_PYTHONPATH:
        env["PYTHONPATH"] = _RUNTIME_PYTHONPATH + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if _is_live:
        # Camera/RTSP needs DISPLAY for GStreamer → V4L2 pipeline
        env.setdefault("DISPLAY", ":0")
    else:
        env.pop("DISPLAY", None)
    if input_type == "image":
        inf = "-i"
    else:
        inf = "-v"  # video, camera, rtsp all use -v flag
    _inp_str = rtsp_url if input_type == "rtsp" else str(inp)
    _loop = loop or (100 if _is_live else 1)
    # embedding/reid: pair-folder demo needs 2+ images (1st = reference, 2nd+ = compare canvas)
    if not _is_live and input_type == "image" and category in _PAIR_COMPARE_CATS and inp.is_dir():
        pair_n = _count_images_in_dir(inp)
        if not loop and pair_n >= 2:
            _loop = pair_n
    if _is_live:
        timeout = max(timeout, 300)  # live sources may need more time
    _video_save_dir = None
    run_lang = _effective_run_lang(lang, category, model_name, variant, input_type)
    tag_extra = ["--show-log"] if category in _STDOUT_TAG_CATS else []
    if run_lang == "cpp":
        bp = BUILD_DIR / f"{model_name}_{variant}"
        if not bp.exists():
            bp = _find_fallback_binary(category, variant)
            if not bp:
                if _b64_tmp:
                    try: os.unlink(_b64_tmp)
                    except OSError: pass
                return _err("binary_not_found", f"Binary not found: {model_name}_{variant} — run build.sh")
        extra = list(tag_extra)
        # Stock dx-runtime C++ --save can SIGABRT when VideoWriter reports w/h=0; skip save on cpp.
        if input_type != "video":
            pass
        if is_multi_model:
            cmd = [str(bp)] + model_args + [inf, _inp_str, "--no-display", "-l", str(_loop)] + extra
        else:
            if tmp_config: extra += ["--config", tmp_config]
            cmd = [str(bp), "-m", str(mp), inf, _inp_str, "--no-display", "-l", str(_loop)] + extra
    else:
        pf = _python_script_path(category, model_name, variant)
        if not pf:
            if _b64_tmp:
                try: os.unlink(_b64_tmp)
                except OSError: pass
            return _err("script_not_found", f"Script not found: {model_name}_{variant}.py")
        py_extra = list(tag_extra)
        if tmp_config: py_extra += ["--config", tmp_config]
        if input_type == "video":
            _video_save_dir = tempfile.mkdtemp(prefix="dxapp_video_", dir="/tmp")
            py_extra += ["--save", "--save-dir", _video_save_dir]
        if _loop != 1:
            py_extra += ["-l", str(_loop)]
        cmd = [_RUNTIME_PYTHON, str(pf), "--model", str(mp),
               f"--{'image' if input_type=='image' else 'video'}", _inp_str, "--no-display"] + py_extra
    hw0 = get_hw(); t0 = time.time()
    _stdout_file = tempfile.mktemp(suffix=".log", dir="/tmp")
    proc = None
    try:
        with open(_stdout_file, "w") as _fout:
            _drain_dxrt_msgqueues()
            with config._proc_lock:
                config._running_proc = subprocess.Popen(cmd, stdout=_fout, stderr=subprocess.STDOUT,
                 cwd=str(DX_APP_ROOT), env=env, text=True, close_fds=True); proc = config._running_proc
            if _multi: _multi_register(proc)
            proc.wait(timeout=timeout); elapsed = time.time() - t0
        if _multi: _multi_unregister(proc)
        with config._proc_lock: config._running_proc = None
        try:
            stdout = open(_stdout_file, "r").read()
        except:
            stdout = ""
        try: os.unlink(_stdout_file)
        except: pass
        hw1 = get_hw()
        res = {"exit_code": proc.returncode, "output": stdout[-4000:], "model": model_name,
               "category": category, "lang": lang, "variant": variant, "input_type": input_type,
               "elapsed_s": round(elapsed, 2), "timestamp": time.time(), "device_id": device_id, "hw_after": hw1}
        if run_lang != lang:
            res["lang_effective"] = run_lang
        if input_type == "video":
            res["video_save_mode"] = "python_save" if run_lang == "python" else "cpp_no_save"
        perf = _parse_perf(stdout); res["perf"] = perf
        res["fps"] = perf.get("overall_fps", ""); res["latency"] = perf.get("inference_latency", "")

        task = _parse_task_tags(stdout)
        res["task_tag"] = task["tag"]
        res["task_summary"] = task["summary"]
        res["task_frames"] = task["frame_count"]
        # Human-readable last predictions (e.g. classification top-k "tabby: 85.3%") — the only
        # visualizable result for tasks (classification/depth/pose/...) that emit NO output image.
        res["task_last_pred"] = task["last_pred"]

        # Result image — normalise to input resolution for CMP slider
        if res_img and os.path.exists(res_img) and os.path.getsize(res_img) > 0:
            try:
                import cv2 as _cv2
                _inp_img = _cv2.imread(str(inp))
                _res_img = _cv2.imread(res_img)
                if _inp_img is not None and _res_img is not None:
                    _ih, _iw = _inp_img.shape[:2]
                    _rh, _rw = _res_img.shape[:2]
                    # Side-by-side canvas (e.g. SR): crop right half only — skip embedding/reid compare layout
                    if (category not in _PAIR_COMPARE_CATS
                            and _rw > _iw * 1.5 and abs(_rh - _ih) < _ih * 0.5):
                        _res_img = _res_img[:, _rw // 2 + 2:]
                        _rh, _rw = _res_img.shape[:2]
                    # Only resize-back if result is SMALLER than original (denoising/etc.)
                    # For SR, keep the high-res result — CMP slider handles it via object-fit:contain
                    if (_rw, _rh) != (_iw, _ih) and not (_rw > _iw and _rh > _ih):
                        _res_img = _cv2.resize(_res_img, (_iw, _ih), interpolation=_cv2.INTER_LANCZOS4)
                    _cv2.imwrite(res_img, _res_img)
            except Exception:
                pass
            # For video input, skip returning result_image (video is the real result)
            if input_type == "video":
                res["result_image"] = None
            else:
                res["result_image"] = base64.b64encode(open(res_img, "rb").read()).decode()
                # Save a copy to outputs directory for gallery (skip when save_output=False)
                if save_output:
                    try:
                        _out_name = f"result_{model_name}_{int(time.time())}.jpg"
                        _out_dst = OUTPUTS_DIR / _out_name
                        shutil.copy2(res_img, str(_out_dst))
                        res["result_image_url"] = f"/outputs/{_out_name}"
                    except Exception:
                        pass
            try: os.unlink(res_img)
            except: pass
        else:
            res["result_image"] = None
        if res_img:
            try: os.unlink(res_img)
            except: pass
        res["result_video_url"] = None
        if input_type == "video":
            vo = _find_saved_video(stdout, _video_save_dir) or (DX_APP_ROOT / "result.mp4")
            if vo.exists() and vo.stat().st_size > 0:
                dst = OUTPUTS_DIR / f"result_{model_name}_{int(time.time())}.mp4"
                if _cvt_video(vo, dst): res["result_video_url"] = f"/outputs/{dst.name}"
                if vo == DX_APP_ROOT / "result.mp4":
                    try: vo.unlink(missing_ok=True)
                    except: pass
        if proc.returncode != 0:
            res["error_hint"] = f"Exit code {proc.returncode}"
            # If no usable perf data was parsed, promote to hard error
            # so validation correctly counts this run as failed.

        if proc.returncode != 0 and not res.get("fps"):
                res["error"] = f"Process exited with code {proc.returncode}: {(res.get('output') or '')[-200:].strip()}"
                res["error_key"] = "process_exit"
        with config._history_lock:
            config._recent_runs.appendleft({"model": model_name, "category": category, "lang": lang,
             "variant": variant, "input_type": input_type, "fps": res["fps"], "latency": res["latency"],
             "elapsed_s": res["elapsed_s"], "exit_code": proc.returncode, "timestamp": time.time(),
             })
        if tmp_config:
            try: os.unlink(tmp_config)
            except: pass
        if _b64_tmp:
            try: os.unlink(_b64_tmp)
            except: pass
        if _video_save_dir:
            shutil.rmtree(_video_save_dir, ignore_errors=True)
        return res
    except subprocess.TimeoutExpired:
        if _multi and proc is not None: _multi_unregister(proc)
        with config._proc_lock:
            if config._running_proc: config._running_proc.kill(); config._running_proc.wait(); config._running_proc = None
        try: os.unlink(_stdout_file)
        except: pass
        if tmp_config:
            try: os.unlink(tmp_config)
            except: pass
        if _b64_tmp:
            try: os.unlink(_b64_tmp)
            except: pass
        if _video_save_dir:
            shutil.rmtree(_video_save_dir, ignore_errors=True)
        return _err("inference_timeout", f"Timeout ({timeout}s)", model=model_name)
    except Exception as e:
        if _multi and proc is not None: _multi_unregister(proc)
        try: os.unlink(_stdout_file)
        except: pass
        if _b64_tmp:
            try: os.unlink(_b64_tmp)
            except: pass
        if _video_save_dir:
            shutil.rmtree(_video_save_dir, ignore_errors=True)
        return _err("inference_exception", str(e), model=model_name)


def stop_inference():
    with config._proc_lock:
        if config._running_proc: config._running_proc.kill(); config._running_proc = None; return {"status": "stopped"}
    return {"status": "no_process"}


def _multi_register(proc):
    """Track a run_multi child process handle under the lock."""
    with _multi_procs_lock:
        _multi_procs.append(proc)


def _multi_unregister(proc):
    """Drop a run_multi child once it has finished (guarded)."""
    with _multi_procs_lock:
        try: _multi_procs.remove(proc)
        except ValueError: pass


def stop_multi():
    """Terminate every in-flight run_multi child from a locked snapshot so a
    concurrent stop/restart cannot lose or double-handle a process (F-14b)."""
    with _multi_procs_lock:
        snapshot = list(_multi_procs)
    stopped = 0
    for p in snapshot:
        try:
            if p and p.poll() is None:
                p.terminate(); stopped += 1
        except Exception:
            pass
    return {"status": "stopping", "count": stopped}


def run_multi(reqs):
    results = [None] * len(reqs)
    def _one(idx, req): r = run_inference(_multi=True, **req); r["slot"] = idx; return idx, r
    with ThreadPoolExecutor(max_workers=min(len(reqs), 4)) as ex:
        futs = {ex.submit(_one, i, req): i for i, req in enumerate(reqs)}
        for fut in as_completed(futs):
            try: idx, r = fut.result(timeout=150); results[idx] = r
            except Exception as e: results[futs[fut]] = {"error": str(e), "error_key": "inference_exception", "slot": futs[fut]}
    return results


def run_pipeline(steps, input_path, input_type="image", mode="chain"):
    """Pipeline modes:
    - chain: pass result_image from step N to step N+1
    - cascade: step 1 detects objects, step 2+ runs on each cropped region
    """
    results = []; cur = input_path
    if mode == "cascade" and len(steps) >= 2 and input_type == "image":
        step0 = steps[0]
        r0 = run_inference(step0.get("model_name", ""), step0.get("category", ""), step0.get("model_file", ""),
         step0.get("lang", "cpp"), step0.get("variant", "sync"), "image",
         image_path=str(input_path))
        r0.update({"step_index": 0, "step_model": step0.get("model_name", "")})
        results.append(r0)
        dets = _parse_detections(r0.get("output", ""))
        if not dets:
            r0["cascade_note"] = "No detections found in step 1"
            return results
        for si in range(1, len(steps)):
            step = steps[si]
            crop_results = []
            orig_path = input_path
            for di, det in enumerate(dets):
                bbox = det["bbox"]  # x1,y1,x2,y2 in display coords
                dw, dh = det.get("disp_w", 1), det.get("disp_h", 1)
                try:
                    import cv2
                    orig_img = cv2.imread(str(DX_APP_ROOT / orig_path) if not os.path.isabs(str(orig_path)) else str(orig_path))
                    if orig_img is None: continue
                    oh, ow = orig_img.shape[:2]
                except: continue
                # Scale bbox from display coords to original coords
                sx, sy = ow / dw, oh / dh
                x1 = max(0, int(bbox[0] * sx)); y1 = max(0, int(bbox[1] * sy))
                x2 = min(ow, int(bbox[2] * sx)); y2 = min(oh, int(bbox[3] * sy))
                if x2 <= x1 or y2 <= y1: continue
                crop = orig_img[y1:y2, x1:x2]
                if crop.size == 0: continue
                tmp = tempfile.mktemp(suffix=".jpg", dir="/tmp")
                cv2.imwrite(tmp, crop)
                cr = run_inference(step.get("model_name", ""), step.get("category", ""), step.get("model_file", ""),
                 step.get("lang", "cpp"), step.get("variant", "sync"), "image", image_path=tmp)
                cr.update({"step_index": si, "step_model": step.get("model_name", ""),
                           "crop_index": di, "crop_class": det.get("class", ""),
                           "crop_conf": det.get("conf", 0),
                           "crop_bbox": [x1, y1, x2, y2]})
                crop_results.append(cr)
                try: os.unlink(tmp)
                except: pass
            results.append({"step_index": si, "step_model": step.get("model_name", ""),
                           "cascade_crops": crop_results, "crop_count": len(crop_results)})
        return results
    for i, step in enumerate(steps):
        actual = cur
        if step.get("crop_bbox") and input_type == "image" and os.path.exists(str(cur)):
            c = _crop_roi(Path(cur), step["crop_bbox"])
            if c: actual = c
        r = run_inference(step.get("model_name", ""), step.get("category", ""), step.get("model_file", ""),
         step.get("lang", "cpp"), step.get("variant", "sync"), input_type,
         image_path=str(actual) if input_type == "image" else None,
         video_path=str(actual) if input_type == "video" else None)
        r.update({"step_index": i, "step_model": step.get("model_name", "")}); results.append(r)
        if r.get("result_image") and input_type == "image":
            try:
                tmp = tempfile.mktemp(suffix=".jpg", dir="/tmp")
                open(tmp, "wb").write(base64.b64decode(r["result_image"])); cur = tmp
            except: pass
    return results


def _parse_detections(stdout_text):
    """Parse [DET] class conf x1 y1 x2 y2 disp_w disp_h lines"""
    dets = []
    if not stdout_text: return dets
    for line in stdout_text.split("\n"):
        line = line.strip()
        if not line.startswith("[DET] "): continue
        parts = line[6:].rsplit(" ", 7)  # class conf x1 y1 x2 y2 dw dh
        if len(parts) < 8: continue
        try:
            cls = " ".join(parts[:-7])  # class name may have spaces
            vals = parts[-7:]
            conf = float(vals[0])
            x1, y1, x2, y2 = float(vals[1]), float(vals[2]), float(vals[3]), float(vals[4])
            dw, dh = float(vals[5]), float(vals[6])
            dets.append({"class": cls, "conf": conf, "bbox": [x1, y1, x2, y2], "disp_w": dw, "disp_h": dh})
        except: continue
    return dets


def _ensure_xvfb(slot_idx=0):
    """Start per-slot Xvfb if not already running."""
    global _xvfb_procs
    display = f":{_XVFB_BASE + slot_idx}"
    with _xvfb_lock:
        proc = _xvfb_procs.get(slot_idx)
        if proc and proc.poll() is None:
            return
        os.system(f"pkill -f 'Xvfb {display}' 2>/dev/null")
        time.sleep(0.3)
        p = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", _XVFB_RES, "-ac"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        _xvfb_procs[slot_idx] = p
        print(f"[LIVE] Xvfb started on {display} PID={p.pid}")


def _build_ld_path():
    """Build LD_LIBRARY_PATH string."""
    _lib_dirs = ["/usr/local/lib", "/usr/lib",
                 str(DX_APP_ROOT.parent / "dx_rt" / "build_x86_64" / "lib"),
                 str(DX_APP_ROOT.parent / "dx_rt" / "lib")]
    _existing = [d for d in _lib_dirs if os.path.isdir(d)]
    _ld = ":".join(_existing)
    if os.environ.get("LD_LIBRARY_PATH"):
        _ld = os.environ["LD_LIBRARY_PATH"] + ":" + _ld
    return _ld


def run_inference_live(model_name, category, model_file, lang="cpp", variant="sync",
                       input_type="camera", camera_id=None, rtsp_url=None,
                       device_id=None, slot_idx=0, n_total_slots=1, **kwargs):
    """Start inference WITHOUT --no-display on per-slot Xvfb. Returns {job_id}."""
    if not model_file:
        return _err("no_model_file", "No model file configured")

    is_multi_model = model_file.startswith("-")
    if is_multi_model:
        import shlex
        model_args = shlex.split(model_file)
        for i, arg in enumerate(model_args):
            if not arg.startswith("-") and arg.endswith(".dxnn"):
                mfp = DX_APP_ROOT / arg
                if not mfp.exists():
                    return _err("model_not_found", f"Model file not found: {arg}")
                model_args[i] = str(mfp)
    else:
        mp = DX_APP_ROOT / model_file
        if not mp.exists():
            return _err("model_not_found", f"Model file not found: {model_file}")

    if input_type == "camera":
        _cam_idx = int(camera_id) if camera_id is not None else 0
        if n_total_slots > 1:
            # Multi-slot: ffmpeg reads camera once → N UDP streams
            if slot_idx == 0:
                if not _start_cam_mux(_cam_idx, n_total_slots):
                    return _err("failed_camera_mux", "Failed to start camera multiplexer (ffmpeg). Is ffmpeg installed?")
            else:
                # Give ffmpeg a moment to stabilize for later slots
                time.sleep(0.5)
            _inp_str = f"udp://127.0.0.1:{_UDP_BASE_PORT + slot_idx}"
        else:
            # Single slot: use real camera directly
            _inp_str = f"/dev/video{_cam_idx}"
            if not Path(_inp_str).exists():
                return _err("camera_not_found", f"Camera device not found: {_inp_str}")
    elif input_type == "rtsp":
        if not rtsp_url:
            return _err("rtsp_required", "RTSP URL is required")
        _inp_str = rtsp_url
    else:
        return _err("live_mode_unsupported", "Live mode only supports camera/rtsp")

    with _live_procs_lock:
        old = _live_procs.get(slot_idx)
        if old and old.poll() is None:
            old.terminate()
            try: old.wait(timeout=3)
            except: old.kill()
        _live_procs.pop(slot_idx, None)

    _ensure_xvfb(slot_idx)

    _display = f":{_XVFB_BASE + slot_idx}"
    _loop = 999999  # effectively infinite until SIGTERM
    _ld = _build_ld_path()
    env = {**os.environ, "DISPLAY": _display, "LD_LIBRARY_PATH": _ld}
    env.pop("QT_QPA_PLATFORM", None)  # allow real X11 rendering

    inf = "-v"
    if lang == "cpp":
        bp = BUILD_DIR / f"{model_name}_{variant}"
        if not bp.exists():
            return _err("binary_not_found", f"Binary not found: {bp.name}")
        if is_multi_model:
            cmd = [str(bp)] + model_args + [inf, _inp_str, "-l", str(_loop)]
        else:
            cmd = [str(bp), "-m", str(mp), inf, _inp_str, "-l", str(_loop)]
    else:
        return _err("live_cpp_only", "Live mode currently supports C++ only")

    job_id = str(uuid.uuid4())[:8]
    log_file = tempfile.mktemp(suffix=".log", dir="/tmp")

    with open(log_file, "w") as fout:
        proc = subprocess.Popen(cmd, stdout=fout, stderr=subprocess.STDOUT,
                                cwd=str(DX_APP_ROOT), env=env, text=True, close_fds=True)
    with _live_procs_lock:
        _live_procs[slot_idx] = proc
    # keep config._running_proc for slot 0 backward compat
    if slot_idx == 0:
        with config._proc_lock:
            config._running_proc = proc

    _live_jobs[job_id] = {
        "proc": proc, "log_file": log_file,
        "start_time": time.time(), "model_name": model_name,
        "category": category, "slot_idx": slot_idx,
    }
    print(f"[LIVE] Started job {job_id} slot={slot_idx} PID={proc.pid} model={model_name}")
    return {"job_id": job_id, "status": "started", "slot_idx": slot_idx}


def _parse_task_tags(content):
    """Parse all task-specific stdout tags from C++ runner output.
    Returns dict: {tag: str, lines: list, frame_count: int, last_pred: list, summary: dict}
    """
    _lines = content.split("\n")
    _buckets = {
        "DET":   [l for l in _lines if l.startswith("[DET] ")],
        "CLS":   [l for l in _lines if l.startswith("[CLS]")],
        "SEG":   [l for l in _lines if l.startswith("[SEG]")],
        "ISEG":  [l for l in _lines if l.startswith("[ISEG] ")],
        "DEPTH": [l for l in _lines if l.startswith("[DEPTH] ")],
        "POSE":  [l for l in _lines if l.startswith("[POSE] ")],
        "FACE":  [l for l in _lines if l.startswith("[FACE] ")],
        "ALIGN": [l for l in _lines if l.startswith("[ALIGN] ")],
        "HAND":  [l for l in _lines if l.startswith("[HAND]")],
        "OBB":   [l for l in _lines if l.startswith("[OBB] ")],
        "3D":    [l for l in _lines if l.startswith("[3D] ")],
    }
    # Determine dominant tag
    tag = max(_buckets, key=lambda k: len(_buckets[k]))
    tag_lines = _buckets[tag]
    frame_count = len(tag_lines)
    if frame_count == 0:
        return {"tag": "", "lines": [], "frame_count": 0, "last_pred": [], "summary": {}}

    # Build last_pred (human-readable, last 5 lines)
    last_pred = []
    for tl in tag_lines[-5:]:
        try:
            if tag == "DET":
                parts = tl.split(); cls, conf = parts[1], float(parts[2])
                last_pred.append(f"{cls}: {conf*100:.0f}%")
            elif tag == "CLS":
                parts = tl[5:].split()  # after "[CLS] "
                for i in range(0, len(parts)-1, 2):
                    last_pred.append(f"{parts[i]}: {float(parts[i+1])*100:.1f}%")
                    if len(last_pred) >= 3: break
            elif tag == "SEG":
                parts = tl[5:].split()
                items = []
                for i in range(0, len(parts)-1, 2):
                    items.append(f"{parts[i]}: {parts[i+1]}%")
                last_pred.append(" | ".join(items[:5]))
            elif tag == "ISEG":
                parts = tl.split(); cls = parts[1]; conf = float(parts[2])
                last_pred.append(f"{cls}: {conf*100:.0f}%")
            elif tag == "DEPTH":
                parts = tl.split()
                last_pred.append(f"min={parts[1]} max={parts[2]} mean={parts[3]}")
            elif tag == "POSE":
                parts = tl.split()
                last_pred.append(f"{parts[1]} persons")
            elif tag == "FACE":
                parts = tl.split()
                last_pred.append(f"{parts[1]} faces")
            elif tag == "ALIGN":
                parts = tl.split()
                last_pred.append(f"yaw={parts[1]} pitch={parts[2]} roll={parts[3]}")
            elif tag == "HAND":
                parts = tl[6:].split()  # after "[HAND]"
                for i in range(0, len(parts)-1, 2):
                    last_pred.append(f"{parts[i]}: {float(parts[i+1])*100:.0f}%")
            elif tag == "OBB":
                parts = tl.split(); cls = parts[1]; conf = float(parts[2]); angle = parts[3]
                last_pred.append(f"{cls}: {conf*100:.0f}% {angle}°")
            elif tag == "3D":
                parts = tl.split(); cls = parts[1]; conf = float(parts[2])
                last_pred.append(f"{cls}: {conf*100:.0f}%")
        except:
            continue

    # Build summary (aggregated across all frames)
    summary = {}
    if tag == "DET" or tag == "ISEG" or tag == "OBB" or tag == "3D":
        for tl in tag_lines:
            parts = tl.split()
            if len(parts) >= 3:
                try:
                    cls = parts[1]; conf = float(parts[2])
                    if cls not in summary: summary[cls] = {"count": 0, "conf_sum": 0.0}
                    summary[cls]["count"] += 1; summary[cls]["conf_sum"] += conf
                except: pass
        for cls in summary:
            c = summary[cls]; c["conf_avg"] = round(c["conf_sum"] / c["count"], 3) if c["count"] else 0
    elif tag == "CLS":
        for tl in tag_lines:
            parts = tl[5:].split()
            if len(parts) >= 2:
                try:
                    cls = parts[0]; conf = float(parts[1])
                    if cls not in summary: summary[cls] = {"count": 0, "conf_sum": 0.0}
                    summary[cls]["count"] += 1; summary[cls]["conf_sum"] += conf
                except: pass
        for cls in summary: c = summary[cls]; c["conf_avg"] = round(c["conf_sum"] / c["count"], 3) if c["count"] else 0
    elif tag == "SEG":
        pct_sums = {}; n = 0
        for tl in tag_lines:
            parts = tl[5:].split()
            for i in range(0, len(parts)-1, 2):
                try:
                    cid = parts[i]; pct = float(parts[i+1])
                    if cid not in pct_sums: pct_sums[cid] = 0.0
                    pct_sums[cid] += pct
                except: pass
            n += 1
        if n > 0:
            summary = {cid: {"avg_pct": round(v / n, 1)} for cid, v in pct_sums.items()}
    elif tag == "DEPTH":
        mins, maxs, means = [], [], []
        for tl in tag_lines:
            parts = tl.split()
            if len(parts) >= 4:
                try: mins.append(float(parts[1])); maxs.append(float(parts[2])); means.append(float(parts[3]))
                except: pass
        if means:
            summary = {"min": round(min(mins), 2), "max": round(max(maxs), 2),
                       "mean": round(sum(means)/len(means), 2), "frames": len(means)}
    elif tag == "POSE":
        total_persons = 0
        for tl in tag_lines:
            parts = tl.split()
            if len(parts) >= 2:
                try: total_persons += int(parts[1])
                except: pass
        summary = {"total_detections": total_persons, "frames": frame_count,
                   "avg_per_frame": round(total_persons / frame_count, 1) if frame_count else 0}
    elif tag == "FACE":
        total_faces = 0
        for tl in tag_lines:
            parts = tl.split()
            if len(parts) >= 2:
                try: total_faces += int(parts[1])
                except: pass
        summary = {"total_detections": total_faces, "frames": frame_count,
                   "avg_per_frame": round(total_faces / frame_count, 1) if frame_count else 0}
    elif tag == "ALIGN":
        yaws, pitches, rolls = [], [], []
        for tl in tag_lines:
            parts = tl.split()
            if len(parts) >= 4:
                try: yaws.append(float(parts[1])); pitches.append(float(parts[2])); rolls.append(float(parts[3]))
                except: pass
        if yaws:
            summary = {"avg_yaw": round(sum(yaws)/len(yaws), 1),
                       "avg_pitch": round(sum(pitches)/len(pitches), 1),
                       "avg_roll": round(sum(rolls)/len(rolls), 1), "frames": len(yaws)}
    elif tag == "HAND":
        for tl in tag_lines:
            parts = tl[6:].split()
            for i in range(0, len(parts)-1, 2):
                try:
                    hand = parts[i]; conf = float(parts[i+1])
                    if hand not in summary: summary[hand] = {"count": 0, "conf_sum": 0.0}
                    summary[hand]["count"] += 1; summary[hand]["conf_sum"] += conf
                except: pass
        for h in summary: c = summary[h]; c["conf_avg"] = round(c["conf_sum"] / c["count"], 3) if c["count"] else 0

    return {"tag": tag, "lines": tag_lines, "frame_count": frame_count,
            "last_pred": last_pred, "summary": summary}


def poll_inference(job_id):
    """Poll live job for stats."""
    job = _live_jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}

    proc = job["proc"]
    running = proc.poll() is None
    elapsed = time.time() - job["start_time"]

    try:
        with open(job["log_file"], "r") as f:
            content = f.read()
    except:
        content = ""

    # ── Frame / detection counting (모든 태스크 태그 통합) ──
    task = _parse_task_tags(content)
    task_tag = task["tag"]
    tag_frame_count = task["frame_count"]

    # 분류(sync): "video - Top predictions:" 또는 "Top predictions:" 마커
    frame_markers = content.count("Top predictions:")
    if frame_markers == 0:
        frame_markers = content.count("video -")

    # 검출(async/sync): [DET] 줄 수를 detections으로 사용
    det_lines = task["lines"] if task_tag == "DET" else []
    det_count = len(det_lines)

    # Source FPS 파싱 (로그에서 추출)
    src_fps = 0.0
    m_fps = re.search(r"\[INFO\] Input source FPS:\s*([\d.]+)", content)
    if m_fps:
        try: src_fps = float(m_fps.group(1))
        except: pass

    is_det_mode = det_count > 0 and frame_markers == 0
    has_tag_mode = tag_frame_count > 0  # any task tag found
    # check if inference started (for models that don't print per-frame logs)
    has_started = "Starting" in content and src_fps > 0

    if has_tag_mode:
        # Tag-based frame counting (works for ALL task types)
        est_frames = tag_frame_count
        fps_est = round(est_frames / elapsed, 1) if elapsed > 0.5 else 0
        display_frames = est_frames
    elif frame_markers > 0:
        fps_est = round(frame_markers / elapsed, 1) if elapsed > 0.5 else 0
        display_frames = frame_markers
    elif has_started and running:
        # Models that don't print per-frame logs (restoration, embedding)
        est_frames = int(elapsed * src_fps) if elapsed > 0.5 else 0
        fps_est = round(est_frames / elapsed, 1) if elapsed > 0.5 else 0
        display_frames = est_frames
    else:
        fps_est = 0
        display_frames = 0

    # ── Last prediction / detection (태스크 태그 기반) ──
    last_pred = task["last_pred"] if task["last_pred"] else []
    if not last_pred and not has_tag_mode:
        # Fallback: legacy "Top predictions:" parsing
        lines = content.strip().split("\n")
        for i in range(len(lines) - 1, -1, -1):
            if "Top predictions:" in lines[i]:
                for j in range(i + 1, min(i + 6, len(lines))):
                    line = lines[j].strip()
                    if line and line[0].isdigit():
                        last_pred.append(line)
                    else:
                        break
                break

    # ── Class counts for detection mode (backward compat) ──
    class_counts = {}
    if is_det_mode:
        for dl in det_lines:
            parts = dl.split()
            if len(parts) >= 3:
                try:
                    cls = parts[1]
                    conf = float(parts[2])
                    if cls not in class_counts:
                        class_counts[cls] = {"count": 0, "conf_sum": 0.0}
                    class_counts[cls]["count"] += 1
                    class_counts[cls]["conf_sum"] += conf
                except: pass

    return {"running": running, "frames": display_frames,
            "det_count": det_count, "class_counts": class_counts,
            "elapsed": round(elapsed, 1), "fps_est": fps_est,
            "src_fps": src_fps, "is_det_mode": is_det_mode,
            "last_pred": last_pred,
            "task_tag": task_tag, "task_summary": task["summary"]}


def stop_inference_live(slot_idx=None):
    """Stop inference with SIGTERM. If slot_idx=None, stop all slots."""
    stopped = []
    with _live_procs_lock:
        targets = list(_live_procs.keys()) if slot_idx is None else [slot_idx]
        for s in targets:
            proc = _live_procs.get(s)
            if proc and proc.poll() is None:
                proc.terminate()
                stopped.append(s)
    if slot_idx == 0 or slot_idx is None:
        with config._proc_lock:
            if config._running_proc and config._running_proc.poll() is None:
                config._running_proc.terminate()
    # Stop camera multiplexer when stopping all slots
    if slot_idx is None:
        _stop_cam_mux()
    return {"status": "stopping", "slots": stopped}


def _terminate_proc(p, timeout=3):
    """SIGTERM then SIGKILL a subprocess handle; never raise."""
    try:
        if p and p.poll() is None:
            p.terminate()
            try: p.wait(timeout=timeout)
            except Exception:
                try: p.kill()
                except Exception: pass
    except Exception:
        pass


def shutdown_live_processes():
    """Terminate every live-mode child (live inference, Xvfb, ffmpeg cam-mux) plus
    any in-flight run_multi children. Called on server shutdown AND watchdog restart
    so nothing is left as an orphan (F-13 / F-14a). Safe to call repeatedly."""
    global _cam_mux_proc
    try: stop_inference_live(None)
    except Exception: pass
    with _live_procs_lock:
        for slot, p in list(_live_procs.items()):
            _terminate_proc(p)
            _live_procs.pop(slot, None)
    with _xvfb_lock:
        for slot, p in list(_xvfb_procs.items()):
            _terminate_proc(p)
            _xvfb_procs.pop(slot, None)
    # ffmpeg camera multiplexer (also cleared by stop_inference_live, but be sure).
    with _cam_mux_lock:
        _terminate_proc(_cam_mux_proc)
        _cam_mux_proc = None
    try: stop_multi()
    except Exception: pass
    try: stop_inference()
    except Exception: pass


# Ensure children are reaped when the interpreter exits — this covers the
# SIGINT/SIGTERM shutdown path (DXServer._shutdown calls sys.exit, which runs
# atexit handlers) in addition to the watchdog restart path.
atexit.register(shutdown_live_processes)


def get_inference_result(job_id):
    """Get final result after live job completes."""
    job = _live_jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}

    proc = job["proc"]
    try:
        proc.wait(timeout=8)
    except:
        proc.kill()

    try:
        with open(job["log_file"], "r") as f:
            content = f.read()
    except:
        content = ""

    perf = _parse_perf(content)

    # Build task-specific summary from all tags
    task = _parse_task_tags(content)

    # Backward-compatible det_summary
    det_summary = task["summary"] if task["tag"] == "DET" else {}
    if task["tag"] == "DET":
        pass  # already in correct format
    elif not det_summary:
        # Legacy fallback
        for line in content.split("\n"):
            if not line.startswith("[DET] "): continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    cls = parts[1]; conf = float(parts[2])
                    if cls not in det_summary:
                        det_summary[cls] = {"count": 0, "conf_sum": 0.0}
                    det_summary[cls]["count"] += 1; det_summary[cls]["conf_sum"] += conf
                except: pass
        for cls in det_summary:
            c = det_summary[cls]; c["conf_avg"] = round(c["conf_sum"] / c["count"], 3) if c["count"] else 0

    result = {
        "job_id": job_id, "exit_code": proc.returncode,
        "model": job["model_name"], "category": job["category"],
        "slot_idx": job.get("slot_idx", 0),
        "perf": perf,
        "fps": perf.get("overall_fps", ""),
        "latency": perf.get("inference_latency", ""),
        "total_frames": perf.get("total_frames", ""),
        "total_time": perf.get("total_time", ""),
        "elapsed_seconds": round(time.time() - job["start_time"], 1),
        "det_summary": det_summary,
        "task_tag": task["tag"],
        "task_summary": task["summary"],
        "task_frames": task["frame_count"],
        "output": content[-4000:],
    }

    slot = job.get("slot_idx", 0)
    try: os.unlink(job["log_file"])
    except: pass
    _live_jobs.pop(job_id, None)
    with _live_procs_lock:
        _live_procs.pop(slot, None)
    if slot == 0:
        with config._proc_lock:
            config._running_proc = None

    return result


_display_env_lock = threading.Lock()   # global lock for DISPLAY env changes

def capture_live_frame(slot_idx=0):
    """Capture per-slot Xvfb screen as JPEG bytes (thread-safe)."""
    display = f":{_XVFB_BASE + slot_idx}"
    with _display_env_lock:
        old_display = os.environ.get("DISPLAY")
        os.environ["DISPLAY"] = display
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                mon = sct.monitors[0]
                img = sct.grab(mon)
                pil = Image.frombytes("RGB", (img.width, img.height), img.rgb)
                pil = pil.resize((960, 540), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=70)
                return buf.getvalue()
        except Exception as e:
            print(f"[LIVE] Capture error slot={slot_idx}: {e}")
            return None
        finally:
            if old_display is not None:
                os.environ["DISPLAY"] = old_display
            else:
                os.environ.pop("DISPLAY", None)
