# -*- mode: python ; coding: utf-8 -*-
"""Folder build of the Qt app. Run from the repo root:

    python -m PyInstaller --noconfirm --clean localpasswordvault.spec

A one-file executable unpacks itself on every launch, which is the slow start.
This build leaves the libraries beside the executable and omits Qt modules the
vault does not load (WebEngine, 3D, multimedia, charts).
"""

from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("qt_ui/qml", "qt_ui/qml"),
    ("wordlist.txt", "."),
]

hiddenimports = collect_submodules("qt_ui") + [
    "config",
    "crypto",
    "vault_db",
    "totp",
    "qrcode",
    "cryptography.hazmat.primitives.kdf.argon2",
    "cryptography.hazmat.primitives.ciphers.aead",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQml",
]

excludes = [
    "customtkinter",
    "tkinter",
    "PIL",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtQuick3D",
    "PySide6.QtDesigner",
    "PySide6.QtBluetooth",
    "PySide6.QtLocation",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtTextToSpeech",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtHelp",
]

# Software OpenGL and the widgets library are not used. Qt Quick draws with
# the normal Windows graphics driver.
_DROP = ("opengl32sw.dll", "qt6pdf.dll", "qdirect2d.dll")


def _keep_binary(entry) -> bool:
    name = str(entry[0]).replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name not in _DROP


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["packaging/hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
a.binaries = [entry for entry in a.binaries if _keep_binary(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalPasswordVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LocalPasswordVault",
)
