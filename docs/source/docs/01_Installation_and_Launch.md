# Installation & Launch

## Prerequisites

- **Python 3.12+** (the studio core is pure standard-library; `./launcher.sh`
  self-installs the package with `pip install -e .` on first run, so there's no manual
  install step).
- **Optional:** the dx_app **Model Zoo** tab needs an extra — `pip install -e ".[modelzoo]"`
  (beautifulsoup4 + requests). Without it that one tab shows an in-app notice; everything
  else works.
- For **real** compilation and inference: the **DEEPX SDK** installed from `dx-runtime`
  (runtime, driver, firmware) and/or `dx-compiler` (DX-COM), plus a DEEPX **NPU**.
- Without an NPU/SDK the studio still launches in **demo / mock mode** for exploring the
  UI.

!!! tip "Check your NPU"
    Once the DEEPX runtime is installed, `dxcli --status` (a.k.a. `dxrt-cli --status`)
    lists each NPU device with its RT driver, PCIe driver, and firmware versions. The
    **DX Monitor** tool shows the same information live in the browser.

## Launch

From the `dx-ai-studio` directory:

```bash
./launcher.sh
```

`./launcher.sh` uses `.venv/bin/python` if a virtual environment is present, otherwise
the system `python3`. It starts the **launcher hub** and boots every module server, then
opens your browser at the hub URL.

### Common options

| Option | Effect |
|--------|--------|
| `--port <PORT>` / `-p <PORT>` | Hub port (default **8890**; auto-bumps if busy). |
| `--no-browser` | Start the servers but do not open a browser. |
| `--no-kill` | Do not kill an existing instance on the chosen port. |
| `--fast` | Faster boot (skips some warm-up). |
| `--verbose` / `-v` | Print port-fallback notices when a default port is busy. |

You can also run the launcher directly:

```bash
python3 launcher/launcher.py --port 8890 --no-browser
```

### Port map

The hub reverse-proxies each module, so you only ever open the **hub** URL. Module
servers bind to ephemeral ports internally; the defaults (overridable via `DX_*_PORT`
environment variables) are:

| Component | Env var | Default |
|-----------|---------|---------|
| Launcher hub | `DX_LAUNCHER_PORT` | 8890 |
| DX App | `DX_APP_PORT` | 8080 |
| DX Stream | `DX_STREAM_PORT` | 8093 |
| DX Model Zoo | `DX_ZOO_PORT` | 8094 |
| DX Compiler | `DX_COMPILER_PORT` | 8095 |
| DX EdgeGuide | `DX_PLANNER_PORT` | 8096 |
| DX Benchmark | `DX_BENCHMARK_PORT` | 8097 |
| DX Monitor | `DX_MONITOR_PORT` | 8098 |

## Boot & health

When the page first loads, the studio shows a brief splash / boot gate while the module
servers come up. Navigation is gated until the studio reports **ready** — this is normal
and prevents opening a tool before its server is listening.

!!! note "Opening the page the instant the server appears"
    If you open the hub the moment the port starts listening (e.g. clicking an IDE
    "open in browser" popup immediately), some modules may still be starting. The studio
    handles this automatically: it retries module entry during a startup window and waits
    for the ready signal, so simply give it a moment or refresh.

## Stopping

Stop the launcher process (`Ctrl+C` in the terminal that ran `./launcher.sh`). Re-running
`./launcher.sh` on a busy port auto-bumps to the next free port unless you pass
`--no-kill`.
