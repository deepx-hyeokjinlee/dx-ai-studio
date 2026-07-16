# dx-benchmark Thin-Viewer Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the studio `/benchmark/` module into a thin viewer over the standalone `dx-benchmark` — serving a bundled snapshot, dropping the vendored `core/` package, and surfacing all new features/data in the studio design.

**Architecture:** The standalone `dx-benchmark` (canonical) builds `dataset.json` + `results/`; a studio sync script copies them into `dx_benchmark/` as a bundled snapshot; `server.py` serves the bundle statically (no runtime aggregation, no `core/` import); the SPA/i18n/tutorial are reworked to the new schema/features. Execution stays delegated to the standalone tool (web is browse-only).

**Tech Stack:** Python 3.8+ stdlib only (http.server), vanilla JS SPA (Canvas charts), `shared/` studio libs (dx_server, i18n, tutorial engine).

## Global Constraints

- Python **3.8+** compatible (no 3.9+ syntax); verify parses under 3.8.
- **Zero third-party dependencies** — `pyproject` deps stay `[]`; stdlib only.
- **6 languages** everywhere user-facing: ko/en/ja/zh-CN/zh-TW/es. New strings added to `static/js/i18n.js` `_DX_I18N_DICT`, keyed by the English string.
- Studio **dark-theme design** — the dashboard keeps the studio look (shared tokens, Canvas charts), NOT the standalone tool's English static-dashboard look.
- **Never fabricate benchmark data**; tutorial preview injections must stay clearly labeled "Tutorial preview".
- Web module is **browse-only** — no `/api/run`, no run button.
- Commit after each task with the standard `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` footer; push only when asked.

## Source of the new schema/data

- Materialized standalone tree (reference during dev): `/tmp/claude-1000/-home-deepx-hj-ai-studio/7e979537-3bd6-4559-be1f-b963a5a253bf/scratchpad/new-dx-benchmark` (fetched from `yjsong/feat/dx-benchmark-suite-relocation`).
- At release, the standalone lands at `dx-all-suite/dx-benchmark` (sibling of `dx-ai-studio`). The sync script must accept the source path (default the sibling) and fail loudly if absent.

## File Structure

- `dx_benchmark/scripts/sync_from_standalone.sh` — **create**. Runs the standalone's `dataset`/`aggregate` build, copies `results/**` + `dataset.json` into the studio bundle.
- `dx_benchmark/dataset.json` — **bundled artifact** (committed, portable). Produced by the sync script.
- `dx_benchmark/results/**` — **bundled snapshot** (committed). Produced by the sync script.
- `dx_benchmark/server.py` — **modify**. Serve bundled `dataset.json` directly; drop `core.aggregator` import + `_regenerate_dataset()` + `_aggregate_all_result_dirs()`; `/api/config` reads a static/bundled config (drop `core.config` import).
- `dx_benchmark/core/` — **delete** (after server no longer imports it).
- `dx_benchmark/templates/dashboard/` — **delete** (dead, unreferenced).
- `dx_benchmark/static/js/dashboard.js` — **modify**. Consume new dataset schema; surface new features in studio design.
- `dx_benchmark/static/js/i18n.js` — **modify**. Add new UI strings (6 langs).
- `dx_benchmark/static/js/tutorial.js` — **modify**. Retarget/extend for the new UI (preserve the recent transient-state fixes).
- `dx_benchmark/static/js/results.js`, `settings.js` — **verify/minor**. Confirm still work against bundled results + static config.
- `tests/launcher/` (+ any `dx_benchmark` tests) — **modify**. Update/□add coverage for the served endpoints without `core/`.

---

### Task 1: Sync script — bundle the standalone snapshot

**Files:**
- Create: `dx_benchmark/scripts/sync_from_standalone.sh`
- Test: `dx_benchmark/tests/test_sync_script.py`

**Interfaces:**
- Produces: `dx_benchmark/dataset.json` (v2) + `dx_benchmark/results/**` populated from a standalone source dir. Script usage: `sync_from_standalone.sh [SRC_DIR]` (default `../../dx-benchmark`).

- [ ] **Step 1: Write the failing test** — assert the script exists, is executable, errors (non-zero + message) when SRC_DIR missing, and (given a fixture SRC with `results/` + a `dataset.json`) copies them into `dx_benchmark/`.

