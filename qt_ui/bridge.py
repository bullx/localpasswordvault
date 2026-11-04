"""
QObject the QML screens call.

crypto.py, vault_db.py, and totp.py stay the source of truth.
Argon2 work runs on a QThread. finish_unlock() runs on the GUI thread.
Passphrases are slot arguments, never QML urls or log lines.
"""
import os
import secrets
import sys
import time

from PySide6.QtCore import Property, QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

import totp as totp_mod
import vault_db
from config import BAK_FILE, PLATFORM, VAULT_FILE, CLIPBOARD_CLEAR_MS
from crypto import (
    _decrypt, _encrypt, decrypt_file, encrypt_file, gen_password,
    passphrase_entropy_bits, pw_strength,
)
from totp import _totp_code, _totp_valid


_PAGES = ("Vault", "Encrypt", "Generate", "Settings")


def _pad_b32(secret: str) -> str:
    return secret + "=" * ((8 - len(secret) % 8) % 8)


def _ellipsis(path: str, limit: int = 28) -> str:
    if len(path) <= limit:
        return path
    return "…" + path[-(limit - 1):]


def _load_wordlist() -> list[str]:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "wordlist.txt")
    try:
        with open(path, encoding="utf-8") as handle:
            words = [line.strip().lower() for line in handle if line.strip() and not line.startswith("#")]
        if len(words) >= 100:
            return words
    except OSError:
        pass
    return [
        "alpha", "bravo", "cedar", "delta", "ember", "frost", "grove", "harbor",
        "ivory", "jade", "kite", "lunar", "maple", "noble", "orbit", "pearl",
        "quartz", "raven", "solar", "thorn", "ultra", "vivid", "willow", "xenon",
        "yield", "zenith", "amber", "bloom", "coral", "dawn", "echo", "flame",
    ]


def _qr_rows(data: str) -> list[str]:
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=1, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    return ["".join("1" if cell else "0" for cell in row) for row in qr.get_matrix()]


