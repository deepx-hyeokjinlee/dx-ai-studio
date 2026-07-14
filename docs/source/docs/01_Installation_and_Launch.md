# Installation & Launch

## Prerequisites

- **Python 3.12+**. `./launcher.sh` installs the package automatically on first run —
  no manual install step, no third-party dependencies.
- For **real** compilation and inference: the **DEEPX SDK** (from `dx-runtime` /
  `dx-compiler`) and a DEEPX **NPU**. Without them the studio still launches in
  **demo / mock mode** for exploring the UI.

!!! tip "Check your NPU"
    Once the DEEPX runtime is installed, `dxcli --status` lists each NPU device with its
    driver and firmware versions. **DX Monitor** shows the same info live in the browser.

## Launch

From the `dx-ai-studio` directory:

```bash
./launcher.sh
```

It starts the launcher hub, boots every module server, and opens your browser at the
hub URL. On first load a brief splash appears while servers start — give it a moment if
a tool isn't ready yet.

### Common options

| Option | Effect |
|--------|--------|
| `--port <PORT>` / `-p <PORT>` | Hub port (default **8890**; auto-bumps if busy). |
| `--no-browser` | Start the servers but do not open a browser. |

Run `./launcher.sh --help` for the full flag list. The hub proxies all modules, so you
only ever open the hub port.

## Stopping

`Ctrl+C` in the terminal running `./launcher.sh`. Re-running on a busy port auto-bumps
to the next free port unless you pass `--no-kill`.
