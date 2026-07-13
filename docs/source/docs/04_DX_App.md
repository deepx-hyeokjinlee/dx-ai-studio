# DX App

Run AI inference on the DEEPX NPU from your browser — pick a model, run it on images,
video, a camera or an RTSP stream, watch live results, and benchmark or compare models.

![DX App — the Models page with task filters, the model table, and the live NPU monitor.](../resources/app.png)

## Using it

The dashboard opens on a set of pages (top navigation):

- **Setup** — guided environment check; run it first so the NPU / runtime is ready.
- **Models** — browse the model registry across **23 AI tasks** (object / face / OBB
  detection, classification, semantic & instance segmentation, pose & keypoint estimation,
  depth, super-resolution, denoising, enhancement, embedding, ReID, hand detection &
  landmark, attribute recognition, PPU, **3D object detection**, **object pose
  estimation**, **panoptic driving perception**, …); open a model to see its details.
- **Run** — pick a **category → model → input**, then Run. Inputs are chosen per category:
  a sample image, your **own uploaded image**, video, camera, or RTSP (some tasks are
  image-only, and special inputs like 3D LiDAR `.bin` are offered where they apply). The
  annotated result appears live, with a **before/after compare slider** for image runs.
  Multiple streams can run at once.
- **Bench** / **Compare** — measure a model's throughput and compare models side by side.
- **Model Zoo** — download additional models into the app. Needs the optional `[modelzoo]`
  extra (`pip install -e ".[modelzoo]"`); without it this tab shows an in-app notice.
- **Lab** — scaffold a new model / task from a template (developer portal).
- **Outputs** — browse and manage saved inference results.
- **Reference** — SDK documentation.

## Key features

- **Multiple input types** — sample or uploaded image, video file, USB camera, and RTSP streams.
- **Before/after compare slider** — drag to compare the original against the annotated result.
- **Live multi-stream** — several inference streams running and displaying at once.
- **Benchmark & compare** — throughput / latency numbers per model, side by side.
- **AI assistant** chat (floating button) for help with the workflow.
- Works **without an NPU** too (falls back to mock data for exploring the UI).

!!! note "Related"
    Run the `.dxnn` files produced by **[DX Compiler](03_DX_Compiler.md)**; the same
    NPU telemetry is visualized live in **[DX Monitor](08_DX_Monitor.md)**.
