import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes


class MultiMonitor:
    def __init__(self):
        self.monitors = []
        self.current_monitor = 0
        self.detect_monitors()

    def detect_monitors(self):
        self.monitors = []

        if IS_WINDOWS:
            try:
                EnumDisplayMonitors = ctypes.windll.user32.EnumDisplayMonitors
                MONITORENUMPROC = ctypes.WINFUNCTYPE(
                    ctypes.wintypes.BOOL,
                    ctypes.wintypes.HANDLE,
                    ctypes.wintypes.HDC,
                    ctypes.POINTER(ctypes.wintypes.RECT),
                    ctypes.wintypes.LPARAM,
                )
                EnumDisplayMonitors(None, None, MONITORENUMPROC(self._callback), 0)
            except Exception:
                pass

        if not self.monitors:
            try:
                import screeninfo
                for m in screeninfo.get_monitors():
                    self.monitors.append({
                        "x": m.x, "y": m.y,
                        "width": m.width, "height": m.height,
                        "name": m.name or f"Monitor {len(self.monitors) + 1}",
                        "is_primary": (m.x == 0 and m.y == 0),
                    })
            except Exception:
                pass

        if not self.monitors:
            sm_cxscreen, sm_cyscreen = 1920, 1080
            if IS_WINDOWS:
                try:
                    sm_cxscreen = ctypes.windll.user32.GetSystemMetrics(0)
                    sm_cyscreen = ctypes.windll.user32.GetSystemMetrics(1)
                except Exception:
                    pass
            else:
                try:
                    import pyautogui
                    sm_cxscreen, sm_cyscreen = pyautogui.size()
                except Exception:
                    pass
            self.monitors.append({
                "x": 0, "y": 0,
                "width": sm_cxscreen, "height": sm_cyscreen,
                "name": "Primary",
                "is_primary": True,
            })

    def _callback(self, hmonitor, hdc, rect, data):
        try:
            r = rect.contents
            x = r.left
            y = r.top
            width = r.right - r.left
            height = r.bottom - r.top

            is_primary = (x == 0 and y == 0)

            self.monitors.append({
                "x": x, "y": y,
                "width": width, "height": height,
                "name": f"Monitor {len(self.monitors) + 1}",
                "is_primary": is_primary,
            })
        except Exception:
            pass
        return True

    def get_monitors(self):
        return self.monitors

    def get_monitor_count(self):
        return len(self.monitors)

    def get_current_monitor(self):
        return self.current_monitor

    def set_current_monitor(self, index):
        if 0 <= index < len(self.monitors):
            self.current_monitor = index
            return True
        return False

    def next_monitor(self):
        self.current_monitor = (self.current_monitor + 1) % len(self.monitors)
        return self.current_monitor

    def prev_monitor(self):
        self.current_monitor = (self.current_monitor - 1) % len(self.monitors)
        return self.current_monitor

    def get_monitor_info(self, index=None):
        if index is None:
            index = self.current_monitor
        if 0 <= index < len(self.monitors):
            return self.monitors[index]
        return None

    def map_to_monitor(self, x, y, source_monitor=None, target_monitor=None):
        if source_monitor is None:
            source_monitor = self.current_monitor
        if target_monitor is None:
            target_monitor = self.current_monitor

        src = self.monitors[source_monitor]
        tgt = self.monitors[target_monitor]

        norm_x = x / src["width"]
        norm_y = y / src["height"]

        screen_x = int(norm_x * tgt["width"]) + tgt["x"]
        screen_y = int(norm_y * tgt["height"]) + tgt["y"]

        return screen_x, screen_y

    def get_full_virtual_screen(self):
        if not self.monitors:
            return {"x": 0, "y": 0, "width": 1920, "height": 1080}

        min_x = min(m["x"] for m in self.monitors)
        min_y = min(m["y"] for m in self.monitors)
        max_x = max(m["x"] + m["width"] for m in self.monitors)
        max_y = max(m["y"] + m["height"] for m in self.monitors)

        return {
            "x": min_x, "y": min_y,
            "width": max_x - min_x,
            "height": max_y - min_y,
        }

    def point_in_monitor(self, x, y):
        for i, monitor in enumerate(self.monitors):
            if (monitor["x"] <= x < monitor["x"] + monitor["width"] and
                monitor["y"] <= y < monitor["y"] + monitor["height"]):
                return i
        return 0

    def center_on_monitor(self, monitor_index=None):
        if monitor_index is None:
            monitor_index = self.current_monitor

        monitor = self.monitors[monitor_index]
        center_x = monitor["x"] + monitor["width"] // 2
        center_y = monitor["y"] + monitor["height"] // 2

        if IS_WINDOWS:
            ctypes.windll.user32.SetCursorPos(center_x, center_y)
        else:
            import pyautogui
            was = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            try:
                pyautogui.moveTo(center_x, center_y, _pause=False)
            finally:
                pyautogui.FAILSAFE = was
        return center_x, center_y
