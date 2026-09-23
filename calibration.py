import numpy as np
import json
import os


class CalibrationSystem:
    FINGERS = ("thumb", "index", "middle", "ring", "pinky")

    def __init__(self):
        self.is_calibrating = False
        self.calibration_step = 0
        self.calibration_data = {
            "palm_size": 0.15,
            "finger_lengths": {},
            "gesture_thresholds": {},
            "hand_position_range": {"x": [0, 1], "y": [0, 1]},
        }
        self.calibration_samples = []
        self.required_samples = 30
        self.sample_buffer = []
        self.calibration_complete = False
        self.calibration_file = "calibration_data.json"
        self._palm_samples = []
        self._finger_samples = {name: [] for name in self.FINGERS}
        self._range_min = {"x": 1.0, "y": 1.0}
        self._range_max = {"x": 0.0, "y": 0.0}

    def start_calibration(self):
        self.is_calibrating = True
        self.calibration_step = 0
        self.calibration_samples = []
        self.sample_buffer = []
        self.calibration_complete = False
        self._palm_samples = []
        self._finger_samples = {name: [] for name in self.FINGERS}
        self._range_min = {"x": 1.0, "y": 1.0}
        self._range_max = {"x": 0.0, "y": 0.0}

    def stop_calibration(self):
        self.is_calibrating = False
        self.calibration_step = 0
        self.sample_buffer = []

    def process_calibration(self, hand_landmarks, detected_gesture):
        if not self.is_calibrating:
            return False

        landmarks = []
        for lm in hand_landmarks:
            landmarks.append({"x": lm.x, "y": lm.y, "z": lm.z})

        self._track_range(landmarks)

        expected_gestures = ["open_palm", "fist", "pinch", "pointing", "unknown"]

        if self.calibration_step < len(expected_gestures):
            expected = expected_gestures[self.calibration_step]

            if detected_gesture == expected or (expected == "unknown" and detected_gesture not in expected_gestures[:4]):
                self.sample_buffer.append(landmarks)

                if len(self.sample_buffer) >= self.required_samples:
                    self._process_samples(expected)
                    self.calibration_step += 1
                    self.sample_buffer = []

                    if self.calibration_step >= len(expected_gestures):
                        self._finalize_calibration()
                        return True

        return False

    def _track_range(self, landmarks):
        cx = (landmarks[0]["x"] + landmarks[9]["x"]) / 2
        cy = (landmarks[0]["y"] + landmarks[9]["y"]) / 2
        self._range_min["x"] = min(self._range_min["x"], cx)
        self._range_min["y"] = min(self._range_min["y"], cy)
        self._range_max["x"] = max(self._range_max["x"], cx)
        self._range_max["y"] = max(self._range_max["y"], cy)

    def _process_samples(self, gesture_name):
        if not self.sample_buffer:
            return

        palm_sizes = []

        for sample in self.sample_buffer:
            palm_size = self._calculate_palm_size(sample)
            palm_sizes.append(palm_size)
            self._palm_samples.append(palm_size)

            lengths = self._calculate_finger_lengths(sample)
            for finger, length in lengths.items():
                self._finger_samples[finger].append(length)

        self.calibration_data["gesture_thresholds"][gesture_name] = {
            "palm_size_mean": float(np.mean(palm_sizes)),
            "palm_size_std": float(np.std(palm_sizes)),
        }

    def _calculate_palm_size(self, landmarks):
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        return float(np.sqrt((wrist["x"] - middle_mcp["x"]) ** 2 + (wrist["y"] - middle_mcp["y"]) ** 2))

    def _calculate_finger_lengths(self, landmarks):
        finger_joints = {
            "thumb": (2, 3, 4),
            "index": (5, 6, 8),
            "middle": (9, 10, 12),
            "ring": (13, 14, 16),
            "pinky": (17, 18, 20),
        }

        lengths = {}
        for finger, (mcp, pip, tip) in finger_joints.items():
            mcp_pos = landmarks[mcp]
            pip_pos = landmarks[pip]
            tip_pos = landmarks[tip]

            length = (
                float(np.sqrt((mcp_pos["x"] - pip_pos["x"]) ** 2 + (mcp_pos["y"] - pip_pos["y"]) ** 2)) +
                float(np.sqrt((pip_pos["x"] - tip_pos["x"]) ** 2 + (pip_pos["y"] - tip_pos["y"]) ** 2))
            )
            lengths[finger] = length

        return lengths

    def _finalize_calibration(self):
        if self._palm_samples:
            self.calibration_data["palm_size"] = float(np.mean(self._palm_samples))

        finger_lengths = {}
        for finger, lengths in self._finger_samples.items():
            if lengths:
                finger_lengths[finger] = {
                    "mean": float(np.mean(lengths)),
                    "std": float(np.std(lengths)),
                }
        if finger_lengths:
            self.calibration_data["finger_lengths"] = finger_lengths

        span_x = self._range_max["x"] - self._range_min["x"]
        span_y = self._range_max["y"] - self._range_min["y"]
        if span_x > 0.05 and span_y > 0.05:
            self.calibration_data["hand_position_range"] = {
                "x": [float(self._range_min["x"]), float(self._range_max["x"])],
                "y": [float(self._range_min["y"]), float(self._range_max["y"])],
            }

        self.calibration_complete = True
        self.is_calibrating = False
        self.save_calibration()

    def save_calibration(self):
        try:
            with open(self.calibration_file, "w") as f:
                json.dump(self.calibration_data, f, indent=2)
            return True
        except Exception:
            return False

    def load_calibration(self):
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, "r") as f:
                    self.calibration_data = json.load(f)
                self.calibration_complete = True
                return True
            except Exception:
                return False
        return False

    def get_progress(self):
        total_steps = 5
        return self.calibration_step / total_steps

    def get_current_step_instruction(self):
        instructions = [
            "Show OPEN PALM (flat hand, all fingers extended)",
            "Show FIST (close all fingers tightly)",
            "Show PINCH (touch thumb and index finger)",
            "Show POINTING (only index finger extended)",
            "Move your hand around the screen area",
        ]
        if self.calibration_step < len(instructions):
            return instructions[self.calibration_step]
        return "Calibration complete!"
