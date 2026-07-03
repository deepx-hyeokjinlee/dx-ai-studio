#!/usr/bin/env python3
"""test_models.conf → model_catalog.json 자동 생성."""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import (CONFIG_FILE, CATEGORIES, EXAMPLE_TYPES, SAMPLE_IMAGES,
                          DX_APP_ROOT, DATA_DIR, CPP_DIR, PY_DIR)
from core.catalog import parse_test_models_conf


def generate():
    models = parse_test_models_conf()
    if not models:
        print("[ERROR] No models found. Check CONFIG_FILE path.")
        sys.exit(1)

    catalog_models = []
    for m in models:
        cat = m["category"]
        cpp_path = f"src/cpp_example/{cat}/{m['id']}/"
        py_path = f"src/python_example/{cat}/{m['id']}/"
        cpp_exists = (DX_APP_ROOT / cpp_path).is_dir() if DX_APP_ROOT.exists() else False
        py_exists = (DX_APP_ROOT / py_path).is_dir() if DX_APP_ROOT.exists() else False

        qpro_file = m["model_file"].replace("assets/models/", "assets/models/q-pro/")
        qpro_exists = (DX_APP_ROOT / qpro_file).exists() if DX_APP_ROOT.exists() else False

        catalog_models.append({
            "id": m["id"],
            "name": m["id"].replace("_", " ").title(),
            "class_name": m["id"],
            "category": cat,
            "description": {
                "en": f"{m['id']} is a {cat.replace('_', ' ')} model optimized for DEEPX NPU.",
                "ko": f"{m['id']}은(는) DEEPX NPU에 최적화된 {CATEGORIES.get(cat, {}).get('label_ko', cat)} 모델입니다."
            },
            "specification": {
                "input_resolution": "", "ops": "", "params": "", "dataset": "",
                "metric": {}, "quantization": ["qlite"],
                "fps": "", "fps_per_watt": ""
            },
            "compile_guide": {
                "onnx_url": "", "recommended_quant": "qlite",
                "notes": {"en": "Use dxcom default settings.", "ko": "dxcom 기본 설정 사용."}
            },
            "demo": {
                "cpp_example": cpp_path if cpp_exists else "",
                "python_example": py_path if py_exists else "",
                "cli_command": f"./{m['id']}_sync -m {m['model_file']} -i {SAMPLE_IMAGES.get(cat, 'sample/img/sample_street.jpg')}"
            },
            "legal": {
                "license": "", "copyright": "", "source_url": ""
            },
            "thumbnail": f"thumbnails/{m['id']}.jpg",
            "example_images": {
                "type": EXAMPLE_TYPES.get(cat, "single"),
                "result": f"examples/{m['id']}_result.jpg",
                "original": f"examples/{m['id']}_original.jpg"
                    if EXAMPLE_TYPES.get(cat) in ("before_after", "overlay") else ""
            },
            "model_file": m["model_file"],
            "model_file_qpro": qpro_file if qpro_exists else ""
        })

    catalog = {
        "version": "1.0",
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "categories": CATEGORIES,
        "models": catalog_models
    }

    out = DATA_DIR / "model_catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))
    print(f"[OK] Generated {out} with {len(catalog_models)} models")


if __name__ == "__main__":
    generate()
