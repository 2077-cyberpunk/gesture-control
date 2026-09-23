import json
import os
import time
import threading


class MacroRecorder:
    def __init__(self):
        self.is_recording = False
        self.is_playing = False
        self.recording_start_time = 0
        self.current_macro = []
        self.saved_macros = {}
        self.macro_file = "macros.json"
        self.playback_thread = None
        self.playback_speed = 1.0
        self.current_macro_name = None

        self.load_macros()

    def start_recording(self, macro_name=None):
        if self.is_playing:
            return False

        self.is_recording = True
        self.recording_start_time = time.time()
        self.current_macro = []
        self.current_macro_name = macro_name or f"macro_{int(time.time())}"
        return True

    def stop_recording(self):
        self.is_recording = False
        if self.current_macro:
            self.saved_macros[self.current_macro_name] = {
                "actions": self.current_macro,
                "created": time.time(),
                "duration": time.time() - self.recording_start_time,
            }
            self.save_macros()
            return self.current_macro_name
        return None

    def record_action(self, gesture, action, hand_center=None):
        if not self.is_recording:
            return

        timestamp = time.time() - self.recording_start_time
        self.current_macro.append({
            "gesture": gesture,
            "action": action,
            "time": timestamp,
            "hand_center": hand_center,
        })

    def play_macro(self, macro_name, callback=None):
        if macro_name not in self.saved_macros or self.is_recording:
            return False

        self.is_playing = True
        macro = self.saved_macros[macro_name]

        def play_thread():
            actions = macro["actions"]
            for i, entry in enumerate(actions):
                if not self.is_playing:
                    break

                if i > 0:
                    delay = (entry["time"] - actions[i-1]["time"]) / self.playback_speed
                    time.sleep(max(0, delay))

                if callback:
                    callback(entry["gesture"], entry["action"], entry.get("hand_center"))

            self.is_playing = False

        self.playback_thread = threading.Thread(target=play_thread, daemon=True)
        self.playback_thread.start()
        return True

    def stop_playback(self):
        self.is_playing = False

    def delete_macro(self, macro_name):
        if macro_name in self.saved_macros:
            del self.saved_macros[macro_name]
            self.save_macros()
            return True
        return False

    def rename_macro(self, old_name, new_name):
        if old_name in self.saved_macros and new_name not in self.saved_macros:
            self.saved_macros[new_name] = self.saved_macros.pop(old_name)
            self.save_macros()
            return True
        return False

    def list_macros(self):
        result = []
        for name, data in self.saved_macros.items():
            result.append({
                "name": name,
                "actions": len(data["actions"]),
                "duration": data.get("duration", 0),
                "created": data.get("created", 0),
            })
        return sorted(result, key=lambda x: x["created"], reverse=True)

    def set_playback_speed(self, speed):
        self.playback_speed = max(0.25, min(4.0, speed))

    def save_macros(self):
        try:
            with open(self.macro_file, "w") as f:
                json.dump(self.saved_macros, f, indent=2)
            return True
        except Exception:
            return False

    def load_macros(self):
        if os.path.exists(self.macro_file):
            try:
                with open(self.macro_file, "r") as f:
                    self.saved_macros = json.load(f)
                return True
            except Exception:
                return False
        return False

    def get_recording_status(self):
        return {
            "is_recording": self.is_recording,
            "is_playing": self.is_playing,
            "macro_name": self.current_macro_name if self.is_recording else None,
            "actions_recorded": len(self.current_macro),
            "elapsed_time": time.time() - self.recording_start_time if self.is_recording else 0,
        }

    def export_macro(self, macro_name, export_path):
        if macro_name in self.saved_macros:
            try:
                with open(export_path, "w") as f:
                    json.dump({macro_name: self.saved_macros[macro_name]}, f, indent=2)
                return True
            except Exception:
                return False
        return False

    def import_macro(self, import_path):
        try:
            with open(import_path, "r") as f:
                data = json.load(f)
            for name, macro_data in data.items():
                if name not in self.saved_macros:
                    self.saved_macros[name] = macro_data
            self.save_macros()
            return True
        except Exception:
            return False