```python
# dx_benchmark/tests/test_sync_script.py
import subprocess, os, json, pathlib, tempfile, shutil
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sync_from_standalone.sh"

def test_missing_source_fails():
    r = subprocess.run([str(SCRIPT), "/nonexistent/path"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "not found" in (r.stderr + r.stdout).lower()

def test_copies_snapshot(tmp_path):
    src = tmp_path / "dx-benchmark"; (src / "results" / "HW/RUN").mkdir(parents=True)
    (src / "results" / "HW/RUN" / "environment.json").write_text("{}")
    (src / "results" / "dashboard").mkdir(parents=True)
    (src / "results" / "dashboard" / "dataset.json").write_text('{"dataset_version":"v2"}')
    dest = tmp_path / "studio_bench"; (dest / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, dest / "scripts" / "sync_from_standalone.sh")
    r = subprocess.run([str(dest/"scripts"/"sync_from_standalone.sh"), str(src)], capture_output=True, text=True, cwd=dest)
    assert r.returncode == 0, r.stderr
    assert json.loads((dest/"dataset.json").read_text())["dataset_version"] == "v2"
    assert (dest/"results"/"HW"/"RUN"/"environment.json").exists()
```

- [ ] **Step 2: Run test to verify it fails** — `cd dx_benchmark && python -m pytest tests/test_sync_script.py -q` → FAIL (script missing).

- [ ] **Step 3: Write the script** (stdlib tools only; runs the standalone dataset build if a prebuilt `dataset.json` is absent).

```bash
#!/usr/bin/env bash
# Bundle a snapshot (results/ + dataset.json) from the standalone dx-benchmark.
# Usage: sync_from_standalone.sh [SRC_DIR]   (default: ../../dx-benchmark relative to studio root)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STUDIO_BENCH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="${1:-$STUDIO_BENCH_DIR/../../dx-benchmark}"
if [ ! -d "$SRC_DIR" ]; then echo "ERROR: standalone dx-benchmark source not found: $SRC_DIR" >&2; exit 1; fi

# Prefer a prebuilt dataset; otherwise build it with the standalone tool.
DATASET="$SRC_DIR/results/dashboard/dataset.json"
if [ ! -f "$DATASET" ]; then
  if [ -f "$SRC_DIR/run.sh" ]; then ( cd "$SRC_DIR" && ./run.sh dashboard results ) || \
    { echo "ERROR: failed to build dataset.json via standalone run.sh" >&2; exit 1; }
  fi
fi
[ -f "$DATASET" ] || { echo "ERROR: dataset.json not produced at $DATASET" >&2; exit 1; }

rm -rf "$STUDIO_BENCH_DIR/results"
mkdir -p "$STUDIO_BENCH_DIR/results"
# copy per-run result trees (exclude the built dashboard/ subdir)
( cd "$SRC_DIR/results" && find . -mindepth 1 -maxdepth 1 -type d ! -name dashboard -print0 | \
  xargs -0 -I{} cp -r "{}" "$STUDIO_BENCH_DIR/results/" )
cp "$DATASET" "$STUDIO_BENCH_DIR/dataset.json"
echo "Synced snapshot from $SRC_DIR → $STUDIO_BENCH_DIR (dataset.json + results/)"
```

- [ ] **Step 4: Run test to verify it passes** — `cd dx_benchmark && python -m pytest tests/test_sync_script.py -q` → PASS.

- [ ] **Step 5: Commit** — `git add dx_benchmark/scripts/sync_from_standalone.sh dx_benchmark/tests/test_sync_script.py && git commit -m "feat(benchmark): sync script to bundle standalone snapshot"`.

---

### Task 2: server.py serves the bundled dataset (drop aggregation)

**Files:**
- Modify: `dx_benchmark/server.py` (routes `/api/dataset` ~203, `_regenerate_dataset` ~163, `_aggregate_all_result_dirs` ~74, `/api/config` ~279, `__main__` ~317)
- Test: `tests/launcher/test_benchmark_endpoints.py` (create or extend)

**Interfaces:**
- Consumes: bundled `dx_benchmark/dataset.json` (Task 1).
- Produces: `/api/dataset` returns the bundled file bytes; `/api/results*` reads `dx_benchmark/results/`; `/api/config` returns a static dict. No `dx_benchmark.core.*` import remains.

- [ ] **Step 1: Write the failing test** — spin the handler (or hit the running module) and assert `/api/dataset` returns the bundled JSON and that `import dx_benchmark.server` triggers no `dx_benchmark.core` import.

```python
# tests/launcher/test_benchmark_endpoints.py
import json, urllib.request
def test_dataset_served(benchmark_server):  # fixture: base URL of running module
    body = urllib.request.urlopen(benchmark_server + "/api/dataset", timeout=5).read()
    assert json.loads(body).get("dataset_version") == "v2"

def test_no_core_import():
    import importlib, sys
    sys.modules.pop("dx_benchmark.server", None)
    importlib.import_module("dx_benchmark.server")
    assert not any(m.startswith("dx_benchmark.core") for m in sys.modules)
```

