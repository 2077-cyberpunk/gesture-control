
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

import threading


class TrayIcon:
    def __init__(self, controller):
        self.controller = controller
        self.icon = None
        self.is_running = False
        self.icon_thread = None

    def create_icon_image(self, color="green"):
        if not HAS_TRAY:
            return None

        colors = {
            "green": (0, 255, 0),
            "red": (255, 0, 0),
            "yellow": (255, 255, 0),
            "blue": (0, 100, 255),
        }
        rgb = colors.get(color, (0, 255, 0))

        image = Image.new("RGB", (64, 64), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 56, 56], fill=rgb)
        draw.ellipse([20, 20, 44, 44], fill=(0, 0, 0))
        return image

    def setup_menu(self):
        if not HAS_TRAY:
            return None

        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self._show_window, default=True),
            pystray.MenuItem("Gesture Controller", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Mode", pystray.Menu(
                pystray.MenuItem("Normal", lambda icon, item: self._set_mode("normal")),
                pystray.MenuItem("Presentation", lambda icon, item: self._set_mode("presentation")),
                pystray.MenuItem("Gaming", lambda icon, item: self._set_mode("gaming")),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Calibration", pystray.Menu(
                pystray.MenuItem("Start", lambda icon, item: self.controller._start_calibration()),
                pystray.MenuItem("Reset", lambda icon, item: self.controller._reset_calibration()),
            )),
            pystray.MenuItem("Macros", pystray.Menu(
                pystray.MenuItem("Start Recording", lambda icon, item: self.controller._start_macro_recording()),
                pystray.MenuItem("Stop Recording", lambda icon, item: self.controller._stop_macro_recording()),
                pystray.MenuItem("Stop Playback", lambda icon, item: self.controller._stop_macro_playback()),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", None, enabled=False),
            pystray.MenuItem("Mode: Normal", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        return menu

    def start(self):
        if not HAS_TRAY:
            print("pystray not installed. Tray icon disabled.")
            print("Install with: pip install pystray pillow")
            return

        menu = self.setup_menu()
        self.icon = pystray.Icon(
            "GestureController",
            self.create_icon_image("green"),
            "Gesture Controller",
            menu,
        )

        self.is_running = True
        self.icon_thread = threading.Thread(target=self._run_icon, daemon=True)
        self.icon_thread.start()

    def _run_icon(self):
        try:
            self.icon.run()
        except Exception:
            self.is_running = False

    def stop(self):
        if self.icon and self.is_running:
            self.is_running = False
            self.icon.stop()

    def update_status(self, mode="normal", is_active=True):
        if self.icon and HAS_TRAY:
            color = "green" if is_active else "red"
            if mode == "presentation":
                color = "blue"
            elif mode == "gaming":
                color = "yellow"

            try:
                self.icon.icon = self.create_icon_image(color)
            except Exception:
                pass

    def _show_window(self, icon=None, item=None):
        pass

    def _set_mode(self, mode):
        self.controller.set_mode(mode)

    def _quit(self, icon=None, item=None):
        self.stop()
        self.controller.should_quit = True
