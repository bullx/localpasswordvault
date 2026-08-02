# LocalPasswordVault

Desktop password manager and encryption tool for **Windows** and **macOS**.

- **Storage:** SQLite (`localpasswordvault.db`) with field-level encryption  
- **Crypto:** Argon2id + AES-256-GCM (random DEK wrapped by master / recovery)  
- **2FA:** App-level TOTP (`localpasswordvault.2fa`) + recovery codes  
- **UI:** CustomTkinter (Vault · Encrypt · Generate · Settings)

Requires **Python 3.11+**. Licensed under the [MIT License](LICENSE).

### Screenshots

<p align="center">
  <img src="screenshots/01-create-vault.png" alt="Create vault" width="720" />
</p>

| Vault | Encrypt |
|:-----:|:-------:|
| ![Vault](screenshots/03-vault-entry.png) | ![Encrypt](screenshots/04-encrypt.png) |

| Generate | Settings |
|:--------:|:--------:|
| ![Generate](screenshots/05-generate.png) | ![Settings](screenshots/06-settings.png) |

| Export / 2FA | Empty vault |
|:------------:|:-----------:|
| ![Export & 2FA](screenshots/07-settings-export-2fa.png) | ![Empty vault](screenshots/02-vault-empty.png) |

---

## Disclaimer — use AS IS

**LocalPasswordVault is provided AS IS, without warranty of any kind**, express or implied, including but not limited to merchantability, fitness for a particular purpose, and non-infringement. The authors are **not liable** for any data loss, security breach, or damages arising from use of this software.

- This is a **personal / experimental** tool, not a substitute for an audited commercial password manager.
- **You** are responsible for strong master passwords, recovery passphrase custody, backups, and your threat model.
- Metadata such as titles, usernames, URLs, and notes are stored **in plaintext** in the SQLite file; only password and TOTP secret fields are field-encrypted.
- There is **no formal security audit**. Run tests (`pytest`) before relying on a build; keep encrypted exports.
- By using this software you accept these terms. See also [LICENSE](LICENSE) and [architecture.md](architecture.md).


---

## Quick start (clone from Git)

```bash
git clone <YOUR_REPO_URL> localpasswordvault
cd localpasswordvault
```

Then pick **with venv** (recommended) or **without venv** below.

### Windows — run with venv

```powershell
cd C:\path\to\localpasswordvault
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Deactivate later with `deactivate`.

### Windows — run without venv

Installs into the active Python (user or system). Prefer `--user` if you are not in a venv:

```powershell
cd C:\path\to\localpasswordvault
py -3.11 -m pip install --user -r requirements.txt
py -3.11 app.py
```

Or, if `python` already points at 3.11+:

```powershell
python -m pip install -r requirements.txt
python app.py
```

### macOS — run with venv

```bash
cd /path/to/localpasswordvault
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

On Apple Silicon / Homebrew Python, `python3` is usually fine if it is 3.11+.

Deactivate later with `deactivate`.

### macOS — run without venv

```bash
cd /path/to/localpasswordvault
python3 -m pip install --user -r requirements.txt
python3 app.py
```

---

## How to run (all options)

Always run commands from the **repository root** (the folder that contains `app.py`).

| Method | With venv | Without venv |
|--------|-----------|--------------|
| Direct script (recommended) | `python app.py` | `python app.py` / `py -3.11 app.py` / `python3 app.py` |
| Module entry | `python __main__.py` | same |
| Editable install + CLI | `pip install -e .` then `localpasswordvault` | `pip install --user -e .` then `localpasswordvault` |

### Editable install (optional)

Uses `pyproject.toml` and registers the `localpasswordvault` console script.

