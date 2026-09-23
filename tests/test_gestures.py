import pytest

import gestures as gestures_mod
from gestures import GestureDetector, GestureState

from helpers import make_fist, make_open_palm, make_pointing, make_two_fingers, make_three_fingers


class FakeClock:
    def __init__(self, start=1000.0):
        self.t = start

    def time(self):
        return self.t

    def advance(self, dt):
        self.t += dt


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr(gestures_mod, "time", c)
    return c


@pytest.fixture
def detector():
    return GestureDetector(smoothing=4)


def test_combo_fist_then_open_palm(detector, clock):
    clock.t = 1000.0
    detector.combo_last_time = 0.0
    assert detector.add_combo("fist") is None
    assert detector.add_combo("open_palm") == "combo_grab_release"
    assert detector.get_combo_history() == []


def test_combo_requires_sequence_within_timeout(detector, clock):
    clock.t = 1000.0
    detector.combo_last_time = 1000.0
    assert detector.add_combo("fist") is None
    clock.t = 1003.5
    result = detector.add_combo("open_palm")
    assert result is None


def test_combo_double_pinch(detector, clock):
    clock.t = 1000.0
    detector.combo_last_time = 0.0
    assert detector.add_combo("pinch") is None
    assert detector.add_combo("pinch") == "combo_zoom"


def test_state_machine_confirms_gesture(detector, clock):
    landmarks = make_open_palm()
    gesture, conf = detector.detect_gesture(landmarks, 640, 480, hand_id=0)
    assert gesture == "none"
    assert detector.hand_states[0]["state"] == GestureState.DETECTED

    clock.advance(0.15)
    gesture, conf = detector.detect_gesture(landmarks, 640, 480, hand_id=0)
    assert gesture == "open_palm"
    assert conf >= 0.5
    assert detector.hand_states[0]["state"] == GestureState.CONFIRMED


def test_state_machine_per_hand_independent(detector, clock):
    palm = make_open_palm()
    fist = make_fist()

    detector.detect_gesture(palm, 640, 480, hand_id=0)
    detector.detect_gesture(fist, 640, 480, hand_id=1)
    clock.advance(0.15)
    g0, _ = detector.detect_gesture(palm, 640, 480, hand_id=0)
    g1, _ = detector.detect_gesture(fist, 640, 480, hand_id=1)

    assert g0 == "open_palm"
    assert g1 == "fist"
    assert detector.hand_states[0]["state"] == GestureState.CONFIRMED
    assert detector.hand_states[1]["state"] == GestureState.CONFIRMED


def test_classify_fist_and_pointing(detector):
    g, conf = detector._classify_gesture_precise(
        [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in make_fist()], 0
    )
    assert g == "fist"

    g, conf = detector._classify_gesture_precise(
        [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in make_pointing()], 0
    )
    assert g in ("pointing", "pointing_up")


def test_classify_two_and_three_fingers(detector):
    g, conf = detector._classify_gesture_precise(
        [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in make_two_fingers()], 0
    )
    assert g == "two_fingers"

    g, conf = detector._classify_gesture_precise(
        [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in make_three_fingers()], 0
    )
    assert g == "three_fingers"


def test_swipe_returns_immediately(detector, clock):
    clock.t = 1000.0

    class LM:
        def __init__(self, x, y, z=0.0):
            self.x, self.y, self.z = x, y, z

    lm_left = [LM(0.50, 0.5) for _ in range(21)]
    lm_right = [LM(0.40, 0.5) for _ in range(21)]

    assert detector.detect_gesture(lm_left, 640, 480, hand_id=0)[0] == "none"
    gesture, conf = detector.detect_gesture(lm_right, 640, 480, hand_id=0)
    assert gesture == "swipe_left"
    assert conf >= 0.5


def test_swipe_uses_hand_id(detector):
    left = [{"x": 0.50, "y": 0.5, "z": 0}] * 21
    right = [{"x": 0.40, "y": 0.5, "z": 0}] * 21
    assert detector._detect_swipe(left, hand_id=0) is None
    assert detector._detect_swipe(right, hand_id=0) == "swipe_left"
    assert detector._detect_swipe(right, hand_id=1) is None


def test_set_calibration_applies(detector):
    detector.set_calibration({
        "palm_size": 0.2,
        "finger_lengths": {"index": {"mean": 0.25, "std": 0.01}},
    })
    assert detector.calibrated is True
    assert detector.ref_palm_size == 0.2
    assert "index" in detector.finger_length_ref

    detector.set_calibration(None)
    assert detector.calibrated is False
    assert detector.ref_palm_size == 0.15


def test_get_gesture_state_defaults_idle(detector):
    assert detector.get_gesture_state() == "idle"
