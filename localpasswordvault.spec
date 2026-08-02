# -*- mode: python ; coding: utf-8 -*-
# One-file desktop build. From repo root (venv activated recommended):
#   pip install pyinstaller
#   pyinstaller localpasswordvault.spec
#
# Output: dist/LocalPasswordVault.exe (Windows) or dist/LocalPasswordVault (macOS)
# Vault files are created next to the executable at runtime.

import os

from PyInstaller.utils.hooks import collect_all

block_cipher = None
SPECPATH = os.path.dirname(os.path.abspath(SPEC))

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")
qr_datas, qr_binaries, qr_hiddenimports = collect_all("qrcode")

# Flat sibling modules — must be named explicitly so one-file builds include them
# (a root __init__.py previously caused Analysis to miss top-level "config").
_LOCAL_MODULES = [
    "config",
    "crypto",
    "totp",
    "vault_db",
    "ui_common",
    "ui_async",
    "screen_unlock",
    "tab_vault",
    "tab_encrypt",
    "tab_generate",
    "tab_settings",
    "dialogs_2fa",
]

a = Analysis(
    [os.path.join(SPECPATH, "app.py")],
    pathex=[SPECPATH],
    binaries=ctk_binaries + qr_binaries,
    datas=ctk_datas + qr_datas + [(os.path.join(SPECPATH, "wordlist.txt"), ".")],
    hiddenimports=[
        "customtkinter",
        "qrcode",
        "cryptography",
        "cryptography.hazmat.primitives.kdf.argon2",
        "cryptography.hazmat.primitives.ciphers.aead",
    ] + _LOCAL_MODULES + ctk_hiddenimports + qr_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="LocalPasswordVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
