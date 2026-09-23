import cv2
import mediapipe as mp
import numpy as np
from collections import deque
from enum import Enum
import time


class GestureState(Enum):
    IDLE = "idle"
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    RELEASING = "releasing"


class GestureDetector:
    def __init__(self, smoothing=2):
        self.base_options = mp.tasks.BaseOptions(
            model_asset_path="hand_landmarker.task"
        )
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=self.base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.hand_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.gesture_history = deque(maxlen=smoothing)
        self.prev_hand_positions = {}
        self.swipe_threshold = 0.08
        self.frame_count = 0

        self.hand_states = {}
        self.confirmed_gesture = None
        self.confirmation_threshold = 0.12
        self.release_threshold = 0.3

        self.hand_angles = {}
        self.finger_curvatures = {}

        self.calibrated = False
        self.calibration_data = {"palm_size": 0.15, "finger_length": 0.1}
        self.ref_palm_size = 0.15
        self.finger_length_ref = {}

        self.two_hand_gesture = None
        self.two_hand_gesture_state = GestureState.IDLE
        self.two_hand_start_time = 0

        self.gesture_combo = []
        self.combo_timeout = 2.0
        self.combo_last_time = 0

        self.mode = "normal"

    def set_mode(self, mode):
        self.mode = mode

    def set_calibration(self, data):
        if not data:
            self.calibrated = False
            self.ref_palm_size = 0.15
            self.finger_length_ref = {}
            return
        self.calibration_data = data
        self.calibrated = True
        try:
            self.ref_palm_size = float(data.get("palm_size", 0.15)) or 0.15
        except (TypeError, ValueError):
            self.ref_palm_size = 0.15
        self.finger_length_ref = data.get("finger_lengths") or {}

    def _palm_scale(self, landmarks):
        palm = self._calculate_palm_size(landmarks)
        if not self.calibrated or self.ref_palm_size <= 0:
            return max(0.5, min(2.5, palm / 0.15))
        return max(0.5, min(2.5, palm / self.ref_palm_size))

    def _get_hand_state(self, hand_id):
        if hand_id not in self.hand_states:
            self.hand_states[hand_id] = {
                "state": GestureState.IDLE,
                "confirmed_gesture": None,
                "gesture_start_time": 0,
                "last_release_time": 0,
            }
        return self.hand_states[hand_id]

    def detect_gesture(self, hand_landmarks, frame_width, frame_height, hand_id=0):
        landmarks = []
        for lm in hand_landmarks:
            landmarks.append({"x": lm.x, "y": lm.y, "z": lm.z})

        gesture, confidence = self._classify_gesture_precise(landmarks, hand_id)

        if gesture in ("swipe_left", "swipe_right"):
            hand_state = self._get_hand_state(hand_id)
            if hand_state["state"] == GestureState.DETECTED:
                hand_state["state"] = GestureState.IDLE
                hand_state["confirmed_gesture"] = None
            return gesture, confidence

        now = time.time()
        hand_state = self._get_hand_state(hand_id)
        state = hand_state["state"]
        confirmed = hand_state["confirmed_gesture"]

        if gesture != "unknown":
            if state == GestureState.IDLE:
                if now - hand_state["last_release_time"] > 0.2:
                    hand_state["state"] = GestureState.DETECTED
                    hand_state["confirmed_gesture"] = gesture
                    hand_state["gesture_start_time"] = now
            elif state == GestureState.DETECTED:
                if gesture == confirmed:
                    if now - hand_state["gesture_start_time"] >= self.confirmation_threshold:
                        hand_state["state"] = GestureState.CONFIRMED
                else:
                    hand_state["state"] = GestureState.IDLE
                    hand_state["confirmed_gesture"] = None
            elif state == GestureState.CONFIRMED:
                if gesture != confirmed:
                    hand_state["state"] = GestureState.RELEASING
                    hand_state["gesture_start_time"] = now
        else:
            if state == GestureState.CONFIRMED:
                if now - hand_state["gesture_start_time"] >= self.release_threshold:
                    hand_state["state"] = GestureState.IDLE
                    hand_state["confirmed_gesture"] = None
                    hand_state["last_release_time"] = now

        state = hand_state["state"]
        confirmed = hand_state["confirmed_gesture"]
        self.confirmed_gesture = confirmed

        if state == GestureState.CONFIRMED:
            return confirmed, confidence
        elif state == GestureState.RELEASING:
            if now - hand_state["gesture_start_time"] >= 0.1:
                hand_state["state"] = GestureState.IDLE
                hand_state["confirmed_gesture"] = None
                hand_state["last_release_time"] = now
            return confirmed, confidence * 0.5

        return "none", 0.0

    def detect_two_hand_gesture(self, hand_data_list, frame_width, frame_height):
        if len(hand_data_list) < 2:
            self.two_hand_gesture = None
            self.two_hand_gesture_state = GestureState.IDLE
            return "none", 0.0

        hand1 = hand_data_list[0]
        hand2 = hand_data_list[1]

        gesture = self._classify_two_hand_gesture(hand1, hand2, frame_width, frame_height)
        confidence = 0.9 if gesture != "none" else 0.0

        now = time.time()

        if gesture != "none":
            if self.two_hand_gesture_state == GestureState.IDLE:
                self.two_hand_gesture_state = GestureState.DETECTED
                self.two_hand_gesture = gesture
                self.two_hand_start_time = now
            elif self.two_hand_gesture_state == GestureState.DETECTED:
                if gesture == self.two_hand_gesture:
                    if now - self.two_hand_start_time >= 0.2:
                        self.two_hand_gesture_state = GestureState.CONFIRMED
                else:
                    self.two_hand_gesture_state = GestureState.IDLE
                    self.two_hand_gesture = None
        else:
            if self.two_hand_gesture_state == GestureState.CONFIRMED:
                self.two_hand_gesture_state = GestureState.RELEASING
                self.two_hand_start_time = now
            elif self.two_hand_gesture_state == GestureState.RELEASING:
                if now - self.two_hand_start_time >= 0.2:
                    self.two_hand_gesture_state = GestureState.IDLE
                    self.two_hand_gesture = None

        if self.two_hand_gesture_state == GestureState.CONFIRMED:
            return self.two_hand_gesture, confidence

        return "none", 0.0

    def _classify_two_hand_gesture(self, hand1, hand2, frame_width, frame_height):
        center1 = hand1["center"]
        center2 = hand2["center"]

        dx = center2[0] - center1[0]
        dy = center2[1] - center1[1]
        distance = np.sqrt(dx**2 + dy**2)

        gesture1 = hand1["gesture"]
        gesture2 = hand2["gesture"]

        if distance < 100:
            if gesture1 == "fist" and gesture2 == "fist":
                return "two_fist_bump"
            elif gesture1 == "open_palm" and gesture2 == "open_palm":
                return "two_palm_press"
        elif distance > 300:
            if gesture1 == "open_palm" and gesture2 == "open_palm":
                return "two_hand_spread"
            elif gesture1 == "fist" and gesture2 == "fist":
                return "two_fist_apart"

        if gesture1 == "open_palm" and gesture2 == "fist":
            return "open_fist_combo"
        elif gesture1 == "fist" and gesture2 == "open_palm":
            return "fist_open_combo"

        if gesture1 == "peace" and gesture2 == "peace":
            return "double_peace"

        if gesture1 == "pointing" and gesture2 == "pointing":
            if abs(dy) < 50:
                if dx > 0:
                    return "point_right"
                else:
                    return "point_left"
            elif abs(dx) < 50:
                if dy > 0:
                    return "point_down"
                else:
                    return "point_up"

        return "none"

    def _classify_gesture_precise(self, landmarks, hand_id=0):
        finger_data = self._analyze_fingers(landmarks)
        hand_shape = self._analyze_hand_shape(landmarks, finger_data)

        swipe = self._detect_swipe(landmarks, hand_id)
        if swipe:
            return swipe, 0.9

        gesture = self._match_gesture(finger_data, hand_shape, landmarks)
        confidence = self._calculate_confidence(gesture, finger_data, landmarks)

        return gesture, confidence

    def _analyze_fingers(self, landmarks):
        finger_tips = [4, 8, 12, 16, 20]
        finger_pips = [2, 6, 10, 14, 18]
        finger_mcps = [1, 5, 9, 13, 17]
        finger_names = ["thumb", "index", "middle", "ring", "pinky"]

        fingers_up = []
        fingers_extended = []
        finger_angles = []

        for i, (tip, pip, mcp) in enumerate(zip(finger_tips, finger_pips, finger_mcps)):
            tip_pos = landmarks[tip]
            pip_pos = landmarks[pip]
            mcp_pos = landmarks[mcp]

            if i == 0:
                is_up = tip_pos["x"] < pip_pos["x"] and tip_pos["x"] < mcp_pos["x"]
            else:
                is_up = tip_pos["y"] < pip_pos["y"]

            is_extended = self._is_finger_extended(landmarks, tip, pip, mcp, finger_names[i])

            angle = self._calculate_finger_angle(tip_pos, pip_pos, mcp_pos)

            fingers_up.append(is_up)
            fingers_extended.append(is_extended)
            finger_angles.append(angle)

        return {
            "up": fingers_up,
            "extended": fingers_extended,
            "angles": finger_angles,
            "count_up": sum(fingers_up),
            "count_extended": sum(fingers_extended),
        }

    def _is_finger_extended(self, landmarks, tip, pip, mcp, finger_name=None):
        tip_pos = landmarks[tip]
        pip_pos = landmarks[pip]
        mcp_pos = landmarks[mcp]

        tip_to_mcp = self._distance_3d(tip_pos, mcp_pos)
        pip_to_mcp = self._distance_3d(pip_pos, mcp_pos)

        if self.calibrated and finger_name and finger_name in self.finger_length_ref:
            try:
                expected = float(self.finger_length_ref[finger_name]["mean"])
            except (KeyError, TypeError, ValueError):
                expected = 0.0
            if expected > 0:
                return tip_to_mcp > expected * 0.7

        return tip_to_mcp > pip_to_mcp * 1.1

    def _calculate_finger_angle(self, tip, pip, mcp):
        v1 = np.array([pip["x"] - mcp["x"], pip["y"] - mcp["y"]])
        v2 = np.array([tip["x"] - pip["x"], tip["y"] - pip["y"]])

        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
        return np.degrees(angle)

    def _analyze_hand_shape(self, landmarks, finger_data):
        palm_size = self._calculate_palm_size(landmarks)
        finger_spread = self._calculate_finger_spread(landmarks)
        hand_rotation = self._calculate_hand_rotation(landmarks)

        return {
            "palm_size": palm_size,
            "finger_spread": finger_spread,
            "rotation": hand_rotation,
        }

    def _calculate_palm_size(self, landmarks):
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        return self._distance_2d(wrist, middle_mcp)

    def _calculate_finger_spread(self, landmarks):
        fingers = [landmarks[8], landmarks[12], landmarks[16], landmarks[20]]
        distances = []
        for i in range(len(fingers) - 1):
            distances.append(self._distance_2d(fingers[i], fingers[i + 1]))
        return np.mean(distances) if distances else 0

    def _calculate_hand_rotation(self, landmarks):
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        dx = middle_mcp["x"] - wrist["x"]
        dy = middle_mcp["y"] - wrist["y"]
        return np.degrees(np.arctan2(dy, dx))

    def _match_gesture(self, finger_data, hand_shape, landmarks):
        up = finger_data["up"]
        extended = finger_data["extended"]

        scale = self._palm_scale(landmarks)
        thumb_index_dist = self._distance_2d(landmarks[4], landmarks[8])

        if thumb_index_dist < 0.06 * scale:
            return "pinch"

        if all(up) and all(extended):
            return "open_palm"

        if sum(up) == 0 and sum(extended) == 0:
            return "fist"

        point_offset = 0.15 * scale
        if not up[0] and up[1] and not up[2] and not up[3] and not up[4]:
            wrist_y = landmarks[0]["y"]
            index_y = landmarks[8]["y"]
            if index_y < wrist_y - point_offset:
                return "pointing_up"
            elif index_y > wrist_y + point_offset:
                return "pointing_down"
            return "pointing"

        if not up[0] and up[1] and up[2] and not up[3] and not up[4]:
            return "peace"

        if up[0] and not any(up[1:]):
            return "thumbs_up"

        if not up[0] and up[1] and up[2] and up[3] and not up[4]:
            return "thumbs_down"

        if up[0] and up[1] and not up[2] and not up[3] and not up[4]:
            return "two_fingers"

        if up[0] and up[1] and up[2] and not up[3] and not up[4]:
            return "three_fingers"

        if up[0] and up[1] and up[2] and up[3] and not up[4]:
            return "four_fingers"

        if up[1] and not up[2] and up[3] and not up[4]:
            return "rock"

        if not up[0] and up[1] and not up[2] and not up[3] and up[4]:
            return "shaka"

        return "unknown"

    def _calculate_confidence(self, gesture, finger_data, landmarks):
        if gesture == "unknown" or gesture == "none":
            return 0.0

        up = finger_data["up"]
        extended = finger_data["extended"]

        if gesture == "open_palm":
            if all(up) and all(extended):
                return 0.95
            return 0.6
        elif gesture == "fist":
            if sum(up) == 0:
                return 0.95
            return 0.6
        elif gesture == "pinch":
            thumb_index_dist = self._distance_2d(landmarks[4], landmarks[8])
            if thumb_index_dist < 0.04 * self._palm_scale(landmarks):
                return 0.95
            return 0.7
        elif gesture in ["pointing_up", "pointing_down", "pointing"]:
            if up[1] and not any(up[2:]):
                return 0.9
            return 0.6
        elif gesture == "peace":
            if up[1] and up[2] and not any(up[3:]):
                return 0.9
            return 0.6

        return 0.7

    def _detect_swipe(self, landmarks, hand_id=0):
        current_x = landmarks[0]["x"]

        if hand_id in self.prev_hand_positions:
            prev_x = self.prev_hand_positions[hand_id]
            delta_x = current_x - prev_x

            if abs(delta_x) > self.swipe_threshold:
                self.prev_hand_positions[hand_id] = current_x
                if delta_x > 0:
                    return "swipe_right"
                else:
                    return "swipe_left"

        self.prev_hand_positions[hand_id] = current_x
        return None

    def _distance_2d(self, p1, p2):
        return np.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2)

    def _distance_3d(self, p1, p2):
        return np.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2 + (p1.get("z", 0) - p2.get("z", 0)) ** 2)

    def process_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        self.frame_count += 1
        results = self.hand_landmarker.detect_for_video(mp_image, self.frame_count)

        hand_data = []
        if results.hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(results.hand_landmarks):
                gesture, confidence = self.detect_gesture(
                    hand_landmarks, frame.shape[1], frame.shape[0], hand_idx
                )
                center = self.get_hand_center(hand_landmarks, frame.shape[1], frame.shape[0])
                hand_data.append({
                    "landmarks": hand_landmarks,
                    "gesture": gesture,
                    "confidence": confidence,
                    "center": center,
                    "state": self._get_hand_state(hand_idx)["state"].value,
                })

        if len(hand_data) >= 2:
            two_hand_gesture, two_hand_confidence = self.detect_two_hand_gesture(
                hand_data, frame.shape[1], frame.shape[0]
            )
            if two_hand_gesture != "none":
                for hd in hand_data:
                    hd["two_hand_gesture"] = two_hand_gesture
                    hd["two_hand_confidence"] = two_hand_confidence
                    hd["gesture"] = two_hand_gesture
                    hd["confidence"] = two_hand_confidence

        return hand_data

    def get_hand_center(self, hand_landmarks, frame_width, frame_height):
        wrist = hand_landmarks[0]
        middle_finger = hand_landmarks[9]
        center_x = int((wrist.x + middle_finger.x) / 2 * frame_width)
        center_y = int((wrist.y + middle_finger.y) / 2 * frame_height)
        return center_x, center_y

    def draw_landmarks(self, frame, hand_landmarks):
        h, w, _ = frame.shape
        connections = [
            (0,1),(1,2),(2,3),(3,4),
            (0,5),(5,6),(6,7),(7,8),
            (0,9),(9,10),(10,11),(11,12),
            (0,13),(13,14),(14,15),(15,16),
            (0,17),(17,18),(18,19),(19,20),
            (5,9),(9,13),(13,17)
        ]
        for connection in connections:
            start_idx = connection[0]
            end_idx = connection[1]
            start = hand_landmarks[start_idx]
            end = hand_landmarks[end_idx]
            pt1 = (int(start.x * w), int(start.y * h))
            pt2 = (int(end.x * w), int(end.y * h))
            cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

        for lm in hand_landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

    def get_gesture_state(self):
        if 0 in self.hand_states:
            return self.hand_states[0]["state"].value
        return GestureState.IDLE.value

    def get_confirmed_gesture(self):
        return self.confirmed_gesture

    def add_combo(self, gesture):
        if gesture is None or gesture == "none":
            return None

        now = time.time()
        if now - self.combo_last_time > self.combo_timeout:
            self.gesture_combo = []

        self.gesture_combo.append(gesture)
        self.combo_last_time = now

        if len(self.gesture_combo) > 5:
            self.gesture_combo.pop(0)

        return self._check_combo()

    def _check_combo(self):
        valid_gestures = [g for g in self.gesture_combo if g is not None and g != "none"]
        if not valid_gestures:
            return None

        combo_str = ",".join(valid_gestures)

        combos = {
            "fist,open_palm": "combo_grab_release",
            "open_palm,fist": "combo_push",
            "peace,fist": "combo_select",
            "fist,peace": "combo_deselect",
            "thumbs_up,thumbs_down": "combo_approve_reject",
            "pointing,open_palm": "combo_point_grab",
            "swipe_left,swipe_right": "combo_shuffle",
            "pinch,pinch": "combo_zoom",
        }

        for combo_pattern, combo_action in combos.items():
            if combo_pattern in combo_str:
                self.gesture_combo = []
                return combo_action

        return None

    def get_combo_history(self):
        return self.gesture_combo
