import cv2
import json
import sys
import time
import urllib.request
import os
import logging
from gestures import GestureDetector
from actions import GestureActions
from feedback import VisualFeedback
from calibration import CalibrationSystem
from macros import MacroRecorder
from monitor import MultiMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("gesture_controller.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def download_model():
    model_path = "hand_landmarker.task"
    if not os.path.exists(model_path):
        logger.info("Downloading hand landmark model...")
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        try:
            urllib.request.urlretrieve(url, model_path)
            logger.info("Model downloaded!")
        except Exception as e:
            logger.error("Failed to download hand landmark model: %s", e)
            raise
    return model_path


class GestureController:
    def __init__(self, config_path="config.json"):
        self.should_quit = False

        with open(config_path) as f:
            self.config = json.load(f)

        download_model()

        self.detector = GestureDetector(
            smoothing=self.config.get("gesture_smoothing", 2)
        )
        self.actions = GestureActions()
        self.feedback = VisualFeedback()
        self.calibration = CalibrationSystem()
        self.macros = MacroRecorder()
        self.monitors = MultiMonitor()

        self.gesture_cooldown = {}
        self.cooldown_time = 0.3
        self.continuous_actions = {
            "mouse_move", "scroll_up", "scroll_down", "drag_move", "presentation_pointer",
            "gaming_w", "gaming_a", "gaming_s", "gaming_d",
            "gaming_space", "gaming_shift", "gaming_e", "gaming_r", "gaming_f",
            "gaming_1", "gaming_2", "gaming_3", "gaming_4",
        }

        self.show_hud = True
        self.show_log = True
        self.show_guide = True
        self.show_performance = True
        self.is_calibrating = False
        self._last_combo_gesture = "none"
        self.feedback.show_guide = True

        self.fps_counter = 0
        self.fps_time = time.time()
        self.current_fps = 0
        self.latency = 0

        self.tray = None
        try:
            from tray import TrayIcon
            self.tray = TrayIcon(self)
        except Exception:
            logger.warning("Tray icon not available")

        self.camera_retry_count = 0
        self.max_camera_retries = 5
        self.last_frame_time = time.time()

        self.calibration.load_calibration()
        self._apply_calibration()

    def _apply_calibration(self):
        if not self.calibration.calibration_complete:
            return
        data = self.calibration.calibration_data
        self.detector.set_calibration(data)
        self.actions.set_hand_range(data.get("hand_position_range"))

    def run(self):
        cap = self._init_camera()

        if self.tray:
            self.tray.start()

        logger.info("Gesture Controller Started!")
        print("Gesture Controller Started!")
        print("Press 'q' to quit")
        print("Press 'h' to toggle HUD")
        print("Press 'l' to toggle action log")
        print("Press 'g' to toggle gesture guide")
        print("Press 'p' to toggle performance panel")
        print("Press 'c' to start calibration")
        print("Press 'r' to reset calibration")
        print("Press 'm' to cycle mode (Normal/Presentation/Gaming)")
        print("Press '1' to start macro recording")
        print("Press '2' to stop macro recording")
        print("Press '3' to play last macro")
        print()

        while not self.should_quit:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame capture failed, attempting camera recovery...")
                cap = self._recover_camera(cap)
                if cap is None:
                    logger.error("Camera recovery failed")
                    break
                continue

            self._update_fps()
            frame_start = time.time()

            frame = cv2.flip(frame, 1)

            hand_data_list = self.detector.process_frame(frame)

            current_gesture = "none"
            hand_center = None
            confidence = 0.0
            gesture_state = "idle"

            for hand_data in hand_data_list:
                if self.show_hud:
                    self.detector.draw_landmarks(frame, hand_data["landmarks"])

                current_gesture = hand_data["gesture"]
                hand_center = hand_data["center"]
                confidence = hand_data["confidence"]
                gesture_state = hand_data["state"]

                if self.is_calibrating:
                    done = self.calibration.process_calibration(
                        hand_data["landmarks"], current_gesture
                    )
                    if done:
                        self.is_calibrating = False
                        self._apply_calibration()
                        self.feedback.add_notification("Calibration complete!", (0, 255, 0))
                        logger.info("Calibration complete and applied")
                else:
                    if current_gesture != "none" and current_gesture != "unknown":
                        frame_h, frame_w = frame.shape[:2]
                        self._execute_action(
                            current_gesture, hand_center, frame_w, frame_h, confidence
                        )

                        if self.macros.is_recording:
                            self.macros.record_action(
                                current_gesture,
                                self._resolve_action(current_gesture, hand_center, frame_w, frame_h),
                                hand_center,
                            )

            self.actions.tick()

            if not self.is_calibrating and current_gesture != self._last_combo_gesture:
                if current_gesture not in ("none", "unknown"):
                    combo = self.detector.add_combo(current_gesture)
                    if combo:
                        self._execute_action(
                            combo, hand_center,
                            frame.shape[1], frame.shape[0], 0.9
                        )
                        self.feedback.add_notification(f"Combo: {combo}", (255, 255, 0))
                self._last_combo_gesture = current_gesture

            if self.show_hud:
                self.feedback.draw_hud(
                    frame, current_gesture, hand_center, gesture_state, confidence
                )

            if self.show_log:
                self.feedback.draw_action_log(frame, self.actions.get_action_history())

            if self.show_performance:
                self.feedback.draw_performance_panel(
                    frame, self.current_fps, len(hand_data_list), self.latency * 1000
                )

            if self.is_calibrating:
                self.feedback.draw_calibration_ui(
                    frame,
                    self.calibration.calibration_step,
                    self.calibration.get_progress(),
                )

            cv2.imshow("Gesture Controller", frame)

            self.latency = time.time() - frame_start

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("h"):
                self.show_hud = not self.show_hud
            elif key == ord("l"):
                self.show_log = not self.show_log
            elif key == ord("g"):
                self.show_guide = not self.show_guide
                self.feedback.show_guide = self.show_guide
            elif key == ord("p"):
                self.show_performance = not self.show_performance
            elif key == ord("c"):
                self._start_calibration()
            elif key == ord("r"):
                self._reset_calibration()
            elif key == ord("m"):
                self._cycle_mode()
            elif key == ord("1"):
                self._start_macro_recording()
            elif key == ord("2"):
                self._stop_macro_recording()
            elif key == ord("3"):
                self._play_last_macro()
            elif key == ord("s"):
                self._save_config()

        if self.tray:
            self.tray.stop()

        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        logger.info("Gesture Controller stopped")

    def _init_camera(self):
        cap = cv2.VideoCapture(self.config.get("camera_id", 0))

        if not cap.isOpened():
            logger.error("Cannot open camera")
            sys.exit(1)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 60)

        return cap

    def _recover_camera(self, old_cap):
        if old_cap:
            old_cap.release()

        self.camera_retry_count += 1
        if self.camera_retry_count > self.max_camera_retries:
            logger.error("Max camera retries exceeded")
            return None

        logger.info(f"Attempting camera recovery ({self.camera_retry_count}/{self.max_camera_retries})...")
        time.sleep(1)

        try:
            cap = cv2.VideoCapture(self.config.get("camera_id", 0))
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 60)
                self.camera_retry_count = 0
                logger.info("Camera recovered successfully")
                return cap
        except Exception as e:
            logger.error(f"Camera recovery failed: {e}")

        return None

    def _gaming_quadrant_action(self, hand_center, frame_w, frame_h):
        x, y = hand_center
        cx = frame_w / 2.0
        cy = frame_h / 2.0
        nx = (x - cx) / frame_w
        ny = (y - cy) / frame_h
        dead = 0.12
        if abs(nx) < dead and abs(ny) < dead:
            return None
        scores = {
            "gaming_w": -ny,
            "gaming_s": ny,
            "gaming_a": -nx,
            "gaming_d": nx,
        }
        best = max(scores, key=scores.get)
        if scores[best] <= 0.02:
            return None
        return best

    def _resolve_action(self, gesture, hand_center, frame_w, frame_h):
        mode = self.actions.mode
        mode_map = self.config.get("mode_actions", {}).get(mode, {})
        if gesture in mode_map:
            mapped = mode_map[gesture]
            if mapped == "gaming_move" and hand_center:
                return self._gaming_quadrant_action(hand_center, frame_w, frame_h)
            if mapped != "gaming_move":
                return mapped

        action_config = self.config.get("actions", {}).get(gesture)
        if not action_config:
            return gesture
        return action_config.get("action") or gesture

    def _execute_action(self, gesture, hand_center, frame_w, frame_h, confidence):
        if gesture == "none" or gesture == "unknown":
            return

        action_name = self._resolve_action(gesture, hand_center, frame_w, frame_h)
        if not action_name:
            return

        now = time.time()

        if action_name in self.continuous_actions:
            self.actions.execute(action_name, hand_center, frame_w, frame_h, confidence)
            if action_name:
                self.feedback.show_action_feedback(action_name, confidence)
            return

        if gesture in self.gesture_cooldown:
            if now - self.gesture_cooldown[gesture] < self.cooldown_time:
                return

        self.gesture_cooldown[gesture] = now
        self.actions.execute(action_name, hand_center, frame_w, frame_h, confidence)
        if action_name:
            self.feedback.show_action_feedback(action_name, confidence)

    def _start_calibration(self):
        self.is_calibrating = True
        self.calibration.start_calibration()
        self.feedback.add_notification("Calibration started!", (0, 255, 0))
        logger.info("Calibration started")

    def _reset_calibration(self):
        self.is_calibrating = False
        self.calibration.stop_calibration()
        if os.path.exists("calibration_data.json"):
            os.remove("calibration_data.json")
        self.detector.set_calibration(None)
        self.actions.set_hand_range(None)
        self.feedback.add_notification("Calibration reset!", (0, 0, 255))
        logger.info("Calibration reset")

    def _save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        self.feedback.add_notification("Config saved!", (0, 255, 0))
        logger.info("Config saved")

    def _cycle_mode(self):
        modes = ["normal", "presentation", "gaming"]
        current_idx = modes.index(self.actions.mode) if self.actions.mode in modes else 0
        new_mode = modes[(current_idx + 1) % len(modes)]
        self.set_mode(new_mode)

    def set_mode(self, new_mode):
        self.actions.set_mode(new_mode)
        self.detector.set_mode(new_mode)
        self.feedback.set_mode(new_mode)
        if self.tray:
            self.tray.update_status(new_mode)
        self.feedback.add_notification(f"Mode: {new_mode.upper()}", (0, 200, 255))
        logger.info("Mode changed to %s", new_mode)

    def _start_macro_recording(self):
        name = f"macro_{int(time.time())}"
        if self.macros.start_recording(name):
            self.feedback.set_macro_status(recording=True, name=name)
            self.feedback.add_notification(f"Recording: {name}", (0, 0, 255))
            logger.info(f"Macro recording started: {name}")

    def _stop_macro_recording(self):
        name = self.macros.stop_recording()
        if name:
            self.feedback.set_macro_status(recording=False)
            self.feedback.add_notification(f"Saved: {name}", (0, 255, 0))
            logger.info(f"Macro recording stopped: {name}")

    def _play_last_macro(self):
        macros = self.macros.list_macros()
        if macros:
            last_macro = macros[0]["name"]
            if self.macros.play_macro(last_macro, self._macro_action_callback):
                self.feedback.set_macro_status(playing=True, name=last_macro)
                self.feedback.add_notification(f"Playing: {last_macro}", (255, 255, 0))
                logger.info(f"Macro playback started: {last_macro}")

    def _stop_macro_playback(self):
        self.macros.stop_playback()
        self.feedback.set_macro_status(playing=False)
        logger.info("Macro playback stopped")

    def _macro_action_callback(self, gesture, action, hand_center):
        if action:
            self.actions.execute(action, hand_center, 640, 480, 1.0)

    def _update_fps(self):
        self.fps_counter += 1
        current_time = time.time()
        if current_time - self.fps_time >= 1.0:
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.fps_time = current_time


