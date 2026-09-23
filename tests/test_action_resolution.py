import json
import time
from pathlib import Path
from types import SimpleNamespace

import actions as actions_mod
from actions import GestureActions
from gesture_controller import GestureController


def make_controller(mode="normal"):
    root = Path(__file__).resolve().parent.parent
    c = GestureController.__new__(GestureController)
    c.config = json.loads((root / "config.json").read_text())
    c.actions = SimpleNamespace(mode=mode, mode_set=None)
    return c


def test_gaming_quadrant_top_is_w():
    c = make_controller()
    assert c._gaming_quadrant_action((100, 50), 640, 480) == "gaming_w"


def test_gaming_quadrant_bottom_is_s():
    c = make_controller()
    assert c._gaming_quadrant_action((100, 430), 640, 480) == "gaming_s"


def test_gaming_quadrant_left_is_a():
    c = make_controller()
    assert c._gaming_quadrant_action((50, 240), 640, 480) == "gaming_a"


def test_gaming_quadrant_right_is_d():
    c = make_controller()
    assert c._gaming_quadrant_action((590, 240), 640, 480) == "gaming_d"


def test_gaming_quadrant_dead_zone():
    c = make_controller()
    assert c._gaming_quadrant_action((320, 240), 640, 480) is None


def test_presentation_mode_overrides():
    c = make_controller("presentation")
    assert c._resolve_action("fist", None, 640, 480) == "presentation_black"
    assert c._resolve_action("open_palm", (10, 10), 640, 480) == "presentation_pointer"
    assert c._resolve_action("swipe_left", None, 640, 480) == "presentation_prev"


def test_gaming_mode_overrides():
    c = make_controller("gaming")
    assert c._resolve_action("fist", None, 640, 480) == "gaming_space"
    assert c._resolve_action("peace", None, 640, 480) == "gaming_shift"
    assert c._resolve_action("open_palm", (100, 50), 640, 480) == "gaming_w"


def test_normal_mode_falls_back_to_config():
    c = make_controller("normal")
    assert c._resolve_action("fist", None, 640, 480) == "left_click"
    assert c._resolve_action("combo_zoom", None, 640, 480) == "zoom_in"
    assert c._resolve_action("combo_deselect", None, 640, 480) == "escape"


def test_unknown_combo_falls_back_to_gesture_name():
    c = make_controller("normal")
    assert c._resolve_action("some_new_combo", None, 640, 480) == "some_new_combo"


def test_execute_action_records_history_for_combo():
    a = GestureActions()
    a.tts_enabled = False
    a.execute("escape", None, 640, 480, 1.0)
    assert a.action_history[-1]["action"] == "escape"


def test_hand_range_normalizes():
    a = GestureActions()
    a.set_hand_range({"x": [0.3, 0.7], "y": [0.2, 0.8]})
    assert a._normalize_hand((0.3, 0.2), 640, 480) == (0.0, 0.0)
    assert a._normalize_hand((0.7, 0.8), 640, 480) == (1.0, 1.0)
    nx, ny = a._normalize_hand((0.5, 0.5), 640, 480)
    assert abs(nx - 0.5) < 1e-9
    assert abs(ny - 0.5) < 1e-9
    assert a._normalize_hand((0.0, 0.0), 640, 480) == (0.0, 0.0)


def test_hand_range_defaults_to_frame():
    a = GestureActions()
    a.set_hand_range(None)
    nx, ny = a._normalize_hand((320, 240), 640, 480)
    assert abs(nx - 0.5) < 1e-9
    assert abs(ny - 0.5) < 1e-9


def test_gaming_key_hold_and_release():
    a = GestureActions()
    a.tts_enabled = False
    a._gaming_key("w")
    assert a.active_gaming_key == "w"
    a._gaming_key("w")
    assert a.active_gaming_key == "w"
    a._gaming_key("space")
    assert a.active_gaming_key == "space"
    a.gaming_hold_until = time.time() - 1
    a.tick()
    assert a.active_gaming_key is None


def test_low_confidence_ignored():
    a = GestureActions()
    a.execute("left_click", None, 640, 480, 0.3)
    assert a.action_history == []


def test_is_windows_flag_exists():
    assert isinstance(actions_mod.IS_WINDOWS, bool)
    if not actions_mod.IS_WINDOWS:
        assert actions_mod.user32 is None
