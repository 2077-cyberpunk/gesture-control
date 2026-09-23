import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_stub(name):
    if name in sys.modules:
        return sys.modules[name]
    try:
        __import__(name)
        return sys.modules[name]
    except ImportError:
        mod = types.ModuleType(name)
        mod.__dict__.update({k: MagicMock() for k in ()})
        mock = MagicMock(name=name)
        sys.modules[name] = mock
        return mock


_ensure_stub("cv2")
_ensure_stub("mediapipe")
_ensure_stub("pyautogui")
_ensure_stub("pystray")
