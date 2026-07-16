# DX AI Studio — dx-benchmark thin-viewer integration (design)

Date: 2026-07-16
Status: approved (design); pending spec review → implementation plan

## Context

`dx-benchmark` is being relocated from an internal package under
`dx-runtime/dx_stream/` to a standalone **top-level suite feature**
(`dx-all-suite/dx-benchmark`, branch `feat/dx-benchmark-suite-relocation`,
"YOLO26 Benchmark Tool"). It was heavily redesigned: CLI-first (`run.sh`,
`setup.sh`, `setup_env.sh`, `benchmark/` package) plus a self-contained **static
HTML dashboard** (`benchmark/dashboard/`, built via `dashboard_builder.py`).

DX AI Studio currently ships its own interactive `/benchmark/` web module
(`dx-ai-studio/dx_benchmark/`): `server.py` + SPA (`static/js/`
dashboard/results/settings) + 6-language i18n + a 50-step tutorial + launcher
reverse-proxy integration + a **vendored copy of the benchmark package**
(`dx_benchmark/core/`).

A comparative survey (2026-07-16) found the two are **two divergent lineages of
the same codebase**, not old-vs-new:

- Per-run result JSON schema is **identical**; `dataset.json` is the same **v2**
  shape → structurally consumable by the studio SPA.
- The `environment.json` `npu` block **diverged** (new: `modules/product/sku/…`;
  studio: `sku/h1_cards/m1_modules/…`). New adds top-level
  `dx_all_suite_version` + `product_name`.
- The Python packages drifted **both** ways: studio `core/` has 5 extra modules
  (`pipeline_sweeps`, `report_models`, `report_renderers`, `runner_contracts`,
  `run_orchestrator`) and lacks `npu_catalog`; the new `benchmark/` has
  `npu_catalog` and the redesigned Version-Trend dashboard.
- New tool has **no i18n and no tutorial** (English, server-less); the studio
  module has both.

Root problem: the benchmark logic exists in **two copies** that drift.

## Goal

Reconcile the studio `/benchmark/` module with the relocated standalone
`dx-benchmark` so that:

1. The duplicate benchmark package is eliminated (standalone is canonical).
2. The studio keeps its UX standard: studio dark-theme design, 6-language i18n,
   in-app tutorial, Results browsing, launcher integration.
3. **All** new features/data from the redesigned tool are surfaced in the studio
   dashboard.

Non-goal: changing the standalone `dx-benchmark` tool itself, or adding a
web-triggered benchmark run to the studio (execution stays CLI/standalone).

## Decision: thin viewer

The studio `/benchmark/` becomes a **thin viewer** over the standalone tool.

- **Canonical** = standalone `dx-all-suite/dx-benchmark` (owns runners,
  aggregation, `dataset.json` build, results schema, `npu_catalog`).
- The studio **keeps** `server.py`, the SPA, i18n, the tutorial, and launcher
  integration, but **drops the vendored `core/` package**.
- **Execution is delegated** to the standalone tool (CLI). The studio web stays
  **browse-only** (no `/api/run`, no run button) — matching current behaviour
  and the existing "CLI-only execution" tutorial messaging.

### Rejected alternatives

- **Adapt** (keep studio SPA + re-sync vendored `core/`): keeps the duplicate
  package → perpetual drift. Rejected.
- **Replace** (embed the standalone static dashboard): loses studio i18n,
  tutorial, Results tab, studio chrome; the static dashboard is English-only and
  server-less. Rejected.

## Architecture

### Data flow — bundled snapshot

- A **sync script** in the studio (`scripts/`), run manually at release/build
  time, invokes the standalone tool's aggregate/dashboard step to build
  `dataset.json`, then copies `results/**` + `dataset.json` into the studio
  bundle (`dx_benchmark/results/` + a committed portable `dataset.json`). This
  matches the studio's existing committed-portable-dataset pattern.
  - Trigger: **manual release step** (not CI — the suite CI is air-gapped).
