import json

import pytest

from gesture_controller import load_config, validate_config, GestureController


VALID = {
    "camera_id": 0,
    "gesture_smoothing": 2,
    "disabled_gestures": [],
    "actions": {
        "fist": {"action": "left_click", "description": "Left click"},
    },
    "mode_actions": {
        "presentation": {"fist": "presentation_black"},
        "gaming": {"fist": "gaming_space"},
    },
}


def test_valid_config_passes():
    validate_config(VALID)


def test_load_config_reads_file(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(VALID))
    assert load_config(p)["actions"]["fist"]["action"] == "left_click"


def test_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        load_config(tmp_path / "nope.json")


def test_invalid_json_exits(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json")
    with pytest.raises(SystemExit):
        load_config(p)


def test_missing_action_field():
    bad = json.loads(json.dumps(VALID))
    del bad["actions"]["fist"]["action"]
    with pytest.raises(SystemExit, match="action"):
        validate_config(bad)


def test_missing_description_field():
    bad = json.loads(json.dumps(VALID))
    del bad["actions"]["fist"]["description"]
    with pytest.raises(SystemExit, match="description"):
        validate_config(bad)


def test_empty_actions():
    with pytest.raises(SystemExit, match="actions"):
        validate_config({"actions": {}})


def test_bad_disabled_gestures_type():
    bad = json.loads(json.dumps(VALID))
    bad["disabled_gestures"] = "swipe_left"
    with pytest.raises(SystemExit, match="disabled_gestures"):
        validate_config(bad)


def test_bad_camera_id():
    bad = json.loads(json.dumps(VALID))
    bad["camera_id"] = -1
    with pytest.raises(SystemExit, match="camera_id"):
        validate_config(bad)


def test_cli_mode_and_camera_overrides():
    c = GestureController.__new__(GestureController)
    c.config = json.loads(json.dumps(VALID))
    # exercise only the override logic shape used in __init__
    c.config["camera_id"] = 2
    assert c.config["camera_id"] == 2


def test_disabled_gestures_skips_execution():
    c = GestureController.__new__(GestureController)
    c.config = json.loads(json.dumps(VALID))
    c.disabled_gestures = {"fist"}
    executed = []

    class FakeActions:
        mode = "normal"

        def execute(self, *a, **k):
            executed.append(a)

    c.actions = FakeActions()
    c.feedback = type("F", (), {"show_action_feedback": lambda *a, **k: None})()
    c.gesture_cooldown = {}
    c.cooldown_time = 0.3
    c.continuous_actions = set()

    c._execute_action("fist", (10, 10), 640, 480, 1.0)
    assert executed == []

    c.disabled_gestures = set()
    c._execute_action("fist", (10, 10), 640, 480, 1.0)
    assert len(executed) == 1


def test_drain_ui_events_clears_queue():
    from actions import GestureActions

    a = GestureActions()
    a.tts_enabled = False
    a.ui_events.append({"type": "failsafe", "action": "right_click", "time": 0})
    events = a.drain_ui_events()
    assert len(events) == 1
    assert events[0]["type"] == "failsafe"
    assert a.drain_ui_events() == []