- [ ] **Step 2: Run test to verify it fails** — expected FAIL (`test_no_core_import` fails: server currently imports `core.aggregator`).

- [ ] **Step 3: Edit server.py** — replace `_regenerate_dataset()` body to load `BASE_DIR/"dataset.json"` directly (no aggregation); delete `_aggregate_all_result_dirs()` and both `from dx_benchmark.core...` imports; make `/api/config` return a static dict (the fixed deployment config values currently read from `BenchmarkConfig`, inlined as constants). `/api/dataset` serves `BASE_DIR/"dataset.json"`; on `__main__`, drop the regenerate call (or make it a no-op that just checks the file exists).

- [ ] **Step 4: Run tests** — `python -m pytest tests/launcher/test_benchmark_endpoints.py -q` → PASS; also `python -c "import ast,sys; ast.parse(open('dx_benchmark/server.py').read())"` and a 3.8 parse check.

- [ ] **Step 5: Commit** — `git commit -am "refactor(benchmark): serve bundled dataset, drop core aggregation"`.

---

### Task 3: Delete vendored core/ and dead templates/dashboard/

**Files:**
- Delete: `dx_benchmark/core/`, `dx_benchmark/templates/dashboard/`
- Modify: any test/import referencing them.

- [ ] **Step 1: Prove nothing imports them** — `grep -rnE "dx_benchmark\.core|from \.core|templates/dashboard|core\.aggregator|core\.config" dx_benchmark tests shared launcher | grep -v "\.md:"`. Expected: empty (after Task 2). If any remain, fix them first.
- [ ] **Step 2: Delete** — `git rm -r dx_benchmark/core dx_benchmark/templates/dashboard`.
- [ ] **Step 3: Verify module still boots** — launch the module (via `./launcher.sh` or directly) and confirm `/benchmark/` loads + `/api/dataset` works; run `python -m pytest tests/launcher -q` (or the benchmark subset) → PASS.
- [ ] **Step 4: Commit** — `git commit -m "chore(benchmark): remove vendored core/ and dead templates/dashboard/"`.

---

### Task 4: Dashboard — schema compatibility with the new dataset

**Files:**
- Modify: `dx_benchmark/static/js/dashboard.js`
- Verify live: load `/benchmark/` against a bundled new-tool `dataset.json`.

**Interfaces:**
- Consumes: `state.dataset` = new `dataset.json` v2 `{environments, runs, history, summaries, snapshots}`; env objects expose `npu_sku`, `hw_id`/`hostname`, and now `dx_all_suite_version`, `product_name`, and the new `npu` block (`modules/product/sku`).

- [ ] **Step 1** Load `/benchmark/` with the bundled new dataset; open the browser console. Record every field-access error / `undefined` render (env.npu_sku vs new npu block, missing dx_all_suite_version). This is the concrete work-list.
- [ ] **Step 2** Fix each read so the existing 4 tabs (E2E FPS, Full Metrics, Detailed Data, Version Trend) render without errors against the new schema. Add a small `envLabel(env)`/`envVersion(env)` accessor that tolerates both old (`m1_modules/h1_cards`) and new (`modules/product/sku`, `dx_all_suite_version`) shapes.
- [ ] **Step 3** Live-verify all 4 tabs render (no console errors, charts drawn) in en. Screenshot each tab.
- [ ] **Step 4: Commit** — `git commit -am "fix(benchmark): dashboard reads new dataset schema"`.

---

### Task 5: Dashboard — surface new features (one sub-task per feature)

For **each** feature below, do: (a) add the UI in studio dark-theme style, (b) wire it to the dataset field, (c) live-verify it renders with real data, (d) commit. Keep each feature independently reviewable.

- [ ] **5a — dx-all-suite version filter + Version-Trend grouping.** Add a `dx-all-suite version` filter (field: `env.dx_all_suite_version`, `unknown` bucket allowed) and rework the Version-Trend tab to the new per-metric grouping in studio Canvas style. Target DOM: `.dashboard-tab[data-tab="version-trend"]` area. Live-verify trend lines per version.
- [ ] **5b — ORT ON/OFF comparison.** Surface the automatic ORT on/off pairs (model_results carry both). Add a compare view/toggle. Live-verify both series show.
- [ ] **5c — Thermal / throttle indicators.** Surface `npu_temp_min/max_c`, `npu_clock_mhz_min/max`, `npu_throttled` per run (badge + detail). Live-verify a throttled run flags.
- [ ] **5d — NPU module/product/sku detail + product_name.** Show the richer NPU identity from the new `npu` block + top-level `product_name` in the environment summary. Live-verify.
- [ ] **5e — resume/retry run status.** Surface per-condition `status`/`reason` (partial/failed/retried) where the dataset provides it. Live-verify a partial run renders its status.