class _Runner(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit({"value": self._fn()})
        except Exception as exc:
            self.failed.emit(str(exc))


class VaultBridge(QObject):
    stateChanged = Signal()
    entriesChanged = Signal()
    qrChanged = Signal()
    confirmRequested = Signal(str, str, str)
    alertRequested = Signal(str, str)
    entryDialogRequested = Signal(str)
    searchFocusRequested = Signal()
    textReady = Signal(str)
    clearFields = Signal(str)

    def __init__(self, palette=None):
        super().__init__(palette)
        self._palette = palette
        self._words = _load_wordlist()
        self._runner = None
        self._busy = False
        self._screen = "unlock"
        self._page = "Vault"
        self._notice = ""
        self._notice_level = "muted"
        self._entries = []
        self._verified_pw = ""
        self._draft_password = ""
        self._ask_id = ""
        self._pending_master = ""
        self._pending_delete = ""
        self._import_path = ""
        self._import_pp = ""
        self._qr_rows = []
        self._setup_open = False
        self._setup_page = 0
        self._setup_secret = ""
        self._setup_codes = []
        self._setup_error = ""
        self._transfer_open = False
        self._transfer_secret = ""
        self._codes_open = False
        self._issued_codes = []
        self._codes_regenerated = False
        self._code_action_open = False
        self._code_kind = ""
        self._code_title = ""
        self._code_body = ""
        self._code_button = ""
        self._code_danger = False
        self._code_error = ""
        self._disable_open = False
        self._disable_error = ""
        self._unlock_codes_on = False
        self._unlock_codes_left = 0
        self._two_fa_on = False
        self._two_fa_remaining = 0
        self._two_fa_codes = False
        self._master_msg = ""
        self._master_level = "muted"
        self._recovery_msg = ""
        self._recovery_level = "muted"
        self._idle_msg = ""
        self._idle_level = "muted"
        self._export_msg = ""
        self._export_level = "muted"
        self._count_text = "0 entries"
        self._idle_label = "Auto-lock off"
        self._idle_value = "5"
        self._recovery_set = False
        self._backup_ok = False
        self._backup_text = ""
        self._low_codes_pending = False
        self._clip = ""
        self._last_activity = 0.0
        self._clip_timer = QTimer(self)
        self._clip_timer.setSingleShot(True)
        self._clip_timer.timeout.connect(self._clear_clipboard)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.lockVault)
        self._show_gate()

    # ── properties ──

    def _touch(self):
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def screen(self) -> str:
        return self._screen

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=stateChanged)
    def notice(self) -> str:
        return self._notice

    @Property(str, notify=stateChanged)
    def noticeLevel(self) -> str:
        return self._notice_level

    @Property(str, notify=stateChanged)
    def page(self) -> str:
        return self._page

    @Property(int, notify=stateChanged)
    def pageIndex(self) -> int:
        try:
            return _PAGES.index(self._page)
        except ValueError:
            return 0

    @Property(str, notify=stateChanged)
    def entryCountText(self) -> str:
        return self._count_text

    @Property(str, notify=stateChanged)
    def idleLabel(self) -> str:
        return self._idle_label

    @Property(str, notify=stateChanged)
    def idleMinutesValue(self) -> str:
        return self._idle_value

    @Property(str, notify=stateChanged)
    def vaultPath(self) -> str:
        return VAULT_FILE

    @Property(str, notify=stateChanged)
    def pathShort(self) -> str:
        return _ellipsis(VAULT_FILE, 28)

    @Property(str, notify=stateChanged)
    def footerLine(self) -> str:
        return f"{PLATFORM} · Python {sys.version.split()[0]} · DB: {VAULT_FILE}"

    @Property(bool, notify=stateChanged)
    def twoFaFile(self) -> bool:
        return totp_mod.tfa.enabled()

    @Property(bool, notify=stateChanged)
    def backupAvailable(self) -> bool:
        return vault_db.vault.backup_exists()

    @Property(bool, notify=stateChanged)
    def backupHasPassword(self) -> bool:
        return vault_db.vault.backup_has_master_check()

    @Property(bool, notify=stateChanged)
    def backupOk(self) -> bool:
        return self._backup_ok

    @Property(str, notify=stateChanged)
    def backupText(self) -> str:
        return self._backup_text

    @Property(bool, notify=stateChanged)
    def recoverySet(self) -> bool:
        return self._recovery_set

    @Property(bool, notify=stateChanged)
    def unlockCodesOn(self) -> bool:
        return self._unlock_codes_on

    @Property(int, notify=stateChanged)
    def unlockCodesLeft(self) -> int:
        return self._unlock_codes_left

    @Property(bool, notify=stateChanged)
    def twoFaOn(self) -> bool:
        return self._two_fa_on

    @Property(int, notify=stateChanged)
    def twoFaRemaining(self) -> int:
        return self._two_fa_remaining

    @Property(bool, notify=stateChanged)
    def twoFaCodesOn(self) -> bool:
        return self._two_fa_codes

    @Property(str, notify=stateChanged)
    def masterMessage(self) -> str:
        return self._master_msg

    @Property(str, notify=stateChanged)
    def masterLevel(self) -> str:
        return self._master_level

    @Property(str, notify=stateChanged)
    def recoveryMessage(self) -> str:
        return self._recovery_msg

    @Property(str, notify=stateChanged)
    def recoveryLevel(self) -> str:
        return self._recovery_level

    @Property(str, notify=stateChanged)
    def idleMessage(self) -> str:
        return self._idle_msg

    @Property(str, notify=stateChanged)
    def idleLevel(self) -> str:
        return self._idle_level

    @Property(str, notify=stateChanged)
    def exportMessage(self) -> str:
        return self._export_msg

    @Property(str, notify=stateChanged)
    def exportLevel(self) -> str:
        return self._export_level

    @Property("QVariantList", notify=entriesChanged)
    def entries(self):
        return self._entries

    @Property("QVariantList", notify=qrChanged)
    def qrRows(self):
        return self._qr_rows

    @Property(bool, notify=stateChanged)
    def setupOpen(self) -> bool:
        return self._setup_open

    @Property(int, notify=stateChanged)
    def setupPage(self) -> int:
        return self._setup_page

    @Property(str, notify=stateChanged)
    def setupSecret(self) -> str:
        return self._setup_secret

    @Property("QVariantList", notify=stateChanged)
    def setupCodes(self):
        return self._setup_codes

    @Property(str, notify=stateChanged)
    def setupError(self) -> str:
        return self._setup_error

    @Property(bool, notify=stateChanged)
    def transferOpen(self) -> bool:
        return self._transfer_open

    @Property(str, notify=stateChanged)
    def transferSecret(self) -> str:
        return self._transfer_secret

    @Property(bool, notify=stateChanged)
    def codesOpen(self) -> bool:
        return self._codes_open

    @Property("QVariantList", notify=stateChanged)
    def issuedCodes(self):
        return self._issued_codes

    @Property(bool, notify=stateChanged)
    def codesRegenerated(self) -> bool:
        return self._codes_regenerated

    @Property(bool, notify=stateChanged)
    def codeActionOpen(self) -> bool:
        return self._code_action_open

    @Property(str, notify=stateChanged)
    def codeActionTitle(self) -> str:
        return self._code_title

    @Property(str, notify=stateChanged)
    def codeActionBody(self) -> str:
        return self._code_body

    @Property(str, notify=stateChanged)
    def codeActionButton(self) -> str:
        return self._code_button

    @Property(bool, notify=stateChanged)
    def codeActionDanger(self) -> bool:
        return self._code_danger

    @Property(str, notify=stateChanged)
    def codeActionError(self) -> str:
        return self._code_error

    @Property(bool, notify=stateChanged)
    def disableOpen(self) -> bool:
        return self._disable_open

    @Property(str, notify=stateChanged)
    def disableError(self) -> str:
        return self._disable_error

    @Property(int, notify=stateChanged)
    def wordlistSize(self) -> int:
        return len(self._words)

    @Property("QVariantList", notify=stateChanged)
    def securityRows(self):
        on = bool((totp_mod.tfa._data or {}).get("setup_complete"))
        status = "ON — RFC 6238 TOTP" if on else "OFF"
        rows = [
            ("Storage", "SQLite + WAL", "Consistent backup via the SQLite backup API"),
            ("Entries", "AES-256-GCM", "Title, username, URL, notes, password, TOTP"),
            ("Data key", "Random DEK", "Wrapped by the master and optional recovery passphrase"),
            ("KDF", "Argon2id", "Used for passphrases only, not for each field"),
            ("Field nonce", "96-bit", "Unique per field; column name is authenticated"),
            ("Memory", "64 MiB", "Argon2id cost for master, recovery, export, and files"),
            ("App 2FA", status, "TOTP secret in localpasswordvault.2fa"),
            ("Recovery", "Separate passphrase", "Unlocks the same DEK and forces a new master"),
            ("Clipboard", "30 seconds", "Cleared on lock if it still holds the copied secret"),
            ("Platform", PLATFORM, f"Python {sys.version.split()[0]}"),
        ]
        return [{"name": name, "value": value, "detail": detail} for name, value, detail in rows]

    # ── threading and clipboard ──

    def _run(self, fn, on_ok, on_err):
        if self._busy:
            return
        self._busy = True
        self._touch()
        runner = _Runner(fn)
        self._runner = runner

        def finish_ok(payload):
            self._busy = False
            self._touch()
            on_ok(payload.get("value") if isinstance(payload, dict) else payload)

        def finish_err(message):
            self._busy = False
            self._touch()
            on_err(message)

        runner.done.connect(finish_ok)
        runner.failed.connect(finish_err)
        runner.start()

    def _set_notice(self, text: str, level: str = "muted"):
        self._notice = text
        self._notice_level = level
        self._touch()

    def _ask(self, ask_id: str, title: str, body: str):
        self._ask_id = ask_id
        self.confirmRequested.emit(ask_id, title, body)

    @Slot(str, bool)
    def answerConfirm(self, ask_id: str, yes: bool):
        if ask_id != self._ask_id:
            return
        self._ask_id = ""
        if ask_id == "create_no_recovery":
            master = self._pending_master
            self._pending_master = ""
            if yes and master:
                self._start_create(master, None)
            return
        if ask_id == "restore_corrupt":
            if yes:
                self._restore_corrupt()
            return
        if ask_id == "reset_damaged":
            if yes:
                vault_db.vault.reset_vault_files()
                self._show_gate()
            return
        if ask_id == "delete":
            eid = self._pending_delete
            self._pending_delete = ""
            if yes and eid:
                vault_db.vault.delete_entry(eid)
                self._publish_entries()
                self._refresh_status()
                self._touch()
            return
        if ask_id == "import":
            if yes:
                self._apply_import()
            else:
                vault_db.vault.clear_staged_export()
                self._import_path = ""
                self._import_pp = ""
                self._export_msg = "Import cancelled."
                self._export_level = "muted"
                self._touch()
            return
        if ask_id == "lock" and yes:
            self.lockVault()

    @Slot(str, result=bool)
    def copyText(self, text: str) -> bool:
        if not text:
            return False
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
        except Exception:
            return False
        self._clip = text
        self._clip_timer.start(CLIPBOARD_CLEAR_MS)
        return True

    def _clear_clipboard(self):
        self._clip_timer.stop()
        secret = self._clip
        self._clip = ""
        if not secret:
            return
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard.text() == secret:
                clipboard.clear()
        except Exception:
            pass

    @Slot()
    def noteActivity(self):
        now = time.monotonic()
        if now - self._last_activity < 1.0:
            return
        self._last_activity = now
        if self._screen == "main":
            self._arm_idle()

    def _arm_idle(self):
        self._idle_timer.stop()
        if self._screen != "main" or not vault_db.vault.unlocked:
            return
        minutes = vault_db.vault.get_idle_lock_minutes()
        if minutes <= 0:
            return
        self._idle_timer.start(minutes * 60_000)

    def _show_gate(self):
        vault = vault_db.vault
        if vault.vault_exists() and not vault.has_master_check():
            self._screen = "corrupt"
        elif vault.vault_exists():
            self._screen = "unlock"
        else:
            self._screen = "create"
        self._notice = ""
        self._notice_level = "muted"
        self._refresh_backup()
        self._touch()

    def _enter_main(self):
        if vault_db.vault.unlocked_via_recovery:
            self._screen = "reset_master"
            self._notice = ""
            self._touch()
            return
        self._verified_pw = ""
        self._screen = "main"
        self._page = "Vault"
        self._notice = ""
        self._publish_entries()
        self._refresh_status()
        self._refresh_twofa()
        self._touch()
        self._arm_idle()
        if self._low_codes_pending:
            self._low_codes_pending = False
            remaining = totp_mod.tfa.recovery_codes_remaining()
            if 0 < remaining <= 3:
                self.alertRequested.emit(
                    "Low Recovery Codes",
                    f"Only {remaining} recovery code(s) remaining.\n\n"
                    "Go to Settings → 2FA to regenerate your codes.",
                )
            elif remaining == 0:
                self.alertRequested.emit(
                    "No Recovery Codes Left",
                    "You have used all recovery codes.\n\n"
                    "Go to Settings → 2FA → Regenerate Codes immediately.",
                )

    def _publish_entries(self):
        vault = vault_db.vault
        if not vault.unlocked:
            self._entries = []
            self.entriesChanged.emit()
            return
        rows = []
        for eid, entry in vault.all_entries().items():
            password = entry.get("password") or ""
            _score, label, color = pw_strength(password) if password else (0, "", "")
            url = entry.get("url") or ""
            created = int(entry.get("created") or 0)
            updated = int(entry.get("updated") or created or 0)
            rows.append({
                "id": eid,
                "title": entry.get("title") or "",
                "username": entry.get("username") or "",
                "password": password,
                "url": url,
                "urlSafe": url.strip().lower().startswith(("https://", "http://")),
                "notes": entry.get("notes") or "",
                "totp_secret": entry.get("totp_secret") or "",
                "decrypt_error": bool(entry.get("decrypt_error")),
                "createdLabel": time.strftime("%Y-%m-%d %H:%M", time.localtime(created)) if created else "",
                "updatedLabel": time.strftime("%Y-%m-%d %H:%M", time.localtime(updated)) if updated else "",
                "strengthLabel": label,
                "strengthColor": color,
            })
        self._entries = rows
        self.entriesChanged.emit()

    def _refresh_backup(self):
        exists = vault_db.vault.backup_exists()
        self._backup_ok = exists
        self._backup_text = (
            f"Backup exists: {BAK_FILE}" if exists else f"No backup yet: {BAK_FILE}"
        )

    def _refresh_status(self):
        vault = vault_db.vault
        count = vault.entry_count() if vault.unlocked else 0
        self._count_text = f"{count} entry" if count == 1 else f"{count} entries"
        minutes = vault.get_idle_lock_minutes() if vault.unlocked else 0
        self._idle_value = str(minutes if vault.unlocked else vault.get_idle_lock_minutes())
        self._idle_label = f"Auto-lock {minutes}m" if minutes > 0 else "Auto-lock off"
        self._recovery_set = bool(vault.unlocked and vault.has_recovery())
        self._refresh_backup()

    def _refresh_twofa(self):
        data = totp_mod.tfa._data or {}
        self._two_fa_on = bool(data.get("setup_complete"))
        self._two_fa_remaining = totp_mod.tfa.recovery_codes_remaining() if self._two_fa_on else 0
        self._two_fa_codes = bool(totp_mod.tfa.codes_enabled()) if self._two_fa_on else False

    def _set_qr(self, data: str):
        try:
            self._qr_rows = _qr_rows(data)
        except Exception:
            self._qr_rows = []
        self.qrChanged.emit()

    def _clear_qr(self):
        self._qr_rows = []
        self.qrChanged.emit()

    # ── unlock ──

    @Slot(str)
    def submitUnlock(self, password: str):
        if self._busy:
            return
        if not password:
            self._set_notice("Password required.", "danger")
            return
        self._verified_pw = password
        self._set_notice("Verifying… (Argon2id)", "muted")

        def work():
            kind = vault_db.vault.begin_unlock(password)
            if not kind:
                return "fail"
            if kind == "recovery":
                return "recovery"
            if totp_mod.tfa.enabled():
                if totp_mod.tfa.load(password):
                    return "2fa"
                totp_mod.tfa.unload()
                vault_db.vault.abort_unlock()
                return "fail"
            return "ok"

        self._run(work, self._on_unlock_result, lambda _message: self._on_unlock_result("error"))

    def _on_unlock_result(self, kind):
        if kind in ("fail", "error", "", None):
            self._verified_pw = ""
            if kind != "error" and not vault_db.vault.has_master_check() and vault_db.vault.vault_exists():
                self._screen = "corrupt"
                self._notice = ""
                self._touch()
                return
            if kind == "error":
                self._set_notice("Could not open the vault.", "danger")
            else:
                self._set_notice("Wrong password. Neither master nor recovery matched.", "danger")
            return
        if kind == "2fa":
            self._screen = "totp"
            self._notice = ""
            self._touch()
            return
        if kind == "recovery":
            if not vault_db.vault.finish_unlock():
                self._set_notice(
                    "Recovery unlock failed.\nLegacy vaults may need a one-time master unlock first.",
                    "danger",
                )
                return
            self._screen = "reset_master"
            self._notice = ""
            self._touch()
            return
        if not vault_db.vault.finish_unlock():
            self._set_notice("Could not open vault. Try again.", "danger")
            return
        self._enter_main()

    @Slot()
    def showRecoveryCodeStep(self):
        self._unlock_codes_on = totp_mod.tfa.codes_enabled()
        self._unlock_codes_left = totp_mod.tfa.recovery_codes_remaining()
        self._screen = "recovery_code"
        self._notice = ""
        self._touch()

    @Slot()
    def showTotpStep(self):
        self._screen = "totp"
        self._notice = ""
        self._touch()

    @Slot()
    def backToPassword(self):
        vault_db.vault.abort_unlock()
        self._screen = "unlock"
        self._notice = ""
        self._touch()

    @Slot(str)
    def submitTotp(self, code: str):
        code = (code or "").strip().replace(" ", "")
        if not code:
            self._set_notice("Enter the 6-digit code.", "danger")
            return
        if not totp_mod.tfa.verify_totp(code):
            self._set_notice("Incorrect code. Try again or use a recovery code.", "danger")
            return
        self._finish_second_factor()

    @Slot(str)
    def submitRecoveryCode(self, code: str):
        if self._busy:
            return
        code = (code or "").strip()
        if not code:
            self._set_notice("Enter your recovery code.", "danger")
            return
        password = self._verified_pw

        def work():
            return bool(totp_mod.tfa.verify_recovery_code(code, password))

        def ok(success):
            if success:
                self._finish_second_factor()
            else:
                self._set_notice("Invalid or already-used recovery code.", "danger")

        self._run(work, ok, lambda _message: self._set_notice("Invalid or already-used recovery code.", "danger"))

    def _finish_second_factor(self):
        if not vault_db.vault.finish_unlock():
            self._set_notice("Could not unlock vault.", "danger")
            return
        self._low_codes_pending = True
        self._enter_main()

    @Slot(str, str)
    def submitNewMaster(self, password: str, confirm: str):
        if self._busy:
            return
        if not password:
            self._set_notice("New master password required.", "danger")
            return
        if password != confirm:
            self._set_notice("Passwords do not match.", "danger")
            return
        score, label, _color = pw_strength(password)
        if score < 40:
            self._set_notice(f"Password too weak ({label}). Use 12+ mixed characters.", "danger")
            return
        self._set_notice("Saving new master…", "muted")

        def work():
            return bool(vault_db.vault.reset_master_after_recovery(password))

        def ok(success):
            if not success:
                self._set_notice("Could not set new master.", "danger")
                return
            self._enter_main()

        self._run(work, ok, lambda _message: self._set_notice("Could not set new master.", "danger"))

    @Slot(str, str, str, str)
    def submitCreate(self, password: str, confirm: str, recovery: str, recovery_confirm: str):
        if self._busy:
            return
        if not password:
            self._set_notice("Master password required.", "danger")
            return
        if password != confirm:
            self._set_notice("Master passwords do not match.", "danger")
            return
        score, label, _color = pw_strength(password)
        if score < 40:
            self._set_notice(f"Password too weak ({label}). Use 12+ mixed characters.", "danger")
            return
        if recovery and recovery != recovery_confirm:
            self._set_notice("Recovery passphrases do not match.", "danger")
            return
        if not recovery:
            self._pending_master = password
            self._ask(
                "create_no_recovery",
                "No recovery passphrase",
                "You haven't set a recovery passphrase.\n\n"
                "If you forget your master password, the vault CANNOT be recovered.\n\n"
                "Continue without a recovery passphrase?",
            )
            return
        self._start_create(password, recovery)

    def _start_create(self, password: str, recovery):
        self._set_notice("Creating vault… (Argon2id)", "muted")

        def work():
            return bool(vault_db.vault.create(password, recovery))

        def ok(success):
            if not success:
                self._set_notice("Could not create vault.", "danger")
                return
            if not vault_db.vault.unlocked:
                self._set_notice("Vault created but could not open.", "danger")
                return
            self._enter_main()

        self._run(work, ok, lambda _message: self._set_notice("Could not create vault.", "danger"))

    @Slot()
    def requestRestoreCorrupt(self):
        self._ask(
            "restore_corrupt",
            "Restore backup",
            "Replace the damaged vault with the backup file?\n\n"
            "You will need the password that was used when that backup was made.",
        )

    def _restore_corrupt(self):
        def work():
            return bool(vault_db.vault.copy_backup_over_vault())

        def ok(copied):
            if copied and vault_db.vault.has_master_check():
                self.alertRequested.emit("Restored", "Backup restored. Enter your password to unlock.")
                self._screen = "unlock"
                self._notice = ""
                self._touch()
            elif copied:
                self.alertRequested.emit("Failed", "Backup restored but still has no password set.")
            else:
                self.alertRequested.emit("Failed", "Could not restore backup.")

        self._run(work, ok, lambda _message: self.alertRequested.emit("Failed", "Could not restore backup."))

    @Slot()
    def requestResetDamaged(self):
        self._ask(
            "reset_damaged",
            "Create new vault",
            "Delete the damaged vault file and set up a new one?\n\n"
            "The current file has no saved entries, so nothing will be lost.",
        )

    @Slot(str)
    def restoreBackup(self, password: str):
        if self._busy:
            return
        if not password:
            self._set_notice("Enter password first, then restore.", "danger")
            return
        self._verified_pw = password
        self._set_notice("Restoring from backup…", "muted")

        def work():
            return bool(vault_db.vault.copy_backup_over_vault())

        def ok(copied):
            if not copied:
                self._set_notice("Backup restore failed.", "danger")
                return
            vault_db.vault.lock()
            self._unlock_restored(password)

        self._run(work, ok, lambda _message: self._set_notice("Backup restore failed.", "danger"))

    def _unlock_restored(self, password: str):
        def work():
            return vault_db.vault.begin_unlock(password) or ""

        def ok(kind):
            if not kind or not vault_db.vault.finish_unlock():
                self._set_notice("Restored, but unlock failed.", "danger")
                return
            if vault_db.vault.unlocked_via_recovery:
                self._screen = "reset_master"
                self._notice = ""
                self._touch()
                return
            self._enter_main()

        self._run(work, ok, lambda _message: self._set_notice("Restored, but unlock failed.", "danger"))

    # ── shell ──

    @Slot()
    def lockVault(self):
        self._idle_timer.stop()
        self._clear_clipboard()
        self._verified_pw = ""
        self._draft_password = ""
        self._pending_master = ""
        self._pending_delete = ""
        self._import_pp = ""
        self._setup_open = False
        self._setup_codes = []
        self._setup_secret = ""
        self._transfer_open = False
        self._transfer_secret = ""
        self._codes_open = False
        self._issued_codes = []
        self._code_action_open = False
        self._disable_open = False
        self._clear_qr()
        vault_db.vault.lock()
        totp_mod.tfa.unload()
        self._entries = []
        self.entriesChanged.emit()
        self._page = "Vault"
        self._two_fa_on = False
        self._show_gate()

    @Slot()
    def requestLockConfirm(self):
        self._ask(
            "lock",
            "Lock Vault",
            "This clears the master password from memory.\nContinue?",
        )

    @Slot(str)
    def setPage(self, name: str):
        if name in _PAGES and name != self._page:
            self._page = name
            self._touch()

    @Slot()
    def focusSearch(self):
        if self._screen != "main":
            return
        self._page = "Vault"
        self._touch()
        self.searchFocusRequested.emit()

    @Slot()
    def newEntry(self):
        if self._screen != "main" or not vault_db.vault.unlocked:
            return
        self._page = "Vault"
        self._touch()
        self.entryDialogRequested.emit("")

    @Slot(str)
    def editEntry(self, eid: str):
        if eid:
            self.entryDialogRequested.emit(eid)

    @Slot(str)
    def setTheme(self, mode: str):
        if self._palette is not None:
            self._palette.set_mode(mode)
            return
        from config import get_theme, save_theme
        mode = "dark" if str(mode).lower().startswith("d") else "light"
        if mode != get_theme():
            save_theme(mode)

    @Slot(str, result=str)
    def localPath(self, url: str) -> str:
        if not url:
            return ""
        parsed = QUrl(url)
        if parsed.isLocalFile():
            return parsed.toLocalFile()
        return url

    @Slot(str)
    def openUrl(self, url: str):
        target = (url or "").strip()
        lower = target.lower()
        if lower.startswith("https://") or lower.startswith("http://"):
            QDesktopServices.openUrl(QUrl(target))

    @Slot(str, result="QVariant")
    def strength(self, password: str):
        score, label, color = pw_strength(password or "")
        return {"score": int(score), "label": label if password else "", "color": color}

    @Slot(str, result="QVariant")
    def totpInfo(self, secret: str):
        if not secret:
            return {"ok": False, "display": "", "raw": "", "remaining": 0, "progress": 0.0}
        try:
            code, remaining, progress = _totp_code(secret)
        except Exception:
            return {"ok": False, "display": "Invalid", "raw": "", "remaining": 0, "progress": 0.0}
        return {
            "ok": True,
            "display": f"{code[:3]} {code[3:]}",
            "raw": code,
            "remaining": int(remaining),
            "progress": float(progress),
        }

    @Slot(str, result="QVariant")
    def totpStatus(self, secret: str):
        secret = (secret or "").strip()
        if not secret:
            return {"text": "", "color": ""}
        if _totp_valid(secret):
            try:
                code, remaining, _progress = _totp_code(secret)
            except Exception:
                return {"text": "Invalid secret — base32 (A-Z, 2-7), at least 16 characters", "color": "#DC2626"}
            return {
                "text": f"Valid — current code {code[:3]} {code[3:]} ({remaining}s)",
                "color": "#059669",
            }
        return {"text": "Invalid secret — base32 (A-Z, 2-7), at least 16 characters", "color": "#DC2626"}

    @Slot(str, result="QVariant")
    def entry(self, eid: str):
        for row in self._entries:
            if row.get("id") == eid:
                return row
        return {}

    @Slot(str)
    def requestDelete(self, eid: str):
        if not eid:
            return
        title = "this entry"
        for row in self._entries:
            if row.get("id") == eid:
                title = row.get("title") or "this entry"
                break
        self._pending_delete = eid
        self._ask("delete", "Delete", f"Delete '{title}'? This cannot be undone.")

    @Slot(str, str, str, str, str, str, str, result=str)
    def saveEntry(self, eid, title, username, password, url, notes, totp_secret) -> str:
        title = (title or "").strip()
        password = password or ""
        if not title or not password:
            return "Title and password are required."
        secret = (totp_secret or "").strip().upper().replace(" ", "")
        if secret and not _totp_valid(secret):
            return "The TOTP secret is not valid base32. Copy it exactly from the site setup page."
        try:
            if eid:
                vault_db.vault.update_entry(
                    eid, title=title, username=username or "", password=password,
                    url=(url or "").strip(), notes=(notes or "").strip(), totp_secret=secret,
                )
            else:
                vault_db.vault.add_entry(
                    title, username or "", password, (url or "").strip(), (notes or "").strip(), secret,
                )
        except Exception:
            return "Could not save the entry."
        self._publish_entries()
        self._refresh_status()
        self._touch()
        return ""

    @Slot(result=str)
    def takeDraftPassword(self) -> str:
        password = self._draft_password
        self._draft_password = ""
        return password

    @Slot(str)
    def saveGeneratedToVault(self, password: str):
        if not password or not vault_db.vault.unlocked:
            return
        self._draft_password = password
        self._page = "Vault"
        self._touch()
        self.entryDialogRequested.emit("")

    # ── encrypt and generate ──

    @Slot(str, str, bool)
    def encryptText(self, passphrase: str, text: str, encrypting: bool):
        if self._busy:
            return
        text = (text or "").strip()
        if not passphrase or not text:
            self.alertRequested.emit("Missing", "Provide a passphrase and input.")
            return

        def work():
            return _encrypt(text, passphrase) if encrypting else _decrypt(text, passphrase)

        def ok(result):
            self.textReady.emit(result or "")

        def err(_message):
            self.alertRequested.emit(
                "Failed",
                "Could not encrypt." if encrypting else "Could not decrypt. Check the passphrase and token.",
            )

        self._run(work, ok, err)

    @Slot(str, str, str, bool)
    def encryptFile(self, passphrase: str, source: str, dest: str, encrypting: bool):
        if self._busy:
            return
        source = (source or "").strip()
        dest = (dest or "").strip()
        if not (passphrase and source and dest):
            self.alertRequested.emit("Missing", "Provide a passphrase, input file, and output file.")
            return

        def work():
            if encrypting:
                encrypt_file(source, dest, passphrase)
            else:
                decrypt_file(source, dest, passphrase)
            return dest

        def ok(path):
            verb = "Encrypted" if encrypting else "Decrypted"
            self.alertRequested.emit("Done", f"{verb} to:\n{path}")

        def err(message):
            if "different files" in (message or ""):
                self.alertRequested.emit("Failed", "Choose a different output file from the input.")
                return
            self.alertRequested.emit(
                "Failed",
                "Could not encrypt the file." if encrypting
                else "Could not decrypt the file. Check the passphrase and that the file is intact.",
            )

        self._run(work, ok, err)

    @Slot(int, bool, bool, bool, bool, bool, result=str)
    def generatePassword(self, length, upper, lower, digits, symbols, no_ambiguous) -> str:
        return gen_password(
            int(length), bool(upper), bool(lower), bool(digits), bool(symbols), bool(no_ambiguous),
        )

    @Slot(int, result="QVariant")
    def generatePassphrase(self, count):
        words = max(1, int(count))
        phrase = "-".join(secrets.choice(self._words) for _ in range(words))
        bits = passphrase_entropy_bits(words, len(self._words))
        return {
            "phrase": phrase,
            "bitsText": f"About {bits:.0f} bits if the words are chosen uniformly from this list.",
        }

    # ── settings ──

    @Slot(str, str, str)
    def changeMaster(self, old: str, new: str, confirm: str):
        if self._busy:
            return
        if new != confirm:
            self._master_msg = "New passwords do not match."
            self._master_level = "danger"
            self._touch()
            return
        score, label, _color = pw_strength(new)
        if score < 40:
            self._master_msg = f"Password too weak ({label})."
            self._master_level = "danger"
            self._touch()
            return
        self._master_msg = "Updating master key wrap…"
        self._master_level = "muted"
        self._touch()

        def work():
            return bool(vault_db.vault.change_master(old, new))

        def ok(success):
            if success:
                self._master_msg = "Master password changed."
                self._master_level = "success"
                self.clearFields.emit("master")
                self._arm_idle()
            else:
                self._master_msg = "Current password incorrect."
                self._master_level = "danger"
            self._touch()

        self._run(work, ok, lambda _message: self._fail_master())

    def _fail_master(self):
        self._master_msg = "Current password incorrect."
        self._master_level = "danger"
        self._touch()

    @Slot(str, str, str)
    def changeRecovery(self, master: str, new: str, confirm: str):
        if self._busy:
            return
        if not master or not new:
            self._recovery_msg = "Master password and new recovery passphrase required."
            self._recovery_level = "danger"
            self._touch()
            return
        if new != confirm:
            self._recovery_msg = "Recovery passphrases do not match."
            self._recovery_level = "danger"
            self._touch()
            return

        def work():
            return bool(vault_db.vault.change_recovery(master, new))

        def ok(success):
            if success:
                self._recovery_msg = "Recovery passphrase updated."
                self._recovery_level = "success"
                self._recovery_set = vault_db.vault.has_recovery()
                self.clearFields.emit("recovery")
            else:
                self._recovery_msg = "Master password incorrect."
                self._recovery_level = "danger"
            self._touch()

        self._run(work, ok, lambda _message: self._fail_recovery())

    def _fail_recovery(self):
        self._recovery_msg = "Master password incorrect."
        self._recovery_level = "danger"
        self._touch()

    @Slot(str)
    def setIdleMinutes(self, raw: str):
        text = (raw or "").strip()
        try:
            minutes = int(text)
        except ValueError:
            self._idle_msg = "Enter a whole number of minutes."
            self._idle_level = "danger"
            self._touch()
            return
        if minutes < 0:
            self._idle_msg = "Minutes cannot be negative."
            self._idle_level = "danger"
            self._touch()
            return
        try:
            vault_db.vault.set_idle_lock_minutes(minutes)
        except RuntimeError as exc:
            self._idle_msg = str(exc)
            self._idle_level = "danger"
            self._touch()
            return
        self._idle_msg = (
            "Auto-lock disabled." if minutes == 0 else f"Auto-lock set to {minutes} minute(s)."
        )
        self._idle_level = "success"
        self._refresh_status()
        self._arm_idle()
        self._touch()

    @Slot(str, str, str)
    def exportVault(self, path: str, passphrase: str, confirm: str):
        if self._busy:
            return
        if not passphrase:
            self._export_msg = "Export passphrase required."
            self._export_level = "danger"
            self._touch()
            return
        if passphrase != confirm:
            self._export_msg = "Passphrases do not match."
            self._export_level = "danger"
            self._touch()
            return
        if not path:
            return
        self._export_msg = "Encrypting export…"
        self._export_level = "muted"
        self._touch()

        def work():
            vault_db.vault.export_encrypted_json(path, passphrase)
            return vault_db.vault.entry_count()

        def ok(count):
            self._export_msg = f"Exported {count} entries → {path}"
            self._export_level = "success"
            self._touch()

        def err(_message):
            self._export_msg = "Export failed."
            self._export_level = "danger"
            self._touch()

        self._run(work, ok, err)

    @Slot(str, str)
    def importVault(self, path: str, passphrase: str):
        if self._busy:
            return
        if not passphrase:
            self._export_msg = "Enter the export passphrase first."
            self._export_level = "danger"
            self._touch()
            return
        if not path:
            return
        self._import_path = path
        self._import_pp = passphrase
        self._export_msg = "Reading export…"
        self._export_level = "muted"
        self._touch()

        def work():
            return vault_db.vault.summarize_export(path, passphrase)

        def ok(info):
            count = int((info or {}).get("count") or 0)
            noun = "entry" if count == 1 else "entries"
            self._ask(
                "import",
                "Import entries",
                f"This file contains {count} {noun}.\n\n"
                "Matching entries will be updated. New ones will be added.",
            )

        def err(_message):
            vault_db.vault.clear_staged_export()
            self._import_path = ""
            self._import_pp = ""
            self._export_msg = "Could not read that export. Check the passphrase and file."
            self._export_level = "danger"
            self._touch()

        self._run(work, ok, err)

    def _apply_import(self):
        path, passphrase = self._import_path, self._import_pp
        self._export_msg = "Importing…"
        self._export_level = "muted"
        self._touch()

        def work():
            return vault_db.vault.import_encrypted_json(path, passphrase)

        def ok(count):
            self._import_path = ""
            self._import_pp = ""
            self._export_msg = f"Imported {count} entries."
            self._export_level = "success"
            self._publish_entries()
            self._refresh_status()
            self._touch()

        def err(_message):
            self._import_pp = ""
            self._export_msg = "Import failed. Check the passphrase and file."
            self._export_level = "danger"
            self._touch()

        self._run(work, ok, err)

    # ── 2FA ──

    @Slot()
    def startSetup(self):
        secret, codes, uri = totp_mod.tfa.begin_setup()
        self._setup_secret = _pad_b32(secret)
        self._setup_codes = list(codes)
        self._setup_page = 0
        self._setup_error = ""
        self._setup_open = True
        self._set_qr(uri)
        self._touch()

    @Slot()
    def cancelSetup(self):
        if not self._setup_open or self._busy:
            return
        totp_mod.tfa.cancel_setup()
        self._setup_open = False
        self._setup_codes = []
        self._setup_secret = ""
        self._clear_qr()
        self._refresh_twofa()
        self._touch()

    @Slot()
    def setupAdvance(self):
        if self._setup_page < 1:
            self._setup_page += 1
            self._setup_error = ""
            self._touch()

    @Slot()
    def setupBack(self):
        if self._setup_page > 0:
            self._setup_page -= 1
            self._setup_error = ""
            self._touch()

    @Slot(str)
    def verifySetup(self, code: str):
        code = (code or "").strip().replace(" ", "")
        if totp_mod.tfa.verify_totp(code):
            self._setup_page = 2
            self._setup_error = ""
        else:
            self._setup_error = "Code incorrect. Make sure your phone's clock is accurate."
        self._touch()

    @Slot(bool)
    def finishSetup(self, confirmed: bool):
        if self._busy:
            return
        if not confirmed:
            self._setup_error = "Please confirm you have saved the recovery codes."
            self._touch()
            return
        master = vault_db.vault._master or ""

        def work():
            return bool(totp_mod.tfa.commit_setup(master))

        def ok(success):
            if not success:
                totp_mod.tfa.cancel_setup()
                self._setup_open = False
                self._setup_codes = []
                self._setup_secret = ""
                self._clear_qr()
                self._setup_error = "Could not save 2FA settings. Please try again."
                self._touch()
                return
            self._setup_open = False
            self._setup_codes = []
            self._setup_secret = ""
            self._clear_qr()
            self._refresh_twofa()
            self._touch()

        self._run(work, ok, lambda _message: self._setup_failed())

    def _setup_failed(self):
        totp_mod.tfa.cancel_setup()
        self._setup_open = False
        self._setup_codes = []
        self._clear_qr()
        self._setup_error = "Could not save 2FA settings. Please try again."
        self._touch()

    @Slot()
    def showTransfer(self):
        uri = totp_mod.tfa.get_transfer_uri()
        secret = totp_mod.tfa.get_secret()
        if not uri or not secret:
            self.alertRequested.emit("Error", "2FA not loaded. Please unlock again.")
            return
        self._transfer_secret = _pad_b32(secret)
        self._transfer_open = True
        self._set_qr(uri)
        self._touch()

    @Slot()
    def closeTransfer(self):
        self._transfer_open = False
        self._transfer_secret = ""
        if not self._setup_open:
            self._clear_qr()
        self._touch()

    @Slot(str)
    def startCodeAction(self, kind: str):
        meta = {
            "regen": (
                "Regenerate Recovery Codes",
                "Enter your Authenticator code to regenerate all 10 recovery codes.\n"
                "All existing codes will be invalidated immediately.",
                "Regenerate",
                False,
            ),
            "disable_codes": (
                "Disable Recovery Codes",
                "Enter your Authenticator code to disable recovery codes.\n"
                "You will not be able to recover access if you lose your phone.",
                "Disable Codes",
                True,
            ),
            "enable_codes": (
                "Enable Recovery Codes",
                "Enter your Authenticator code to generate new recovery codes.",
                "Enable & Generate",
                False,
            ),
        }.get(kind)
        if not meta:
            return
        self._code_kind = kind
        self._code_title, self._code_body, self._code_button, self._code_danger = meta
        self._code_error = ""
        self._code_action_open = True
        self._touch()

    @Slot()
    def closeCodeAction(self):
        self._code_action_open = False
        self._code_error = ""
        self._touch()

    @Slot(str)
    def submitCodeAction(self, code: str):
        if self._busy:
            return
        code = (code or "").strip().replace(" ", "")
        if not code:
            self._code_error = "Enter the 6-digit code."
            self._touch()
            return
        kind = self._code_kind
        master = vault_db.vault._master or ""

        def work():
            manager = totp_mod.tfa
            if kind == "regen":
                return ("codes", manager.regenerate_recovery_codes(master, code), True)
            if kind == "enable_codes":
                return ("codes", manager.enable_recovery_codes(master, code), False)
            if kind == "disable_codes":
                return ("bool", manager.disable_recovery_codes(master, code), False)
            return ("bad", None, False)

        def ok(result):
            mode, payload, regenerated = result
            if mode == "bool" and payload:
                self._code_action_open = False
                self._refresh_twofa()
            elif mode == "codes" and payload:
                self._code_action_open = False
                self._issued_codes = list(payload)
                self._codes_regenerated = bool(regenerated)
                self._codes_open = True
                self._refresh_twofa()
            else:
                self._code_error = "Incorrect authenticator code. Try again."
            self._touch()

        self._run(work, ok, lambda _message: self._code_action_failed())

    def _code_action_failed(self):
        self._code_error = "Incorrect authenticator code. Try again."
        self._touch()

    @Slot()
    def closeIssuedCodes(self):
        self._codes_open = False
        self._issued_codes = []
        self._touch()

    @Slot(result=str)
    def issuedCodesText(self) -> str:
        return "\n".join(f"{i + 1}. {code}" for i, code in enumerate(self._issued_codes))

    @Slot(result=str)
    def setupCodesText(self) -> str:
        return "\n".join(f"{i + 1}. {code}" for i, code in enumerate(self._setup_codes))

    @Slot()
    def openDisable2fa(self):
        self._disable_error = ""
        self._disable_open = True
        self._touch()

    @Slot()
    def closeDisable2fa(self):
        self._disable_open = False
        self._disable_error = ""
        self._touch()

    @Slot(str, str)
    def submitDisable2fa(self, code: str, word: str):
        code = (code or "").strip().replace(" ", "")
        if not code:
            self._disable_error = "Enter the Authenticator code."
            self._touch()
            return
        if (word or "").strip().upper() != "DISABLE":
            self._disable_error = "Type DISABLE (uppercase) to confirm."
            self._touch()
            return
        if totp_mod.tfa.disable_2fa(vault_db.vault._master or "", code, word):
            self._disable_open = False
            self._disable_error = ""
            self._refresh_twofa()
        else:
            self._disable_error = "Incorrect authenticator code."
        self._touch()
