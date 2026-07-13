# The Hub

The **hub** is the landing page that ties the studio together. Every tool is launched
from here and every tool is reached through the hub's address bar — you never open a
module's port directly.

![The hub's orbital launcher — the eight tools orbit the central DEEPX mark, each showing its online status.](../resources/hub.png)

## Layout

- **Orbital launcher** — the eight tools orbit the central DEEPX mark. Click a tile to
  open that tool; the shell swaps to the module while the hub chrome stays in place.
- **Top bar** — language switcher, the guided-tutorial toggle, and a shortcut to the
  DEEPX store / "Buy now".
- **Hub views** — besides the eight tools, the hub hosts the **SDK Library** (in-app
  DEEPX documentation and brochures) and the **About DEEPX** page. See
  [SDK Library & About](11_SDK_Library_and_About.md).

## Navigating

- Click any orbital tile to enter a tool; use the top navigation or the browser **Back**
  button to return to the hub.
- The current tool and its view are reflected in the **URL**, so links are shareable and
  reload-safe (for example, a DX EdgeGuide recommendation or an SDK Library document can
  be linked directly).
- **Keyboard shortcuts** — `Alt`+`1`…`8` jump straight to a tool; `Esc` backs out of a
  tool or closes an open panel.

## Language

The entire studio is available in **6 languages** — English, 한국어, 日本語, 简体中文,
繁體中文, Español. Switch from the top bar at any time; the choice persists.

## Guided tutorials

Several tools ship an in-app guided tutorial. Toggle tutorial mode from the top bar to
get step-by-step callouts over the live UI. Tutorials are optional and can be replayed.

## Demo / mock mode

The hub and every tool are fully browsable without an NPU or the SDK. In that state each
tool falls back to representative **sample / mock data** and indicates that it is not
showing live hardware results — useful for evaluation, demos, and screenshots.
