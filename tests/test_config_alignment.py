import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _handler_keys():
    tree = ast.parse((ROOT / "actions.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "action_handlers":
                    if isinstance(node.value, ast.Dict):
                        keys = set()
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant):
                                keys.add(k.value)
                        return keys
    raise AssertionError("action_handlers dict not found in actions.py")


def _combo_actions():
    src = (ROOT / "gestures.py").read_text()
    block = re.search(r"combos\s*=\s*\{(.*?)\}", src, re.S)
    assert block, "combos dict not found"
    return set(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', block.group(1)))


def test_config_actions_have_handlers():
    config = json.loads((ROOT / "config.json").read_text())
    handlers = _handler_keys()
    missing = []
    for gesture, cfg in config["actions"].items():
        action = cfg.get("action")
        if not action:
            missing.append(f"{gesture}: no action field")
        elif action not in handlers:
            missing.append(f"{gesture} -> {action}")
    assert not missing, f"config actions missing handlers: {missing}"


def test_config_entries_have_descriptions():
    config = json.loads((ROOT / "config.json").read_text())
    for gesture, cfg in config["actions"].items():
        assert "description" in cfg, f"{gesture} missing description"


def test_combo_detection_maps_to_config_actions():
    config = json.loads((ROOT / "config.json").read_text())
    handlers = _handler_keys()
    combos = _combo_actions()
    assert len(combos) >= 8
    for _pattern, combo_name in combos:
        assert combo_name in config["actions"], f"{combo_name} missing from config"
        action = config["actions"][combo_name]["action"]
        assert action in handlers, f"{combo_name} -> {action} has no handler"


def test_mode_actions_have_handlers():
    config = json.loads((ROOT / "config.json").read_text())
    handlers = _handler_keys()
    mode_actions = config.get("mode_actions", {})
    assert "presentation" in mode_actions
    assert "gaming" in mode_actions
    for mode, mapping in mode_actions.items():
        for gesture, action in mapping.items():
            if action == "gaming_move":
                continue
            assert action in handlers, f"mode {mode}: {gesture} -> {action} has no handler"


def test_continuous_actions_cover_gaming_keys():
    src = (ROOT / "gesture_controller.py").read_text()
    for key in ("gaming_w", "gaming_space", "gaming_4", "presentation_pointer"):
        assert key in src
