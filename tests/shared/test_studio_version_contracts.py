"""Studio version SSOT and launcher hook contracts."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO_VERSION_JS = ROOT / "shared" / "static" / "studio-version.js"
LAUNCHER_INDEX = ROOT / "launcher" / "static" / "index.html"


def test_studio_version_ssot_semver():
    text = STUDIO_VERSION_JS.read_text(encoding="utf-8")
    assert "semver: '0.1.0'" in text
    assert "label: 'Beta version'" in text
    assert "channel: 'beta'" in text


def test_launcher_wires_studio_version_hooks():
    html = LAUNCHER_INDEX.read_text(encoding="utf-8")
    assert "/static/shared/studio-version.js" in html
    assert 'id="studioBetaBadge"' in html
    assert 'id="studioVersionHub"' in html
    assert 'id="studioVersionFooter"' in html


def test_studio_version_js_exports_apply():
    text = STUDIO_VERSION_JS.read_text(encoding="utf-8")
    assert "DXStudioVersion" in text
    assert "applyStudioVersion" in text or "apply:" in text