- `server.py` **serves** the bundled artifacts directly:
  - `/api/dataset` → the bundled `dataset.json` (no runtime aggregation).
  - `/api/results`, `/api/results/<hw>/<run>[/report]` → the bundled
    `results/*.json` + `REPORT.md`.
  - `/api/config` stays read-only (501 on POST).
  - The `core.aggregator` import and the on-startup `_regenerate_dataset()` are
    removed once the bundled dataset is authoritative.

### Schema

- Consume the standalone dataset (`v2`) and the new `environment.json` `npu`
  block (`modules/product/sku`) + top-level `dx_all_suite_version` /
  `product_name`. Because the **standalone** builds `dataset.json` (with its
  `npu_catalog`), the studio consumes a correct env summary and needs no
  `npu_catalog` of its own.
- **Legacy studio-era runs** (no `dx_all_suite_version`) bucket as `unknown` in
  Version Trend. Accepted as-is — no backfill (historical runs never recorded
  the version, and the current re-measurement produces all-new-tool data, so the
  `unknown` bucket will rarely appear).

### Frontend (studio-styled, full feature/data parity)

Rework `dx_benchmark/static/js/dashboard.js` to surface **all** new
features/data, rendered in the **studio design** (dark theme, Canvas charts,
studio chrome — not the English static dashboard's look):

- Version Trend with the new grouping (per-metric small-multiples), styled
  studio-way, with the `dx_all_suite_version` filter.
- ORT ON/OFF comparison, thermal / throttle indicators, NPU module/product/sku
  detail, resume/retry status — wherever the new dataset provides them.
- Keep the Results tab (rendered `REPORT.md` + raw JSON drill-down), read-only
  Settings, and EdgeGuide deep-links.

### i18n

Add every new UI string introduced by the reworked dashboard to
`static/js/i18n.js` (`_DX_I18N_DICT`) in all **6 languages**
(ko/en/ja/zh-CN/zh-TW/es), keyed by English string, matching the existing
mechanism. New strings include Version-Trend group/metric labels, the
`dx-all-suite version` filter, ORT tooltip, thermal/throttle labels, and NPU
module/product/sku labels.

### Tutorial

Rework `static/js/tutorial.js` for the new UI: retarget/added steps for the new
Version-Trend layout, new panels, and filters, in all 6 languages. **Preserve**
the recently-landed transient-state fixes (mock previews via `beforeStep`,
`afterStep` cleanup) and re-point steps whose target DOM changed.

### Cleanup

- Remove the dead, unreferenced `dx_benchmark/templates/dashboard/` (vendored
  static-dashboard copy not used by `server.py` or the SPA).
- Remove the vendored `dx_benchmark/core/` package once `server.py` no longer
  imports it.

## Risks / open items

- **Path/deploy coupling of the sync step**: the sync script assumes the
  standalone `dx-benchmark` is reachable at build time (sibling suite dir). Must
  be documented and fail loudly if absent.
- **Divergence check**: after dropping `core/`, verify no other studio code
  imports `dx_benchmark.core.*` (server.py, tests). A grep gate is part of the
  plan.
- **Tutorial/i18n churn**: the dashboard rework will move DOM targets; the
  tutorial + i18n passes must run against the reworked UI, verified live
  (spotlight alignment, all 6 languages).

## Out of scope

- Modifying the standalone `dx-benchmark` tool.
- Web-triggered benchmark execution / a run button in the studio.
- The relocation itself (moving `dx-benchmark` to the suite top level) — owned by
  the release branch; this spec covers only the studio-side integration.

## Verification

- `server.py` serves the bundled dataset + results with `core/` removed (no
  import errors; existing `tests/launcher` + module tests pass).
- Studio dashboard renders all new features/data from a real new-tool
  `dataset.json`, in studio design, across all 6 languages.
- Tutorial steps spotlight their (possibly moved) targets live in all 6
  languages.
- No `dx_benchmark.core` references remain.
