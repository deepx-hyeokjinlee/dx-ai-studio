"""DX Model Zoo — 경로, 상수, 카테고리 정의."""
import os
from pathlib import Path

# ── 경로 계산 (dx_stream/core/config.py 패턴) ──
SCRIPT_DIR = Path(__file__).resolve().parent.parent          # dx_modelzoo/
SUITE_ROOT = SCRIPT_DIR.parent.parent                        # dx-all-suite/
DX_APP_ROOT = Path(os.environ["DX_APP_ROOT"]) if os.environ.get("DX_APP_ROOT") \
    else SUITE_ROOT / "dx-runtime" / "dx_app"

CONFIG_FILE = DX_APP_ROOT / "config" / "test_models.conf"
ASSETS_DIR = DX_APP_ROOT / "assets"
MODELS_DIR = ASSETS_DIR / "models"
CPP_DIR = DX_APP_ROOT / "src" / "cpp_example"
PY_DIR = DX_APP_ROOT / "src" / "python_example"
BUILD_DIR = DX_APP_ROOT / "build_x86_64" / "src" / "cpp_example"
SAMPLE_DIR = DX_APP_ROOT / "sample"
SAMPLE_IMG_DIR = SAMPLE_DIR / "img"

STATIC_DIR = SCRIPT_DIR / "static"
TEMPLATES_DIR = SCRIPT_DIR / "templates"
DATA_DIR = SCRIPT_DIR / "data"
CATALOG_FILE = DATA_DIR / "model_catalog.json"

# ── 서버 설정 ──
DEFAULT_PORT = 8094
# Inference is proxied to the dx_app server. The launcher may reassign dx_app to a
# free port when 8080 is held by a foreign process, so honor DX_APP_PORT from the
# environment (set by the launcher) instead of hardcoding 8080.
try:
    DX_APP_PORT = int(os.environ.get("DX_APP_PORT", "8080"))
except (TypeError, ValueError):
    DX_APP_PORT = 8080
SERVER_NAME = "DX Model Zoo"

# ── 17개 카테고리 (test_models.conf에서 확인된 실제 값) ──
CATEGORIES = {
    "object_detection":     {"label_en": "Object Detection",      "label_ko": "객체 탐지",           "icon": "🎯"},
    "classification":       {"label_en": "Classification",        "label_ko": "분류",               "icon": "🏷️"},
    "ppu":                  {"label_en": "PPU",                   "label_ko": "PPU",                "icon": "⚙️"},
    "instance_segmentation":{"label_en": "Instance Segmentation", "label_ko": "인스턴스 분할",       "icon": "🎨"},
    "face_detection":       {"label_en": "Face Detection",        "label_ko": "얼굴 탐지",          "icon": "👤"},
    "pose_estimation":      {"label_en": "Pose Estimation",       "label_ko": "자세 추정",          "icon": "🏃"},
    "semantic_segmentation":{"label_en": "Semantic Segmentation", "label_ko": "시맨틱 분할",        "icon": "🖌️"},
    "image_denoising":      {"label_en": "Image Denoising",       "label_ko": "이미지 노이즈 제거", "icon": "✨"},
    "obb_detection":        {"label_en": "OBB Detection",         "label_ko": "OBB 탐지",           "icon": "📐"},
    "reid":                 {"label_en": "Re-Identification",     "label_ko": "재식별",             "icon": "🔎"},
    "embedding":            {"label_en": "Embedding",             "label_ko": "임베딩",             "icon": "🔗"},
    "attribute_recognition":{"label_en": "Attribute Recognition",  "label_ko": "속성 인식",          "icon": "🏷️"},
    "super_resolution":     {"label_en": "Super Resolution",      "label_ko": "초해상도",           "icon": "🔍"},
    "face_alignment":       {"label_en": "Face Alignment",        "label_ko": "얼굴 정렬",          "icon": "😀"},
    "depth_estimation":     {"label_en": "Depth Estimation",      "label_ko": "깊이 추정",          "icon": "📏"},
    "image_enhancement":    {"label_en": "Image Enhancement",     "label_ko": "이미지 향상",        "icon": "🌟"},
    "hand_landmark":        {"label_en": "Hand Landmark",         "label_ko": "손 랜드마크",        "icon": "✋"},
}

# 태스크별 Example 이미지 표시 타입
EXAMPLE_TYPES = {
    "object_detection": "single", "face_detection": "single",
    "pose_estimation": "single", "obb_detection": "single",
    "ppu": "single", "face_alignment": "single", "hand_landmark": "single",
    "attribute_recognition": "single", "embedding": "single",
    "image_denoising": "before_after", "super_resolution": "before_after",
    "image_enhancement": "before_after",
    "semantic_segmentation": "overlay", "instance_segmentation": "overlay",
    "depth_estimation": "overlay",
    "classification": "classified", "reid": "gallery",
}

# 태스크별 기본 샘플 이미지 (inference 용)
SAMPLE_IMAGES = {
    "object_detection": "sample/img/sample_street.jpg",
    "face_detection": "sample/img/sample_face.jpg",
    "pose_estimation": "sample/img/sample_people.jpg",
    "obb_detection": "sample/dota8_test/P0284.png",
    "classification": "sample/img/sample_dog.jpg",
    "instance_segmentation": "sample/img/sample_street.jpg",
    "semantic_segmentation": "sample/img/sample_parking.jpg",
    "depth_estimation": "sample/img/sample_horse.jpg",
    "image_denoising": "sample/img/sample_denoising.jpg",
    "super_resolution": "sample/img/sample_superresolution.png",
    "image_enhancement": "sample/img/sample_lowlight.jpg",
    "embedding": "sample/img/face_pair",
    "attribute_recognition": "sample/img/sample_person_a1.jpg",
    "reid": "sample/img/person_pair",
    "ppu": "sample/img/sample_street.jpg",
    "hand_landmark": "sample/img/sample_hand.jpg",
    "face_alignment": "sample/img/sample_face_a1.jpg",
}

MODEL_IMAGE_OVERRIDE = {
    "scrfd500m_ppu": "sample/img/sample_face.jpg",
    "yolov5pose_ppu": "sample/img/sample_people.jpg",
    "handlandmarklite_1": "sample/img/sample_hand.jpg",
    "unet_mobilenet_v2": "sample/img/sample_dog.jpg",
}

for _name, _path in [("DX_APP_ROOT", DX_APP_ROOT)]:
    if not _path.is_dir():
        print(f"[WARNING] {_name} not found: {_path}")
