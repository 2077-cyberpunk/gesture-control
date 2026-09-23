import argparse
import math
import cv2
import json
import sys
import time
import urllib.request
import os
import logging
import numpy as np
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


def load_config(config_path):
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"Config not found: {config_path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {config_path}: {e}")
    validate_config(config, config_path)
    return config


def validate_config(config, config_path="config.json"):
    if not isinstance(config, dict):
        raise SystemExit(f"{config_path}: root must be a JSON object")

    actions = config.get("actions")
    if not isinstance(actions, dict) or not actions:
        raise SystemExit(f"{config_path}: 'actions' must be a non-empty object")

    for gesture, cfg in actions.items():
        if not isinstance(cfg, dict):
            raise SystemExit(f"{config_path}: actions.{gesture} must be an object")
        if not cfg.get("action"):
            raise SystemExit(f"{config_path}: actions.{gesture} needs an 'action' field")
        if not cfg.get("description"):
            raise SystemExit(f"{config_path}: actions.{gesture} needs a 'description' field")

    mode_actions = config.get("mode_actions", {})
    if not isinstance(mode_actions, dict):
        raise SystemExit(f"{config_path}: 'mode_actions' must be an object")
    for mode, mapping in mode_actions.items():
        if not isinstance(mapping, dict):
            raise SystemExit(f"{config_path}: mode_actions.{mode} must be an object")
        for gesture, action in mapping.items():
            if not isinstance(action, str) or not action:
                raise SystemExit(
                    f"{config_path}: mode_actions.{mode}.{gesture} must be a non-empty string"
                )

    disabled = config.get("disabled_gestures", [])
    if not isinstance(disabled, list) or not all(isinstance(g, str) for g in disabled):
        raise SystemExit(f"{config_path}: 'disabled_gestures' must be a list of strings")

    camera_id = config.get("camera_id", 0)
    if not isinstance(camera_id, int) or camera_id < 0:
        raise SystemExit(f"{config_path}: 'camera_id' must be a non-negative integer")

    smoothing = config.get("gesture_smoothing", 2)
    if not isinstance(smoothing, int) or smoothing < 1:
        raise SystemExit(f"{config_path}: 'gesture_smoothing' must be a positive integer")


class GestureController:
    def __init__(self, config_path="config.json", camera_id=None, mode=None, demo=False):
        self.should_quit = False
        self.demo_mode = demo

        self.config = load_config(config_path)
        if camera_id is not None:
            self.config["camera_id"] = camera_id
        if mode is not None:
            self.config.setdefault("_cli_mode", mode)

        if not self.demo_mode:
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
        self.disabled_gestures = set(self.config.get("disabled_gestures", []))
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
        self._demo_frame_count = 0

        self.calibration.load_calibration()
        self._apply_calibration()

        cli_mode = self.config.pop("_cli_mode", None)
        if cli_mode:
            self.set_mode(cli_mode)

    def _apply_calibration(self):
        if not self.calibration.calibration_complete:
            return
        data = self.calibration.calibration_data
        self.detector.set_calibration(data)
        self.actions.set_hand_range(data.get("hand_position_range"))

    def run(self):
        cap = None if self.demo_mode else self._init_camera()

        if self.tray:
            self.tray.start()

        logger.info("Gesture Controller Started!%s", " (demo mode)" if self.demo_mode else "")
        print("Gesture Controller Started!" + (" [DEMO MODE]" if self.demo_mode else ""))
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
            if self.demo_mode:
                frame = self._next_demo_frame()
            else:
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

            if not self.demo_mode:
                frame = cv2.flip(frame, 1)

            hand_data_list = [] if self.demo_mode else self.detector.process_frame(frame)

            self._drain_ui_events()

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

    def _next_demo_frame(self):
        self._demo_frame_count += 1
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (40, 30, 20)
        for y in range(0, 480, 40):
            cv2.line(frame, (0, y), (640, y), (55, 45, 35), 1)
        for x in range(0, 640, 40):
            cv2.line(frame, (x, 0), (x, 480), (55, 45, 35), 1)
        t = self._demo_frame_count
        cx = int(320 + 180 * math.sin(t / 30.0))
        cy = int(240 + 100 * math.cos(t / 45.0))
        cv2.circle(frame, (cx, cy), 28, (0, 200, 255), 2)
        cv2.circle(frame, (cx, cy), 6, (0, 200, 255), -1)
        cv2.putText(
            frame, "DEMO MODE - no camera", (160, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2
        )
        cv2.putText(
            frame, "HUD preview only", (190, 70),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1
        )
        return frame

    def _drain_ui_events(self):
        for ev in self.actions.drain_ui_events():
            if ev.get("type") == "failsafe":
                self.feedback.add_notification(
                    f"Fail-safe: {ev.get('action', '?')} retried", (255, 165, 0)
                )

    def _init_camera(self):
        cap = cv2.VideoCapture(self.config.get("camera_id", 0))

        if not cap.isOpened():
            logger.error("Cannot open camera %s", self.config.get("camera_id", 0))
            print(f"Error: cannot open camera {self.config.get('camera_id', 0)}.")
            print("Try --camera N, check permissions, or run with --demo.")
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
        if gesture in self.disabled_gestures:
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
    config = load_config("config.json")

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


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gesture_controller.py",
        description="Gesture Controller - Tony Stark Style",
    )
    parser.add_argument("--list", action="store_true", help="list all gestures and actions")
    parser.add_argument("--controls", action="store_true", help="list keyboard controls")
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        metavar="N",
        help="camera device id (overrides config.json)",
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "presentation", "gaming"],
        default=None,
        help="start mode (default: normal)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="run without a camera (HUD preview only)",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        metavar="PATH",
        help="path to config file (default: config.json)",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.list:
        list_actions()
    elif args.controls:
        list_controls()
    else:
        controller = GestureController(
            config_path=args.config,
            camera_id=args.camera,
            mode=args.mode,
            demo=args.demo,
        )
        controller.run()
