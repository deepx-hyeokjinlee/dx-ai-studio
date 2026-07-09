# DX Benchmark

Browse and compare DEEPX NPU benchmark results in your browser — throughput, latency,
and multi-stream numbers per model, with charts.

![DX Benchmark — the performance dashboard: environment selection and E2E FPS by model size.](../resources/benchmark.png)

## Using it

1. Open the dashboard to see the benchmark **results** (from the latest benchmark run).
2. **Filter and compare** models by AI task and model size; read throughput / latency /
   max-channel figures.
3. Use the **charts** and tables to compare models and pick one for your workload
   (**[DX EdgeGuide](09_DX_EdgeGuide.md)** uses the same data to recommend hardware).

## Key features

- **NPU benchmark results** — throughput (FPS), latency (ms), and multi-stream channel
  measurements per model.
- **Comparison charts** across models and sizes.

!!! note
    The dashboard is **read-only**; the benchmark runs themselves are produced by the
    DEEPX benchmark tooling, and their results feed this view (and DX EdgeGuide).