**Windows (venv):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
localpasswordvault
```

**Windows (no venv):**

```powershell
py -3.11 -m pip install --user -e .
localpasswordvault
```

**macOS (venv):**

```bash
source .venv/bin/activate
pip install -e .
localpasswordvault
```

**macOS (no venv):**

```bash
python3 -m pip install --user -e .
localpasswordvault
```

> **Note:** Prefer `python app.py` from the repo root. The flat module layout (`from config import …`) is designed for that. `python -m LocalPasswordVault` only works when the *parent* of this folder is on `PYTHONPATH` and can be fragile; stick to `app.py` or the `localpasswordvault` script after `pip install -e .`.

---

## Data files (important)

Vault data is stored **next to the app**, not in a user profile folder:

| File | Purpose |
|------|---------|
| `localpasswordvault.db` | Encrypted vault (SQLite) |
| `localpasswordvault.db.bak` | Auto backup of the vault |
| `localpasswordvault.2fa` | Encrypted app TOTP secret + recovery hashes |

- When running from source: files appear in the **repo directory**.  
- When running a frozen binary: files appear **next to the executable**.

**Never commit** `localpasswordvault.db`, `localpasswordvault.2fa`, or backups. `.gitignore` already excludes them.

Unlock needs: **master password** + (if 2FA is on) **TOTP or recovery code**.  
An attacker needs the `.db` file, the `.2fa` file (if 2FA enabled), and the master password.

**Upgrading older vaults:** First unlock with the **master** password migrates fields to a DEK. After that, open Settings → Recovery and re-save your recovery passphrase so recovery unlock works with the new model. Skipping recovery at create no longer writes a `__NO_RECOVERY__` backdoor.

---

## Git hosting checklist

Make the repo safe to publish:

1. **Init and first commit** (local):

   ```bash
   git init
   git add .
   git status   # confirm no .db / .2fa / .venv
   git commit -m "Initial LocalPasswordVault release"
   ```

2. **Remote** (GitHub example):

   ```bash
   gh repo create localpasswordvault --private --source=. --remote=origin --push
   ```

   Or add a remote manually and `git push -u origin main`.

3. **Do not publish** real vaults. Use a throwaway vault for demos/screenshots.  
4. `cursor_plan.md` is gitignored (local session notes).  
5. Prefer a **private** repo until you are sure no secrets were ever committed.  
6. Before the first commit, run `git status` and confirm `.db` / `.2fa` / `.venv` / `dist/` are **not** staged.

---

## Dependencies

Declared in two places (keep them aligned):

| File | Role |
|------|------|
| `requirements.txt` | Fast `pip install -r` for developers |
| `pyproject.toml` | Package metadata, Python `>=3.11`, console entry `localpasswordvault` |

Runtime packages:

- `cryptography` — Argon2id + AES-GCM  
- `customtkinter` — UI  
- `qrcode` — 2FA transfer QR (matrix rendered in Tk; Pillow not required)

System requirements:

- **Windows:** Tk is bundled with official python.org / most `py` installs.  
- **macOS:** use python.org or Homebrew Python; if Tk is missing, install a Python build that includes Tcl/Tk (e.g. `brew install python-tk` when applicable).

---

## Build distributable binaries

Ship a single GUI executable with **PyInstaller**. Build on the OS you target (Windows build → Windows `.exe`; macOS build → macOS binary).

Install the build tool (venv recommended):

```bash
pip install pyinstaller
```

### Windows — build with venv

```powershell
cd C:\path\to\localpasswordvault
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
pyinstaller localpasswordvault.spec
```

Output: `dist\LocalPasswordVault.exe`

Distribute that file (zip it if you like). First run creates `localpasswordvault.db` beside the exe.

### Windows — build without venv

```powershell
cd C:\path\to\localpasswordvault
py -3.11 -m pip install --user -r requirements.txt pyinstaller
py -3.11 -m PyInstaller localpasswordvault.spec
```

### macOS — build with venv

```bash
cd /path/to/localpasswordvault
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller localpasswordvault.spec
```

Output: `dist/LocalPasswordVault`

```bash
chmod +x dist/LocalPasswordVault
open dist/LocalPasswordVault
# or: ./dist/LocalPasswordVault
```

### macOS — build without venv

```bash
cd /path/to/localpasswordvault
python3 -m pip install --user -r requirements.txt pyinstaller
python3 -m PyInstaller localpasswordvault.spec
```

### Distribute without packaging (source via Git)

Recipients clone and run (venv or not) as in [Quick start](#quick-start-clone-from-git). This is the simplest “git distribution” path—no binary, same source for all platforms.

### Optional: one-folder build

If antivirus or macOS Gatekeeper fights one-file mode, use:

```bash
pyinstaller --noconfirm --windowed --name LocalPasswordVault app.py
```

Then zip the entire `dist/LocalPasswordVault/` folder.

### Code signing (release hardening)

| Platform | Notes |
|----------|--------|
| Windows | Sign `LocalPasswordVault.exe` with a code-signing cert (`signtool`) to reduce SmartScreen warnings |
| macOS | `codesign` + notarization for Gatekeeper; unsigned apps need right-click → Open |

Not required for personal/private distribution.

---

## Feature map

| Tab | What it does |
|-----|----------------|
| **Vault** | Store credentials; per-entry passwords encrypted; optional per-entry TOTP |
| **Encrypt** | Standalone text/file encrypt & decrypt (same crypto stack) |
| **Generate** | Password / passphrase generator + strength meter |
| **Settings** | Change master/recovery, export/import encrypted JSON, enable/manage 2FA |

---

## Development notes

- Heavy crypto (unlock, export, encrypt file, etc.) runs off the UI thread via `ui_async.run_async`.  
- UI scale lives in `config.UI_SCALE`.  
- Clipboard copies auto-clear after 30 seconds; idle auto-lock defaults to 5 minutes (Settings).  
- See [architecture.md](architecture.md) for module layout, threat model, and packaging caveats.

### Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Covers encrypt/decrypt, master vs recovery unlock, import TOTP retention, and no-recovery create.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: config` (source) | Run from the repo root: `cd …\localpasswordvault` then `python app.py`. |
| `ModuleNotFoundError: config` (`.exe`) | Rebuild from the repo root with the updated spec: `pyinstaller --noconfirm --clean localpasswordvault.spec`. Use the new `dist\LocalPasswordVault.exe` (old builds missed local modules). |
| `ModuleNotFoundError: customtkinter` | `pip install -r requirements.txt` (venv active if you use one) |
| `python` not found (Windows) | Use `py` / `python` or install from python.org and tick “Add to PATH” |
| `py -3.11` fails | This machine may only have 3.12/3.13 — use `python` or `py -3.13` (3.11+ is fine) |
| Tk / display errors on macOS | Use a Python build with Tcl/Tk; don’t use a headless-only install |
| Wrong / empty vault after moving the app | Vault path follows the app folder—copy `.db` / `.2fa` / `.bak` with the binary |
| Damaged vault screen | Restore from `.bak` in the unlock UI, or reset and create a new vault |
| Lost authenticator | Use a recovery code → Settings → 2FA → Show Transfer QR |

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 LocalPasswordVault Contributors.  
The MIT text includes an AS-IS warranty disclaimer; the [Disclaimer](#disclaimer--use-as-is) section above adds product-use caveats beyond the license.
