from pathlib import Path

import pytest

from calibration import CalibrationSystem
from gestures import GestureDetector

from helpers import make_fist, make_open_palm, make_pointing


class FakeLm:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


def as_landmarks(palm_lms, dx=0.0, dy=0.0):
    return [FakeLm(lm.x + dx, lm.y + dy, lm.z) for lm in palm_lms]


@pytest.fixture
def cal(tmp_path):
    c = CalibrationSystem()
    c.calibration_file = str(tmp_path / "calibration_data.json")
    c.required_samples = 3
    c.start_calibration()
    return c


def _feed(cal, lms, gesture, n=3):
    for _ in range(n):
        done = cal.process_calibration(lms, gesture)
    return done


def test_full_calibration_records_range_and_finger_lengths(cal):
    assert _feed(cal, as_landmarks(make_open_palm(), -0.2, -0.1), "open_palm") is False
    assert cal.calibration_step == 1

    _feed(cal, as_landmarks(make_fist()), "fist")
    assert cal.calibration_step == 2

    _feed(cal, as_landmarks(make_pointing()), "pinch")
    assert cal.calibration_step == 3

    _feed(cal, as_landmarks(make_pointing()), "pointing")
    assert cal.calibration_step == 4

    for i in range(3):
        lms = as_landmarks(make_open_palm(), dx=0.1 * i, dy=0.1 * i)
        done = cal.process_calibration(lms, "none")
    assert done is True
    assert cal.calibration_complete is True
    assert cal.is_calibrating is False

    data = cal.calibration_data
    assert Path(cal.calibration_file).exists()
    assert data["palm_size"] > 0
    assert "index" in data["finger_lengths"]
    assert "open_palm" in data["gesture_thresholds"]
    rx = data["hand_position_range"]["x"]
    ry = data["hand_position_range"]["y"]
    assert rx[1] - rx[0] > 0.05
    assert ry[1] - ry[0] > 0.05


def test_load_calibration_roundtrip(cal, tmp_path):
    _feed(cal, as_landmarks(make_open_palm()), "open_palm")
    _feed(cal, as_landmarks(make_fist()), "fist")
    _feed(cal, as_landmarks(make_pointing()), "pinch")
    _feed(cal, as_landmarks(make_pointing()), "pointing")
    for i in range(3):
        cal.process_calibration(as_landmarks(make_open_palm(), 0.1 * i, 0.1 * i), "none")

    loaded = CalibrationSystem()
    loaded.calibration_file = cal.calibration_file
    assert loaded.load_calibration() is True
    assert loaded.calibration_complete is True
    assert loaded.calibration_data["palm_size"] == cal.calibration_data["palm_size"]


def test_detector_consumes_calibration(cal):
    _feed(cal, as_landmarks(make_open_palm(), -0.1, -0.1), "open_palm")
    _feed(cal, as_landmarks(make_fist()), "fist")
    _feed(cal, as_landmarks(make_pointing()), "pinch")
    _feed(cal, as_landmarks(make_pointing()), "pointing")
    for i in range(3):
        cal.process_calibration(as_landmarks(make_open_palm(), 0.1 * i, 0.1 * i), "none")

    det = GestureDetector()
    det.set_calibration(cal.calibration_data)
    assert det.calibrated is True
    assert det.ref_palm_size == pytest.approx(cal.calibration_data["palm_size"])
    assert det.finger_length_ref


def test_progress_and_instructions(cal):
    assert cal.get_progress() == 0.0
    assert "OPEN PALM" in cal.get_current_step_instruction()
    cal.calibration_step = 5
    assert cal.get_progress() == 1.0
    assert cal.get_current_step_instruction() == "Calibration complete!"


def test_not_calibrating_returns_false(cal):
    cal.stop_calibration()
    assert cal.process_calibration(as_landmarks(make_open_palm()), "open_palm") is False
