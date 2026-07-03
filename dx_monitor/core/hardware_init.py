"""DX Monitor — 하드웨어 SDK 초기화.

기존 dx_monitor/config.py의 SDK 초기화 로직을 분리.
import 시 자동으로 DX Engine SDK를 로드하고 hardware.py를 초기화한다.
"""
import sys
from pathlib import Path

from core.config import SUITE_ROOT, STUDIO_DIR, SCRIPT_DIR, DX_APP_ROOT

_DS = None
_dx_ok = False
_NPU_STATS_BIN = SCRIPT_DIR / "dx_npu_stats"

if not _NPU_STATS_BIN.exists():
    _alt = DX_APP_ROOT / "core" / "dx_npu_stats"
    if _alt.exists():
        _NPU_STATS_BIN = _alt


def _load_dx():
    global _DS, _dx_ok
    DX_RT_ROOT = SUITE_ROOT / "dx-runtime"
    for root in [DX_RT_ROOT / "venv-dx-runtime",
                 SUITE_ROOT / "venv-dx-runtime",
                 # dx_engine lives under dx-runtime/dx_rt/python_package/src (the /dx_rt/ was
                 # missing here → import failed → mock NPU data, unlike dx_app which has it).
                 DX_RT_ROOT / "dx_rt" / "python_package" / "src"]:
        if not (root and root.is_dir()):
            continue
        for sp in list(root.glob("lib/python*/site-packages")) + [root]:
            if sp.is_dir() and str(sp) not in sys.path:
                sys.path.insert(0, str(sp))
    try:
        from dx_engine.device_status import DeviceStatus
        _DS = DeviceStatus
        _dx_ok = True
        print("[DX Monitor] dx_engine loaded")
    except Exception:
        _dx_ok = False
        print("[DX Monitor] dx_engine unavailable — mock NPU data")


def init():
    """SDK 로드 + hardware.py 초기화. 서버 시작 시 1회 호출."""
    _load_dx()
    from hardware import init_hw
    init_hw(ds=_DS, dx_ok=_dx_ok, npu_stats_bin=_NPU_STATS_BIN,
            app_root=DX_APP_ROOT)