def list_actions():
    with open("config.json") as f:
        config = json.load(f)

    print("\nAvailable Gestures and Actions:")
    print("=" * 60)
    for gesture, action_config in config.get("actions", {}).items():
        print(f"  {gesture:20s} -> {action_config['action']:25s} ({action_config['description']})")
    print()


def list_controls():
    print("\nKeyboard Controls:")
    print("=" * 40)
    print("  q - Quit")
    print("  h - Toggle HUD")
    print("  l - Toggle action log")
    print("  g - Toggle gesture guide")
    print("  p - Toggle performance panel")
    print("  c - Start calibration")
    print("  r - Reset calibration")
    print("  m - Cycle mode (Normal/Presentation/Gaming)")
    print("  1 - Start macro recording")
    print("  2 - Stop macro recording")
    print("  3 - Play last macro")
    print("  s - Save config")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_actions()
        elif sys.argv[1] == "--controls":
            list_controls()
        elif sys.argv[1] == "--help":
            print("\nGesture Controller - Tony Stark Style")
            print("=" * 50)
            print("\nUsage: python gesture_controller.py [option]")
            print("\nOptions:")
            print("  (no args)    - Run the gesture controller")
            print("  --list       - List all gestures and actions")
            print("  --controls   - List keyboard controls")
            print("  --help       - Show this help message")
            print()
            list_controls()
    else:
        controller = GestureController()
        controller.run()
