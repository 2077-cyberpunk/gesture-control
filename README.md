# Gesture Controller

[![CI](https://github.com/2077-cyberpunk/gesture-control/actions/workflows/ci.yml/badge.svg)](https://github.com/2077-cyberpunk/gesture-control/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Tony Stark–style hand gesture control for your computer. Webcam in, mouse/keyboard out — no controller needed.

Built with **MediaPipe**, **OpenCV**, and **PyAutoGUI**.

## Features

- **Mouse control** — move the cursor with an open palm
- **Clicks & scrolling** — fist = left click, pinch = right click, point up/down = scroll
- **Media & system keys** — volume, play/pause, tracks, screenshots, window management
- **Modes** — Normal / Presentation / Gaming (mode-specific gesture mappings)
- **Gesture combos** — sequences within 2 seconds (e.g. fist → open palm = release drag)
- **Calibration** — learn your hand size and reach for more accurate control
- **Macros** — record and playback gesture sequences
- **Multi-monitor** — cursor maps across detected displays
- **HUD overlay** — live gesture state, confidence, FPS, action log
- **System tray** — mode switch, calibration, macros from the tray icon

## Requirements

- Python 3.10+
- A webcam
- OS with a desktop session (Windows, Linux, or macOS)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The hand landmark model (`hand_landmarker.task`) is downloaded automatically on first run.

## Usage

```bash
python gesture_controller.py
```

| Flag | Description |
|------|-------------|
| `--camera N` | Camera device id (overrides `config.json`) |
| `--mode MODE` | Start in `normal`, `presentation`, or `gaming` |
| `--demo` | Run without a camera (HUD preview only) |
| `--config PATH` | Alternate config file |
| `--list` | List all gestures & actions |
| `--controls` | List keyboard shortcuts |
| `--help` | Full help |

```bash
python gesture_controller.py --camera 1 --mode gaming
python gesture_controller.py --demo
```

| Key | Action |
|-----|--------|
| `q` | Quit |
| `h` | Toggle HUD |
| `l` | Toggle action log |
| `g` | Toggle gesture guide |
| `p` | Toggle performance panel |
| `c` | Start calibration |
| `r` | Reset calibration |
| `m` | Cycle mode (Normal → Presentation → Gaming) |
| `1` / `2` / `3` | Start / stop recording, play last macro |
| `s` | Save config |

```bash
python gesture_controller.py --list       # list gestures & actions
python gesture_controller.py --controls   # keyboard shortcuts
python gesture_controller.py --help
```

## Gestures (Normal mode)

| Gesture | Action |
|---------|--------|
| Open palm | Move mouse |
| Fist | Left click |
| Pinch | Right click |
| Point up / down | Scroll up / down |
| Point | Double click |
| Peace | Volume up |
| Thumbs up / down | Play/pause, volume down |
| Swipe left / right | Next / previous track |
| Two fingers | Copy (Ctrl+C) |
| Three fingers | Paste (Ctrl+V) |
| Four fingers | Undo (Ctrl+Z) |
| Rock | Screenshot |
| Shaka | New browser tab |

**Combos** (within 2s): fist→open palm, open palm→fist, peace↔fist, thumbs up→down, pinch→pinch, and more.

**Presentation mode:** open palm = laser pointer, fist = black screen, swipes = next/prev slide.

**Gaming mode:** open palm quadrant = WASD, fist = space, peace = shift, pinch = E, etc.

Full list: see [GESTURE_GUIDE.txt](GESTURE_GUIDE.txt).

## Calibration

1. Press `c`
2. Show **open palm**, **fist**, **pinch**, **pointing** when prompted
3. Move your hand around the screen area
4. Saves automatically to `calibration_data.json`

Press `r` to reset.

## Configuration

Edit `config.json` to remap gestures, change the camera id, or adjust mode-specific actions.

- **`disabled_gestures`** — list of gesture names to ignore (e.g. `["swipe_left", "swipe_right"]` if swipes false-positive).
- Config is validated at startup; malformed JSON or missing fields fail fast with a clear error.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

CI runs lint + tests on every push/PR (Python 3.10–3.12).

## Project layout

```
gesture_controller.py  # main loop / app shell
gestures.py            # MediaPipe hand tracking + gesture state machine
actions.py             # mouse, keyboard, media, window, gaming actions
feedback.py            # HUD, notifications, calibration UI
calibration.py         # hand size / reach calibration
macros.py              # record & playback
monitor.py             # multi-monitor detection
tray.py                # system tray icon
config.json            # gesture → action mapping
tests/                 # pytest suite
```

## Notes

- PyAutoGUI's corner fail-safe is respected; if the cursor hits a screen corner, the action is retried once with the fail-safe temporarily disabled (and logged).
- Keep your hand 1–2 feet from the camera with decent lighting for best results.

## License

[MIT](LICENSE)
