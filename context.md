# Context for the next session

Read this before changing LocalPasswordVault. The running app is the Qt Quick UI. The vault format is already shipped and must keep opening existing files.

## How to run

From the repo root:

```powershell
cd C:\Custom\Projects\PycharmProjects\localpasswordvault
python app.py
```

That opens the PySide6 window. The previous CustomTkinter window is `python tk_app.py`. Dependencies are in `requirements.txt` (`PySide6>=6.6`, `customtkinter`, `cryptography`, `qrcode`). This machine used Python 3.13 and PySide6 6.12.

Vault files are created beside `config.py`: `localpasswordvault.db`, `.db.bak`, `.2fa`, and `localpasswordvault.prefs` for the theme. Do not commit them. Do not unlock the user's real vault while testing. Tests use a temp directory.

The Qt frozen build writes those files beside `dist\LocalPasswordVault\LocalPasswordVault.exe`, not inside `_internal`. The Tk frozen build uses `dist\LocalPasswordVaultTk\`. Do not unlock the same vault in both apps at once.

## What was finished

Qt Quick replaced CustomTkinter as the default window. Behavior matches the Tk app. `crypto.py`, `vault_db.py`, and `totp.py` were not rewritten for this UI and the on-disk format was not changed.

- `app.py` only inserts the repo root on `sys.path` and calls `qt_ui.main.main`.
- `tk_app.py` is the old `App` class. `__main__.py` and the `localpasswordvault` console script still call `app:main`, so they open Qt.
- `qt_ui/bridge.py` is `VaultBridge`, one `QObject`. QML calls slots. Heavy Argon2 work runs on a `QThread`. `finish_unlock()` runs on the GUI thread after `begin_unlock` returns.
- `qt_ui/palette.py` exposes `config` light/dark tokens to QML as `lpv`.
- `qt_ui/main.py` builds a `QGuiApplication`, loads `qt_ui/qml/Main.qml`, colors the Windows 11 caption, and calls `release_qml()` after the event loop so quit does not spam `Cannot read property '…' of null`.
- Screens: unlock and create, recovery reset, TOTP and recovery code, damaged-vault restore, then Vault, Encrypt, Generate, and Settings, including the 2FA wizard. QR codes are drawn on a Qt `Canvas` from the `qrcode` matrix. The otpauth URI is not put in a QML URL.
- Palette stays navy `#1E3A5F` and emerald `#059669` from `config.py`. Font is the system UI face (Segoe UI Variable, then Segoe UI). Poppins was the design-search suggestion and is not installed. Controls use a 1px border, antialiasing, and a focus ring that does not change the control size. The lock mark is `LpvMark.qml`.
- `config.py` imports CustomTkinter only inside the Tk font and theme helpers. The Qt process does not need it.
- `pytest -q` was green: 16 crypto tests, `tests/test_qt_smoke.py`, and `tests/test_qt_ui_flows.py` (18 total). The UI test sets `QT_QPA_PLATFORM=offscreen`, loads the real window, and walks create, sidebar pages, path copy, add entry, search, text encrypt, generate, theme, 2FA open/cancel, lock, and recovery reset.
- `localpasswordvault.spec` builds the Qt folder, about 110 MB on Windows. `packaging/hooks/hook-PySide6.QtQml.py` keeps Qt Quick, Basic controls, layouts, and file dialogs. Do not call `collect_all("PySide6")`. A Windows launch stayed up. A macOS Qt build was not run.
- The previous window is a separate PyInstaller command on `tk_app.py`, output name `LocalPasswordVaultTk`. It is not built by the Qt spec, because that spec excludes CustomTkinter. That frozen Tk build has not been run.

## Invariants

