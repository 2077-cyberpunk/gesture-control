import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Always stub GUI packages in tests: real cv2/mediapipe/pyautogui/pystray
# need a display or platform libs and would crash on headless CI.
for _name in ("cv2", "mediapipe", "pyautogui", "pystray"):
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock(name=_name)
