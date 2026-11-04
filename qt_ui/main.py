"""Qt Quick application entry."""
import os
import platform
import sys

from PySide6.QtCore import QEvent, QObject, QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from config import APP_TITLE, C, get_theme, load_theme
from qt_ui.bridge import VaultBridge
from qt_ui.palette import Palette


def qml_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "qt_ui", "qml")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml")


def apply_caption(window):
    """Windows 11 caption color. No-op elsewhere."""
    if platform.system() != "Windows" or window is None:
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi

        def _set(attr: int, value: int):
            raw = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(raw), ctypes.sizeof(raw))

        dark = get_theme() == "dark"
        _set(20, 1 if dark else 0)
        hex_color = C["bg"].lstrip("#")
        red, green, blue = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        colorref = red | (green << 8) | (blue << 16)
        _set(35, colorref)
        _set(34, colorref)
        _set(33, 2)
    except Exception:
        pass


class ActivityFilter(QObject):
    def __init__(self, bridge: VaultBridge):
        super().__init__()
        self._bridge = bridge

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind in (
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
        ):
            self._bridge.noteActivity()
        return False


def release_qml(engine):
    """Destroy the QML windows while the theme and bridge are still alive.

    Shutting down the engine clears `lpv` and `bridge` before the windows are
    gone. Every binding then logs ``Cannot read property '…' of null``.
    """
    from shiboken6 import delete, isValid

    if engine is None or not isValid(engine):
        return
    for root in list(engine.rootObjects()):
        if isValid(root):
            delete(root)
    if isValid(engine):
        engine.collectGarbage()


def build(app):
    """Create the palette, bridge, and engine. Does not enter the event loop."""
    load_theme()
    QQuickStyle.setStyle("Basic")
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
    # Palette, then bridge (child of the palette), then the engine. release_qml()
    # still has to drop the windows before the engine is destroyed.
    palette = Palette(app)
    app.setFont(QFont(palette.uiFamily, 10))
    bridge = VaultBridge(palette)
    engine = QQmlApplicationEngine(app)
    engine.rootContext().setContextProperty("lpv", palette)
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(os.path.join(qml_dir(), "Main.qml")))
    roots = engine.rootObjects()
    if roots:
        def paint():
            apply_caption(roots[0])

        palette.changed.connect(paint)
        QTimer.singleShot(0, paint)
    return engine, bridge, palette


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName(APP_TITLE)
    engine, bridge, _palette = build(app)
    if not engine.rootObjects():
        raise SystemExit("Could not load the Qt Quick interface.")
    activity = ActivityFilter(bridge)
    app.installEventFilter(activity)
    # Keep the filter alive for the process lifetime.
    app._lpv_activity = activity
    app._lpv_engine = engine
    code = app.exec()
    release_qml(engine)
    return code


if __name__ == "__main__":
    main()