- Field tokens stay v4 AES-GCM under the DEK. Passphrase tokens stay Argon2id (master, recovery, export, text encrypt, `.2fa`, `LPVF` files).
- `begin_unlock` may run off the GUI thread. It must not leave the vault unlocked. `finish_unlock` stays on the GUI thread.
- `vault_db.vault` and `totp.tfa` are the singletons. The bridge looks them up on the module at call time so tests can replace them.
- Passwords are slot arguments only. Do not log them or put them in image URLs.
- Clipboard clear is 30 seconds and on lock, only if the clipboard still holds the value this process copied.
- Idle lock uses the vault's `idle_lock_minutes`. Recovery unlock forces a new master before the main shell.
- Do not call `collect_all("PySide6")` in the spec. That produced the 280 MB one-file build.

## Qt pitfalls already hit

- `release_qml()` must delete the QML root objects while `lpv` and `bridge` are still alive. The engine clears those context properties during its own destructor, and every binding then logs `Cannot read property '…' of null`. Parenting the engine last does not prevent that.
- Do not assign an unqualified property from a nested handler. `TapHandler { onTapped: pathCopied = true }` is an invalid write to a global. Use `pathLabel.pathCopied = true`, and declare the property before the handler.
- Do not put a `Repeater` inside a `ColumnLayout` or `RowLayout` and expect the delegates to appear. That hid the sidebar pages. `Shell.qml` uses four explicit nav buttons. Word-count radios are explicit. History, the vault list, and the security list use `ListView`. The QR grid is a `Canvas`.
- A `Rectangle` does not draw its border unless `border.width` is at least 1. Setting only `border.color` leaves the card borderless.
- `echoMode` cannot be read from Python with `QObject.property()` (no enum converter). UI tests find fields by `placeholderText`.
- Visual rows inside a `ListView` are on `contentItem.childItems()`, not always on `QObject.children()`.
- PyInstaller's stock QtQml hook copies every QML plugin, and those plugins pull large DLLs. Filter destinations in `packaging/hooks/hook-PySide6.QtQml.py`. Destinations are directories, not file names.

## File map

| Path | Role |
|------|------|
| `app.py` | Qt entry |
| `tk_app.py` | CustomTkinter entry |
| `qt_ui/main.py` | Process, engine, caption, idle-lock filter, `release_qml()` |
| `qt_ui/bridge.py` | All vault slots |
| `qt_ui/palette.py` | `lpv` colors and font names |
| `qt_ui/qml/Main.qml` | Window, shortcuts Ctrl+F / Ctrl+N / Ctrl+L, confirm and alert dialogs |
| `qt_ui/qml/UnlockPage.qml` | Create, unlock, TOTP, recovery code, damaged file, forced new master |
| `qt_ui/qml/Shell.qml` | Sidebar and page stack |
| `qt_ui/qml/VaultPage.qml` | Search, list, detail, live TOTP |
| `qt_ui/qml/EntryDialog.qml` | Add and edit |
| `qt_ui/qml/EncryptPage.qml` | Text token and `LPVF` file encrypt |
| `qt_ui/qml/GeneratePage.qml` | Password, passphrase, history |
| `qt_ui/qml/SettingsPage.qml` | Master, recovery, idle, import/export, backup, 2FA, theme, lock |
| `qt_ui/qml/TwoFaDialogs.qml` | Setup, transfer QR, codes, disable |
| `qt_ui/qml/LpvMark.qml` | Lock mark |
| `localpasswordvault.spec` | Qt folder build. Do not use it for `tk_app.py` |
| `packaging/hooks/hook-PySide6.QtQml.py` | QML plugin allow-list |
| `wordlist.txt` | Passphrase word list. The frozen build copies it |
| `tests/test_qt_ui_flows.py` | Offscreen window walk |
| `tests/test_qt_smoke.py` | Bridge-level temp vault |
| `tests/test_crypto_vault.py` | Format tests. Do not weaken these |

## Not done

- README screenshots are still the Tk window. Qt shots were not taken.
- The Windows Qt folder launches. Its screens were not clicked through in the frozen app. macOS Qt and both Tk frozen builds were not run.
- No GitHub remote was created in the original handoff. Do not commit `localpasswordvault.db`, `.2fa`, `.prefs`, `dist/`, or `build/`.
- The Tk modules are still the behavior reference if a Qt screen drifts. Prefer fixing Qt over restyling Tk.
