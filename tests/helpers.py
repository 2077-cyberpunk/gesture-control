import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_lm(x, y, z=0.0):
    return type("LM", (), {"x": x, "y": y, "z": z})()


def make_open_palm():
    return [
        make_lm(0.50, 0.85),
        make_lm(0.42, 0.78), make_lm(0.36, 0.70), make_lm(0.32, 0.62), make_lm(0.28, 0.55),
        make_lm(0.45, 0.65), make_lm(0.44, 0.50), make_lm(0.43, 0.38), make_lm(0.42, 0.28),
        make_lm(0.50, 0.62), make_lm(0.50, 0.46), make_lm(0.50, 0.33), make_lm(0.50, 0.22),
        make_lm(0.55, 0.64), make_lm(0.56, 0.49), make_lm(0.57, 0.37), make_lm(0.58, 0.27),
        make_lm(0.60, 0.67), make_lm(0.62, 0.54), make_lm(0.63, 0.43), make_lm(0.64, 0.35),
    ]


def make_fist():
    return [
        make_lm(0.50, 0.85),
        make_lm(0.38, 0.78), make_lm(0.42, 0.76), make_lm(0.40, 0.74), make_lm(0.39, 0.79),
        make_lm(0.45, 0.65), make_lm(0.44, 0.60), make_lm(0.45, 0.64), make_lm(0.455, 0.66),
        make_lm(0.50, 0.62), make_lm(0.50, 0.57), make_lm(0.50, 0.61), make_lm(0.50, 0.64),
        make_lm(0.55, 0.64), make_lm(0.55, 0.59), make_lm(0.55, 0.63), make_lm(0.55, 0.66),
        make_lm(0.60, 0.67), make_lm(0.60, 0.62), make_lm(0.60, 0.66), make_lm(0.60, 0.69),
    ]


def make_pointing():
    lms = make_fist()
    lms[5] = make_lm(0.45, 0.65)
    lms[6] = make_lm(0.44, 0.50)
    lms[7] = make_lm(0.43, 0.38)
    lms[8] = make_lm(0.42, 0.28)
    return lms


def make_two_fingers():
    lms = make_pointing()
    lms[4] = make_lm(0.36, 0.76)
    return lms


def make_three_fingers():
    lms = make_two_fingers()
    lms[9] = make_lm(0.50, 0.62)
    lms[10] = make_lm(0.50, 0.46)
    lms[11] = make_lm(0.50, 0.33)
    lms[12] = make_lm(0.50, 0.22)
    return lms


def load_config():
    with open(ROOT / "config.json") as f:
        return json.load(f)
