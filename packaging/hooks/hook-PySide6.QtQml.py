# Replace PyInstaller's QtQml hook, which copies every QML plugin.
# The vault loads Qt Quick, Basic controls, layouts, windows, and file dialogs.
# Destinations from the Qt hook are directories, not file names.

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()

_EXACT = {
    "PySide6/qml/QtQml",
    "PySide6/qml/QtQuick",
    "PySide6/qml/QtQuick/Controls",
    "PySide6/qml/QtQuick/Dialogs",
}
_PREFIX = (
    "PySide6/qml/QtQml/",
    "PySide6/qml/QtQuick/Controls/Basic",
    "PySide6/qml/QtQuick/Controls/impl",
    "PySide6/qml/QtQuick/Layouts",
    "PySide6/qml/QtQuick/Templates",
    "PySide6/qml/QtQuick/Window",
    "PySide6/qml/QtQuick/Dialogs/",
)


def _keep(dest) -> bool:
    path = str(dest).replace("\\", "/").rstrip("/")
    if path in _EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _PREFIX)


binaries += [(src, dest) for src, dest in qml_binaries if _keep(dest)]
datas += [(src, dest) for src, dest in qml_datas if _keep(dest)]
