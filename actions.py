import pyautogui
import ctypes
import subprocess
import sys
import time
import threading
import logging

IS_WINDOWS = sys.platform == "win32"

try:
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

if IS_WINDOWS:
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1

KEY_TO_VK = {
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
    "space": 0x20, "shift": 0x10, "e": 0x45, "r": 0x52,
    "f": 0x46, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
}

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

CURSOR_EDGE_MARGIN = 40


class GestureActions:
    def __init__(self):
        self.last_mouse_pos = None
        self.is_dragging = False
        self.drag_start_pos = None
        self.action_history = []
        self.tts_enabled = True
        self.speech_thread = None

        self.mode = "normal"
        self.presentation_slide = 0
        self.gaming_keys = {"w": False, "a": False, "s": False, "d": False}
        self.active_gaming_key = None
        self.gaming_hold_until = 0.0
        self.hand_range = None
        self.ui_events = []

        self.monitors = self._get_monitors()
        self.current_monitor = 0

    def _get_monitors(self):
        monitors = []
        try:
            import screeninfo
            for m in screeninfo.get_monitors():
                monitors.append({"x": m.x, "y": m.y, "width": m.width, "height": m.height, "name": m.name})
        except Exception:
            if user32 is not None:
                sm_cxscreen = user32.GetSystemMetrics(0)
                sm_cyscreen = user32.GetSystemMetrics(1)
            else:
                try:
                    sm_cxscreen, sm_cyscreen = pyautogui.size()
                except Exception:
                    sm_cxscreen, sm_cyscreen = 1920, 1080
            monitors.append({"x": 0, "y": 0, "width": sm_cxscreen, "height": sm_cyscreen, "name": "Primary"})
        return monitors if monitors else [{"x": 0, "y": 0, "width": 1920, "height": 1080, "name": "Primary"}]

    def set_mode(self, mode):
        self.mode = mode
        self._speak(f"Mode: {mode}")

    def set_hand_range(self, hand_range):
        self.hand_range = hand_range

    def tick(self):
        if self.active_gaming_key is not None and time.time() > self.gaming_hold_until:
            self._release_gaming_key()

    def execute(self, action, hand_center=None, frame_width=None, frame_height=None, confidence=1.0):
        if confidence < 0.5:
            return

        timestamp = time.time()

        action_handlers = {
            "mouse_move": lambda: self._move_mouse(hand_center, frame_width, frame_height),
            "left_click": lambda: self._left_click(),
            "right_click": lambda: self._right_click(),
            "double_click": lambda: self._double_click(),
            "middle_click": lambda: self._middle_click(),
            "scroll_up": lambda: self._scroll(-5),
            "scroll_down": lambda: self._scroll(5),
            "volume_up": lambda: self._volume_up(),
            "volume_down": lambda: self._volume_down(),
            "volume_mute": lambda: self._volume_mute(),
            "play_pause": lambda: self._play_pause(),
            "next_track": lambda: self._next_track(),
            "prev_track": lambda: self._prev_track(),
            "minimize_window": lambda: self._minimize_window(),
            "maximize_window": lambda: self._maximize_window(),
            "close_window": lambda: self._close_window(),
            "switch_app": lambda: self._switch_app(),
            "desktop": lambda: self._show_desktop(),
            "lock_screen": lambda: self._lock_screen(),
            "screenshot": lambda: self._screenshot(),
            "screenshot_region": lambda: self._screenshot_region(),
            "copy": lambda: self._copy(),
            "paste": lambda: self._paste(),
            "cut": lambda: self._cut(),
            "undo": lambda: self._undo(),
            "redo": lambda: self._redo(),
            "select_all": lambda: self._select_all(),
            "save": lambda: self._save(),
            "find": lambda: self._find(),
            "new_tab": lambda: self._new_tab(),
            "close_tab": lambda: self._close_tab(),
            "refresh": lambda: self._refresh(),
            "browser_back": lambda: self._browser_back(),
            "browser_forward": lambda: self._browser_forward(),
            "snap_left": lambda: self._snap_window("left"),
            "snap_right": lambda: self._snap_window("right"),
            "maximize_restore": lambda: self._maximize_restore(),
            "virtual_desktop_left": lambda: self._virtual_desktop("left"),
            "virtual_desktop_right": lambda: self._virtual_desktop("right"),
            "new_virtual_desktop": lambda: self._new_virtual_desktop(),
            "close_virtual_desktop": lambda: self._close_virtual_desktop(),
            "task_view": lambda: self._task_view(),
            "start_menu": lambda: self._start_menu(),
            "action_center": lambda: self._action_center(),
            "run_dialog": lambda: self._run_dialog(),
            "file_explorer": lambda: self._file_explorer(),
            "settings": lambda: self._settings(),
            "calculator": lambda: self._calculator(),
            "notepad": lambda: self._notepad(),
            "terminal": lambda: self._terminal(),
            "task_manager": lambda: self._task_manager(),
            "brightness_up": lambda: self._brightness_up(),
            "brightness_down": lambda: self._brightness_down(),
            "wifi_toggle": lambda: self._wifi_toggle(),
            "bluetooth_toggle": lambda: self._bluetooth_toggle(),
            "night_light": lambda: self._night_light(),
            "focus_assist": lambda: self._focus_assist(),
            "drag_start": lambda: self._drag_start(),
            "drag_end": lambda: self._drag_end(),
            "drag_move": lambda: self._drag_move(hand_center, frame_width, frame_height),
            "presentation_next": lambda: self._presentation_next(),
            "presentation_prev": lambda: self._presentation_prev(),
            "presentation_first": lambda: self._presentation_first(),
            "presentation_last": lambda: self._presentation_last(),
            "presentation_pointer": lambda: self._presentation_pointer(hand_center, frame_width, frame_height),
            "presentation_black": lambda: self._presentation_black(),
            "gaming_w": lambda: self._gaming_key("w"),
            "gaming_a": lambda: self._gaming_key("a"),
            "gaming_s": lambda: self._gaming_key("s"),
            "gaming_d": lambda: self._gaming_key("d"),
            "gaming_space": lambda: self._gaming_key("space"),
            "gaming_shift": lambda: self._gaming_key("shift"),
            "gaming_e": lambda: self._gaming_key("e"),
            "gaming_r": lambda: self._gaming_key("r"),
            "gaming_f": lambda: self._gaming_key("f"),
            "gaming_1": lambda: self._gaming_key("1"),
            "gaming_2": lambda: self._gaming_key("2"),
            "gaming_3": lambda: self._gaming_key("3"),
            "gaming_4": lambda: self._gaming_key("4"),
            "switch_monitor": lambda: self._switch_monitor(),
            "cursor_to_monitor": lambda: self._cursor_to_monitor(hand_center, frame_width, frame_height),
            "escape": lambda: self._escape(),
            "zoom_in": lambda: self._zoom_in(),
        }

        handler = action_handlers.get(action)
        if handler:
            try:
                handler()
            except Exception as e:
                msg = str(e).lower()
                if "fail-safe" in msg or "failsafe" in msg:
                    logger.warning(
                        "PyAutoGUI fail-safe triggered during %s, retrying with fail-safe disabled",
                        action,
                    )
                    pyautogui.FAILSAFE = False
                    try:
                        handler()
                        self.ui_events.append({
                            "type": "failsafe",
                            "action": action,
                            "time": timestamp,
                        })
                    except Exception as retry_err:
                        logger.error("Action %s failed after fail-safe override: %s", action, retry_err)
                    finally:
                        pyautogui.FAILSAFE = True
                else:
                    logger.error("Action %s failed: %s", action, e)
            self.action_history.append({
                "action": action,
                "time": timestamp,
                "confidence": confidence,
                "mode": self.mode,
            })
            if len(self.action_history) > 200:
                self.action_history.pop(0)

    def drain_ui_events(self):
        events = self.ui_events
        self.ui_events = []
        return events

    def _speak(self, text):
        if self.tts_enabled:
            def speak_thread():
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass
            self.speech_thread = threading.Thread(target=speak_thread, daemon=True)
            self.speech_thread.start()

    def _run_first(self, cmds):
        for cmd in cmds:
            try:
                subprocess.run(cmd, check=False, capture_output=True, timeout=2)
                return True
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        return False

    def _set_cursor_pos(self, x, y):
        x, y = int(x), int(y)
        if user32 is not None:
            user32.SetCursorPos(x, y)
        else:
            was = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            try:
                pyautogui.moveTo(x, y, _pause=False)
            finally:
                pyautogui.FAILSAFE = was

    def _normalize_hand(self, hand_center, frame_width, frame_height):
        x, y = hand_center
        rng = self.hand_range
        if rng:
            x0, x1 = rng.get("x", [0, 1])
            y0, y1 = rng.get("y", [0, 1])
            if (x1 - x0) > 0.02 and (y1 - y0) > 0.02:
                nx = (x - x0) / (x1 - x0)
                ny = (y - y0) / (y1 - y0)
                return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))
        return x / frame_width, y / frame_height

    def _set_cursor_from_hand(self, hand_center, frame_width, frame_height):
        if not hand_center or not frame_width or not frame_height:
            return

        monitor = self.monitors[self.current_monitor]
        screen_w = monitor["width"]
        screen_h = monitor["height"]
        offset_x = monitor["x"]
        offset_y = monitor["y"]

        nx, ny = self._normalize_hand(hand_center, frame_width, frame_height)
        screen_x = int(nx * screen_w) + offset_x
        screen_y = int(ny * screen_h) + offset_y

        margin = CURSOR_EDGE_MARGIN
        screen_x = max(offset_x + margin, min(offset_x + screen_w - 1 - margin, screen_x))
        screen_y = max(offset_y + margin, min(offset_y + screen_h - 1 - margin, screen_y))

        self._set_cursor_pos(screen_x, screen_y)

    def _move_mouse(self, hand_center, frame_width, frame_height):
        self._set_cursor_from_hand(hand_center, frame_width, frame_height)

    def _left_click(self):
        pyautogui.click()

    def _right_click(self):
        pyautogui.rightClick()

    def _double_click(self):
        pyautogui.doubleClick()

    def _middle_click(self):
        pyautogui.middleClick()

    def _scroll(self, amount):
        pyautogui.scroll(amount)

    def _win_keybd(self, vk):
        if user32 is None:
            return False
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return True

    def _volume_up(self):
        if user32 is not None:
            for _ in range(3):
                user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
            return
        self._run_first([
            ["amixer", "-q", "set", "Master", "5%+"],
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"],
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"],
        ])

    def _volume_down(self):
        if user32 is not None:
            for _ in range(3):
                user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
            return
        self._run_first([
            ["amixer", "-q", "set", "Master", "5%-"],
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"],
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"],
        ])

    def _volume_mute(self):
        if self._win_keybd(VK_VOLUME_MUTE):
            return
        self._run_first([
            ["amixer", "-q", "set", "Master", "toggle"],
            ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
            ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"],
        ])

    def _play_pause(self):
        if self._win_keybd(VK_MEDIA_PLAY_PAUSE):
            return
        self._run_first([["playerctl", "play-pause"]])

    def _next_track(self):
        if self._win_keybd(VK_MEDIA_NEXT):
            return
        self._run_first([["playerctl", "next"]])

    def _prev_track(self):
        if self._win_keybd(VK_MEDIA_PREV):
            return
        self._run_first([["playerctl", "previous"]])

    def _modifier_key(self, *keys):
        pyautogui.hotkey(*keys)

    def _minimize_window(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "down")
        else:
            pyautogui.hotkey("super", "h")

    def _maximize_window(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "up")
        else:
            pyautogui.hotkey("super", "up")

    def _close_window(self):
        pyautogui.hotkey("alt", "f4")

    def _switch_app(self):
        if IS_WINDOWS:
            pyautogui.hotkey("alt", "tab")
        else:
            pyautogui.hotkey("alt", "tab")

    def _show_desktop(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "d")
        else:
            pyautogui.hotkey("super", "d")

    def _lock_screen(self):
        if user32 is not None:
            user32.LockWorkStation()
            return
        if sys.platform == "darwin":
            self._run_first([["osascript", "-e", 'tell application "System Events" to keystroke "q" using {command down, control down}']])
        else:
            self._run_first([
                ["loginctl", "lock-session"],
                ["xdg-screensaver", "lock"],
            ])

    def _screenshot(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "printscreen")
        elif sys.platform == "darwin":
            pyautogui.hotkey("command", "shift", "3")
        else:
            pyautogui.hotkey("shift", "printscreen")

    def _screenshot_region(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "shift", "s")
        elif sys.platform == "darwin":
            pyautogui.hotkey("command", "shift", "4")
        else:
            pyautogui.hotkey("shift", "printscreen")

    def _copy(self):
        pyautogui.hotkey("ctrl", "c")
        self._speak("Copied")

    def _paste(self):
        pyautogui.hotkey("ctrl", "v")
        self._speak("Pasted")

    def _cut(self):
        pyautogui.hotkey("ctrl", "x")
        self._speak("Cut")

    def _undo(self):
        pyautogui.hotkey("ctrl", "z")
        self._speak("Undo")

    def _redo(self):
        pyautogui.hotkey("ctrl", "y")
        self._speak("Redo")

    def _select_all(self):
        pyautogui.hotkey("ctrl", "a")

    def _escape(self):
        pyautogui.press("esc")

    def _zoom_in(self):
        if sys.platform == "darwin":
            pyautogui.hotkey("command", "equal")
        else:
            pyautogui.hotkey("ctrl", "equal")

    def _save(self):
        pyautogui.hotkey("ctrl", "s")
        self._speak("Saved")

    def _find(self):
        pyautogui.hotkey("ctrl", "f")

    def _new_tab(self):
        pyautogui.hotkey("ctrl", "t")

    def _close_tab(self):
        pyautogui.hotkey("ctrl", "w")

    def _refresh(self):
        pyautogui.hotkey("ctrl", "r")

    def _browser_back(self):
        pyautogui.hotkey("alt", "left")

    def _browser_forward(self):
        pyautogui.hotkey("alt", "right")

    def _snap_window(self, direction):
        key = "left" if direction == "left" else "right"
        if IS_WINDOWS:
            pyautogui.hotkey("win", key)
        else:
            pyautogui.hotkey("super", key)

    def _maximize_restore(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "up")
        else:
            pyautogui.hotkey("super", "up")

    def _virtual_desktop(self, direction):
        key = "left" if direction == "left" else "right"
        if IS_WINDOWS:
            pyautogui.hotkey("ctrl", "win", key)
        else:
            pyautogui.hotkey("ctrl", "super", key)

    def _new_virtual_desktop(self):
        if IS_WINDOWS:
            pyautogui.hotkey("ctrl", "win", "d")
        else:
            pyautogui.hotkey("ctrl", "super", "d")

    def _close_virtual_desktop(self):
        if IS_WINDOWS:
            pyautogui.hotkey("ctrl", "win", "f4")
        else:
            pyautogui.hotkey("ctrl", "super", "f4")

    def _task_view(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "tab")
        else:
            pyautogui.hotkey("super", "tab")

    def _start_menu(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win")
        else:
            pyautogui.hotkey("super")

    def _action_center(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "a")
        else:
            pyautogui.hotkey("super", "a")

    def _run_dialog(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "r")
        else:
            pyautogui.hotkey("super", "r")

    def _file_explorer(self):
        if IS_WINDOWS:
            pyautogui.hotkey("win", "e")
        elif sys.platform == "darwin":
            self._run_first([["open", "."]])
        else:
            self._run_first([["xdg-open", "."]])

    def _settings(self):
        if IS_WINDOWS:
            subprocess.Popen(["start", "ms-settings:"], shell=True)
        elif sys.platform == "darwin":
            self._run_first([["open", "x-apple.systempreferences:"]])
        else:
            self._run_first([["gnome-control-center"], ["systemsettings"], ["unity-control-center"]])

    def _calculator(self):
        if IS_WINDOWS:
            subprocess.Popen(["calc.exe"])
        elif sys.platform == "darwin":
            self._run_first([["open", "-a", "Calculator"]])
        else:
            self._run_first([["gnome-calculator"], ["kcalc"], ["xcalc"]])

    def _notepad(self):
        if IS_WINDOWS:
            subprocess.Popen(["notepad.exe"])
        elif sys.platform == "darwin":
            self._run_first([["open", "-a", "TextEdit"]])
        else:
            self._run_first([["gedit"], ["kate"], ["mousepad"], ["xdg-open", "/tmp"]])

    def _terminal(self):
        if IS_WINDOWS:
            try:
                subprocess.Popen(["wt.exe"])
            except FileNotFoundError:
                subprocess.Popen(["cmd.exe"])
        elif sys.platform == "darwin":
            self._run_first([["open", "-a", "Terminal"]])
        else:
            self._run_first([
                ["gnome-terminal"],
                ["konsole"],
                ["xterm"],
                ["x-terminal-emulator"],
            ])

    def _task_manager(self):
        pyautogui.hotkey("ctrl", "shift", "esc")

    def _brightness_up(self):
        if self._run_first([
            ["brightnessctl", "set", "+10%"],
            ["xbacklight", "-inc", "10"],
            ["light", "-A", "10"],
        ]):
            return
        if IS_WINDOWS:
            pyautogui.hotkey("win", "a")

    def _brightness_down(self):
        if self._run_first([
            ["brightnessctl", "set", "10%-"],
            ["xbacklight", "-dec", "10"],
            ["light", "-U", "10"],
        ]):
            return
        if IS_WINDOWS:
            pyautogui.hotkey("win", "a")

    def _wifi_toggle(self):
        pyautogui.hotkey("win", "a") if IS_WINDOWS else pyautogui.hotkey("super", "a")

    def _bluetooth_toggle(self):
        pyautogui.hotkey("win", "a") if IS_WINDOWS else pyautogui.hotkey("super", "a")

    def _night_light(self):
        pyautogui.hotkey("win", "a") if IS_WINDOWS else pyautogui.hotkey("super", "a")

    def _focus_assist(self):
        pyautogui.hotkey("win", "a") if IS_WINDOWS else pyautogui.hotkey("super", "a")

    def _mouse_button(self, down):
        if user32 is not None:
            flag = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
            user32.mouse_event(flag, 0, 0, 0, 0)
        elif down:
            pyautogui.mouseDown(_pause=False)
        else:
            pyautogui.mouseUp(_pause=False)

    def _drag_start(self):
        self.is_dragging = True
        if HAS_WIN32:
            self.drag_start_pos = win32api.GetCursorPos()
        else:
            self.drag_start_pos = pyautogui.position()
        self._mouse_button(True)
        self._speak("Drag started")

    def _drag_end(self):
        if self.is_dragging:
            self._mouse_button(False)
            self.is_dragging = False
            self.drag_start_pos = None
            self._speak("Drop")

    def _drag_move(self, hand_center, frame_width, frame_height):
        if self.is_dragging:
            self._set_cursor_from_hand(hand_center, frame_width, frame_height)

    def _presentation_next(self):
        pyautogui.press("right")
        self.presentation_slide += 1
        self._speak(f"Slide {self.presentation_slide}")

    def _presentation_prev(self):
        pyautogui.press("left")
        self.presentation_slide = max(0, self.presentation_slide - 1)
        self._speak(f"Slide {self.presentation_slide}")

    def _presentation_first(self):
        pyautogui.press("home")
        self.presentation_slide = 0
        self._speak("First slide")

    def _presentation_last(self):
        pyautogui.press("end")
        self._speak("Last slide")

    def _presentation_pointer(self, hand_center, frame_width, frame_height):
        self._set_cursor_from_hand(hand_center, frame_width, frame_height)

    def _presentation_black(self):
        pyautogui.press("b")
        self._speak("Black screen")

    def _press_key_start(self, key):
        if user32 is not None:
            vk = KEY_TO_VK[key]
            user32.keybd_event(vk, 0, 0, 0)
        else:
            pyautogui.keyDown(key)

    def _press_key_end(self, key):
        if user32 is not None:
            vk = KEY_TO_VK[key]
            user32.keybd_event(vk, 0, 2, 0)
        else:
            pyautogui.keyUp(key)

    def _release_gaming_key(self):
        if self.active_gaming_key is not None:
            try:
                self._press_key_end(self.active_gaming_key)
            except Exception as e:
                logger.error("Failed to release gaming key %s: %s", self.active_gaming_key, e)
            self.active_gaming_key = None

    def _gaming_key(self, key):
        if key not in KEY_TO_VK:
            return
        if self.active_gaming_key != key:
            self._release_gaming_key()
            self._press_key_start(key)
            self.active_gaming_key = key
        self.gaming_hold_until = time.time() + 0.2

    def _switch_monitor(self):
        self.current_monitor = (self.current_monitor + 1) % len(self.monitors)
        self._speak(f"Monitor {self.current_monitor + 1}")

    def _cursor_to_monitor(self, hand_center, frame_width, frame_height):
        if hand_center:
            monitor = self.monitors[self.current_monitor]
            screen_w = monitor["width"]
            screen_h = monitor["height"]
            offset_x = monitor["x"]
            offset_y = monitor["y"]

            nx, ny = self._normalize_hand(hand_center, frame_width, frame_height)
            x = int(nx * screen_w) + offset_x
            y = int(ny * screen_h) + offset_y

            margin = CURSOR_EDGE_MARGIN
            x = max(offset_x + margin, min(offset_x + screen_w - 1 - margin, x))
            y = max(offset_y + margin, min(offset_y + screen_h - 1 - margin, y))

            self._set_cursor_pos(x, y)

    def get_action_history(self):
        return self.action_history[-30:]

    def get_mode(self):
        return self.mode

    def get_current_monitor(self):
        return self.current_monitor, len(self.monitors)

    def is_dragging_active(self):
        return self.is_dragging