(Each 5x ends with a commit `feat(benchmark): dashboard <feature>`.)

---

### Task 6: i18n — new strings in 6 languages

**Files:**
- Modify: `dx_benchmark/static/js/i18n.js`

- [ ] **Step 1** Collect every new user-facing English string introduced in Tasks 4–5 (`grep -oE "_t\('[^']+'\)" static/js/dashboard.js` diff vs baseline; also `data-i18n="…"`). Produce the exact list.
- [ ] **Step 2** Add each to `_DX_I18N_DICT` with ko/ja/zh-CN/zh-TW/es (native-quality, matching the existing entries' tone). English is the key (no `en` field needed, per existing pattern).
- [ ] **Step 3** Live-verify: switch through all 6 languages on each dashboard tab; assert no raw English leaks for the new strings and no layout breakage. `node --check` not applicable; use a headless lang-sweep like the existing i18n browser test.
- [ ] **Step 4: Commit** — `git commit -am "i18n(benchmark): translate new dashboard strings (6 languages)"`.

---

### Task 7: Tutorial rework for the new UI

**Files:**
- Modify: `dx_benchmark/static/js/tutorial.js` (sections `dashboard-fps`/`dashboard-metrics`/`dashboard-detail`/`dashboard-trend`/`results` at lines ~184–352)

**Interfaces:**
- Consumes: the reworked DOM from Tasks 4–5 (new trend layout, version filter, ORT/thermal panels).

- [ ] **Step 1** Diff the DOM targets the tutorial currently uses (`.dashboard-tab[data-tab=…]`, `#fpsRunSelectors`, `data-help-id="bench-*"`, the old single-chart trend `trendMetricFilter`) against the reworked UI. List broken/at-risk steps (esp. Version-Trend steps).
- [ ] **Step 2** Retarget those steps to the new elements; add steps for the new features (version filter, ORT compare, thermal, resume/retry). **Preserve** the recently-landed transient-state mock helpers + `afterStep` cleanup. 6 languages for any new/edited copy.
- [ ] **Step 3** `node --check dx_benchmark/static/js/tutorial.js`; live-verify every touched step spotlights a visible target (rect>2, not display:none) and the `.dxt-spotlight` aligns, in all 6 languages (reuse the earlier iframe-embedded verification method).
- [ ] **Step 4: Commit** — `git commit -am "fix(benchmark): rework tutorial for redesigned dashboard"`.

---

### Task 8: Final integration verification

- [ ] **Step 1** Run the sync script against the real/materialized standalone; confirm bundle populated.
- [ ] **Step 2** Boot the studio (`./launcher.sh`), open `/benchmark/`: all tabs render new data in studio design; Results tab renders REPORT.md + raw JSON; Settings read-only; EdgeGuide links work.
- [ ] **Step 3** `grep -rnE "dx_benchmark\.core|templates/dashboard" dx_benchmark tests shared launcher` → empty.
- [ ] **Step 4** Full 6-language sweep + tutorial spotlight pass (headless), plus `tests/launcher` benchmark subset green.
- [ ] **Step 5** Confirm `pyproject` deps still `[]`; module parses under Python 3.8.
- [ ] **Step 6: Commit** any test/doc updates — `git commit -am "test(benchmark): verify thin-viewer integration end-to-end"`.

---

## Self-Review notes

- **Spec coverage:** thin viewer (Tasks 2–3) · bundled snapshot (Task 1) · drop core/ (Task 3) · delegate execution/browse-only (no run route — enforced by Task 2 leaving no `/api/run`) · dashboard all-features studio-design (Tasks 4–5) · i18n 6-lang (Task 6) · tutorial rework preserving prior fixes (Task 7) · dead templates/dashboard removal (Task 3) · legacy `unknown` bucket (Task 5a) · sync trigger = manual script (Task 1). All spec sections mapped.
- **Open realism note:** Tasks 4–5 (dashboard) and 7 (tutorial) are UI-exploratory; steps specify exact dataset fields, target DOM, and live-verification acceptance rather than pre-fabricated Canvas code, because the exact chart code depends on reading the reworked file — pre-writing 900 lines would be fake precision. Each sub-task is still independently testable via live render + screenshot.
- **Dependency ordering:** Task 1 → 2 → 3 (backend seam first), then 4 → 5 (dashboard), then 6 (i18n of the new strings), then 7 (tutorial of the new DOM), then 8 (verify). i18n/tutorial intentionally follow the UI so they target final strings/DOM.
