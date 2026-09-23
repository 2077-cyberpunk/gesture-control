import cv2
import time
from collections import deque


class VisualFeedback:
    def __init__(self):
        self.notifications = deque(maxlen=5)
        self.gesture_indicators = {}
        self.action_feedback = None
        self.action_feedback_time = 0
        self.calibration_points = []
        self.is_calibrating = False
        self.confidence_meter = 0

        self.mode = "normal"
        self.macro_recording = False
        self.macro_playing = False
        self.macro_name = None
        self.gesture_combo = []
        self.show_guide = True

    def add_notification(self, message, color=(0, 255, 0), duration=2.0):
        self.notifications.append({
            "message": message,
            "color": color,
            "time": time.time(),
            "duration": duration,
        })

    def show_action_feedback(self, action, confidence=1.0):
        self.action_feedback = {
            "action": action,
            "confidence": confidence,
            "time": time.time(),
        }

    def set_mode(self, mode):
        self.mode = mode

    def set_macro_status(self, recording=False, playing=False, name=None):
        self.macro_recording = recording
        self.macro_playing = playing
        self.macro_name = name

    def set_gesture_combo(self, combo):
        self.gesture_combo = combo

    def draw_hud(self, frame, gesture, hand_center, gesture_state, confidence):
        h, w = frame.shape[:2]

        self._draw_main_panel(frame, gesture, gesture_state, confidence)
        self._draw_mode_indicator(frame)
        self._draw_macro_status(frame)

        if hand_center:
            self._draw_hand_tracking(frame, hand_center, gesture)

        self._draw_notifications(frame)
        self._draw_action_feedback(frame)
        if self.show_guide:
            self._draw_gesture_guide(frame)

        if self.gesture_combo:
            self._draw_combo_indicator(frame)

    def _draw_main_panel(self, frame, gesture, gesture_state, confidence):
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (10, 10), (320, 170), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (320, 170), (0, 255, 0), 2)

        cv2.putText(
            frame, "GESTURE CONTROLLER", (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )

        state_colors = {
            "idle": (150, 150, 150),
            "detected": (0, 165, 255),
            "confirmed": (0, 255, 0),
            "releasing": (0, 0, 255),
        }
        state_color = state_colors.get(gesture_state, (150, 150, 150))

        cv2.putText(
            frame, f"Gesture: {gesture}", (20, 65),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )

        cv2.putText(
            frame, f"State: {gesture_state.upper()}", (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, state_color, 1
        )

        bar_width = int(confidence * 200)
        cv2.rectangle(frame, (20, 100), (220, 115), (50, 50, 50), -1)
        cv2.rectangle(frame, (20, 100), (20 + bar_width, 115), state_color, -1)
        cv2.putText(
            frame, f"Confidence: {confidence:.0%}", (20, 140),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1
        )

        cv2.putText(
            frame, f"Mode: {self.mode.upper()}", (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 200), 1
        )

    def _draw_mode_indicator(self, frame):
        h, w = frame.shape[:2]

        mode_colors = {
            "normal": (0, 255, 0),
            "presentation": (255, 165, 0),
            "gaming": (255, 0, 255),
        }
        color = mode_colors.get(self.mode, (0, 255, 0))

        cv2.rectangle(frame, (w - 200, 70), (w - 10, 100), (0, 0, 0), -1)
        cv2.rectangle(frame, (w - 200, 70), (w - 10, 100), color, 2)
        cv2.putText(
            frame, f"MODE: {self.mode.upper()}", (w - 190, 92),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
        )

    def _draw_macro_status(self, frame):
        if not self.macro_recording and not self.macro_playing:
            return

        h, w = frame.shape[:2]

        if self.macro_recording:
            color = (0, 0, 255)
            text = f"REC: {self.macro_name or 'Recording...'}"
            cv2.circle(frame, (w - 30, 115), 8, color, -1)
        elif self.macro_playing:
            color = (0, 255, 255)
            text = f"PLAY: {self.macro_name or 'Playing...'}"
            cv2.circle(frame, (w - 30, 115), 8, color, -1)

        cv2.rectangle(frame, (w - 200, 105), (w - 10, 135), (0, 0, 0), -1)
        cv2.rectangle(frame, (w - 200, 105), (w - 10, 135), color, 1)
        cv2.putText(
            frame, text, (w - 190, 127),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1
        )

    def _draw_hand_tracking(self, frame, hand_center, gesture):
        h, w = frame.shape[:2]

        x, y = hand_center
        cv2.circle(frame, (x, y), 20, (0, 255, 0), 2)
        cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

        cv2.line(frame, (x - 30, y), (x + 30, y), (0, 255, 255), 1)
        cv2.line(frame, (x, y - 30), (x, y + 30), (0, 255, 255), 1)

        cv2.putText(
            frame, f"Pos: {x}, {y}", (x + 25, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1
        )

    def _draw_notifications(self, frame):
        h, w = frame.shape[:2]
        current_time = time.time()

        y_offset = 200
        for notification in list(self.notifications):
            if current_time - notification["time"] < notification["duration"]:
                color = notification["color"]

                cv2.rectangle(frame, (10, y_offset), (350, y_offset + 30), (0, 0, 0), -1)
                cv2.rectangle(frame, (10, y_offset), (350, y_offset + 30), color, 1)
                cv2.putText(
                    frame, notification["message"], (20, y_offset + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
                )
                y_offset += 40
            else:
                self.notifications.remove(notification)

    def _draw_action_feedback(self, frame):
        if self.action_feedback:
            current_time = time.time()
            if current_time - self.action_feedback["time"] < 1.0:
                h, w = frame.shape[:2]
                action = self.action_feedback.get("action") or "unknown"
                confidence = self.action_feedback.get("confidence", 0)

                cv2.rectangle(frame, (w - 300, 140), (w - 10, 190), (0, 0, 0), -1)
                cv2.rectangle(frame, (w - 300, 140), (w - 10, 190), (0, 200, 0), 2)
                cv2.putText(
                    frame, f"ACTION: {str(action).upper()}", (w - 290, 165),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
                )
                cv2.putText(
                    frame, f"Confidence: {confidence:.0%}", (w - 290, 182),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1
                )

    def _draw_gesture_guide(self, frame):
        h, w = frame.shape[:2]

        guide_x = w - 220
        guide_y = h - 350

        cv2.rectangle(frame, (guide_x, guide_y), (w - 10, h - 10), (0, 0, 0), -1)
        cv2.rectangle(frame, (guide_x, guide_y), (w - 10, h - 10), (100, 100, 100), 1)

        cv2.putText(
            frame, "GESTURES", (guide_x + 10, guide_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1
        )

        gestures = [
            ("Open Palm", "Move Mouse"),
            ("Fist", "Left Click"),
            ("Pinch", "Right Click"),
            ("Point Up", "Scroll Up"),
            ("Point Down", "Scroll Down"),
            ("Peace", "Volume Up"),
            ("Thumbs Up", "Play/Pause"),
            ("Thumbs Down", "Volume Down"),
            ("Swipe Left", "Next Track"),
            ("Swipe Right", "Prev Track"),
            ("Two Fingers", "Copy"),
            ("Three Fingers", "Paste"),
            ("Four Fingers", "Undo"),
            ("Rock", "Screenshot"),
            ("Shaka", "New Tab"),
            ("Double Fist", "Drag Start"),
            ("Open Palm+Fist", "Drag End"),
        ]

        y = guide_y + 40
        for gesture, action in gestures:
            cv2.putText(
                frame, f"{gesture}: {action}", (guide_x + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (180, 180, 180), 1
            )
            y += 15

    def _draw_combo_indicator(self, frame):
        h, w = frame.shape[:2]

        combo_text = " -> ".join(self.gesture_combo[-3:])
        cv2.rectangle(frame, (10, h - 50), (400, h - 20), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, h - 50), (400, h - 20), (255, 255, 0), 1)
        cv2.putText(
            frame, f"COMBO: {combo_text}", (20, h - 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1
        )

    def draw_calibration_ui(self, frame, calibration_step, calibration_progress):
        h, w = frame.shape[:2]

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (50, 50, 50), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        cv2.putText(
            frame, "CALIBRATION MODE", (w // 2 - 150, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2
        )

        instructions = [
            "1. Show OPEN PALM to camera",
            "2. Show FIST to camera",
            "3. Show PINCH to camera",
            "4. Show POINTING to camera",
            "5. Move hand around screen",
        ]

        y = 120
        for i, instruction in enumerate(instructions):
            color = (0, 255, 0) if i < calibration_step else (150, 150, 150)
            cv2.putText(
                frame, instruction, (w // 2 - 200, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1
            )
            y += 40

        bar_width = int(calibration_progress * 400)
        cv2.rectangle(frame, (w // 2 - 200, h - 100), (w // 2 + 200, h - 70), (50, 50, 50), -1)
        cv2.rectangle(frame, (w // 2 - 200, h - 100), (w // 2 - 200 + bar_width, h - 70), (0, 255, 0), -1)

    def draw_action_log(self, frame, action_history):
        h, w = frame.shape[:2]

        log_x = 10
        log_y = h - 350
        log_w = 300
        log_h = 330

        cv2.rectangle(frame, (log_x, log_y), (log_x + log_w, log_y + log_h), (0, 0, 0), -1)
        cv2.rectangle(frame, (log_x, log_y), (log_x + log_w, log_y + log_h), (100, 100, 100), 1)

        cv2.putText(
            frame, "ACTION LOG", (log_x + 10, log_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1
        )

        y = log_y + 45
        for entry in reversed(action_history[-18:]):
            action = entry["action"]
            confidence = entry["confidence"]
            timestamp = time.strftime("%H:%M:%S", time.localtime(entry["time"]))

            cv2.putText(
                frame, f"{timestamp} {action} ({confidence:.0%})", (log_x + 10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1
            )
            y += 17

    def draw_performance_panel(self, frame, fps, hand_count, latency):
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (10, 10), (200, 100), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (200, 100), (50, 50, 50), 1)

        cv2.putText(
            frame, "PERFORMANCE", (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 0), 1
        )
        cv2.putText(
            frame, f"FPS: {fps}", (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1
        )
        cv2.putText(
            frame, f"Hands: {hand_count}", (20, 68),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1
        )
        cv2.putText(
            frame, f"Latency: {latency:.1f}ms", (20, 86),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1
        )
