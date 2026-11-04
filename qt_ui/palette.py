"""Navy and emerald tokens from config, exposed to QML."""
import platform

from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtGui import QFontDatabase, QGuiApplication

from config import C, get_theme, save_theme


def _camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


def _prefers_reduced_motion() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        enabled = ctypes.c_bool()
        # SPI_GETCLIENTAREAANIMATION — false when the user turns off window animation.
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return not bool(enabled.value)
    except Exception:
        return False
    return False


def _system_fonts() -> tuple[str, str]:
    if QGuiApplication.instance() is None:
        system = platform.system()
        if system == "Windows":
            return "Segoe UI", "Consolas"
        if system == "Darwin":
            return "Helvetica Neue", "Menlo"
        return "DejaVu Sans", "DejaVu Sans Mono"
    families = set(QFontDatabase.families())
    system = platform.system()
    if system == "Windows":
        ui_options = ("Segoe UI Variable", "Segoe UI")
        mono_options = ("Cascadia Mono", "Consolas")
    elif system == "Darwin":
        ui_options = ("SF Pro", "Helvetica Neue")
        mono_options = ("Menlo", "Monaco")
    else:
        ui_options = ("DejaVu Sans",)
        mono_options = ("DejaVu Sans Mono",)
    ui = next((name for name in ui_options if name in families), QGuiApplication.font().family())
    mono = next((name for name in mono_options if name in families), "monospace")
    return ui, mono


class Palette(QObject):
    """Semantic colors. Bindings refresh when `changed` fires."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._c = {}
        self._mode = "light"
        self._ui, self._mono = _system_fonts()
        self._reduce = _prefers_reduced_motion()
        self.reload()

    def reload(self):
        self._c = dict(C)
        self._mode = get_theme()
        self.changed.emit()

    @Property(str, notify=changed)
    def mode(self) -> str:
        return self._mode

    @Property(str, notify=changed)
    def uiFamily(self) -> str:
        return self._ui

    @Property(str, notify=changed)
    def monoFamily(self) -> str:
        return self._mono

    @Property(bool, notify=changed)
    def reduceMotion(self) -> bool:
        return self._reduce

    def set_mode(self, mode: str):
        mode = "dark" if str(mode).lower().startswith("d") else "light"
        if mode == get_theme():
            return
        save_theme(mode)
        self.reload()

    # Defined in the class body so PySide publishes them to QML.
    for _key in list(C):
        def _getter(self, token=_key):
            return self._c.get(token, "#000000")

        locals()[_camel(_key)] = Property(str, _getter, notify=changed)
    del _key, _getter
