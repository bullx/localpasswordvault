"""
SQLite-backed vault with field-level AES-256-GCM encryption.

Field ciphertext is encrypted with a random data encryption key (DEK).
The DEK is wrapped (encrypted) under the master password and, optionally,
under the recovery passphrase — so either can unlock without treating
recovery as the field key.
"""
import os, json, time, secrets, sqlite3, shutil

from config import VAULT_FILE, BAK_FILE
from crypto import _encrypt, _decrypt
from totp import tfa


class VaultDB:
    """
    Schema
    ──────
    meta
      master_check      — encrypt("OK", master)
      recovery_check    — encrypt("OK", recovery)          [optional]
      dek_wrap_master   — encrypt(dek, master)
      dek_wrap_recovery — encrypt(dek, recovery)           [optional]
    entries
      enc_password / enc_totp encrypted with DEK
    """

    def __init__(self):
        self._master       = None   # master password (for 2FA file); None during recovery until reset
        self._dek          = None   # data encryption key for entry fields
        self._unlocked     = False
        self._via_recovery = False
        self._db           = None

    # ── public state ──

    @property
    def unlocked(self): return self._unlocked

    @property
    def unlocked_via_recovery(self): return self._via_recovery

    def vault_exists(self): return os.path.exists(VAULT_FILE)

    def has_master_check(self) -> bool:
        if not self.vault_exists():
            return False
        conn = sqlite3.connect(VAULT_FILE, check_same_thread=False)
        try:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
            ).fetchone():
                return False
            row = conn.execute(
                "SELECT value FROM meta WHERE key='master_check'"
            ).fetchone()
            return bool(row and row[0])
        finally:
            conn.close()

    def backup_has_master_check(self) -> bool:
        if not os.path.exists(BAK_FILE):
            return False
        conn = sqlite3.connect(BAK_FILE, check_same_thread=False)
        try:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
            ).fetchone():
                return False
            row = conn.execute(
                "SELECT value FROM meta WHERE key='master_check'"
            ).fetchone()
            return bool(row and row[0])
        finally:
            conn.close()

    def reset_vault_files(self):
        self.lock()
        for path in (
            VAULT_FILE, BAK_FILE,
            VAULT_FILE + "-wal", VAULT_FILE + "-shm",
            VAULT_FILE + "-journal",
        ):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def verify_passphrase(self, passphrase: str) -> str | None:
        """
        Returns 'master', 'recovery', or None. Safe from a worker thread.
        """
        if not self.vault_exists():
            return None
        conn = sqlite3.connect(VAULT_FILE, check_same_thread=False)
        try:
            for col in ("master_check", "recovery_check"):
                row = conn.execute(
                    "SELECT value FROM meta WHERE key=?", (col,)).fetchone()
                if row:
                    try:
                        if _decrypt(row[0], passphrase) == "OK":
                            return "recovery" if col == "recovery_check" else "master"
                    except Exception:
                        pass
        finally:
            conn.close()
        return None

    def _meta_get(self, key: str, conn=None):
        db = conn or self._db
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _meta_set(self, key: str, value: str):
        self._db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    # ── open / create ──

    def create(self, master: str, recovery: str | None = None) -> bool:
        """Create a brand-new vault. recovery=None/empty skips recovery entirely."""
        if self.has_master_check():
            return False
        if self.vault_exists():
            self.reset_vault_files()
        self._connect()
        dek = secrets.token_urlsafe(32)
        recovery = recovery.strip() if recovery else None
        self._meta_set("master_check", _encrypt("OK", master))
        self._meta_set("dek_wrap_master", _encrypt(dek, master))
        if recovery:
            self._meta_set("recovery_check", _encrypt("OK", recovery))
            self._meta_set("dek_wrap_recovery", _encrypt(dek, recovery))
        self._db.commit()
        self._master       = master
        self._dek          = dek
        self._unlocked     = True
        self._via_recovery = False
        self._write_backup()
        return True

    def unlock(self, passphrase: str) -> bool:
        """Unlock with master OR recovery passphrase; load DEK for field crypto."""
        if not self.vault_exists():
            return False
        self._connect()
        self._via_recovery = False

        # Master path
        row = self._meta_get("master_check")
        if row:
            try:
                if _decrypt(row, passphrase) == "OK":
                    wrap = self._meta_get("dek_wrap_master")
                    if wrap:
                        self._dek = _decrypt(wrap, passphrase)
                    else:
                        # Legacy vault: fields encrypted with master — migrate to DEK
                        self._dek = self._migrate_legacy_to_dek(passphrase)
                    self._master       = passphrase
                    self._unlocked     = True
                    self._via_recovery = False
                    self._purge_no_recovery_sentinel()
                    return True
            except Exception:
                pass

        # Recovery path
        row = self._meta_get("recovery_check")
        if row:
            try:
                if _decrypt(row, passphrase) == "OK":
                    wrap = self._meta_get("dek_wrap_recovery")
                    if not wrap:
                        # Legacy vault without DEK wrap — cannot decrypt fields
                        return False
                    self._dek          = _decrypt(wrap, passphrase)
                    self._master       = None
                    self._unlocked     = True
                    self._via_recovery = True
                    return True
            except Exception:
                pass
        return False

    def _purge_no_recovery_sentinel(self):
        """Remove legacy '__NO_RECOVERY__' recovery path if present."""
        row = self._meta_get("recovery_check")
        if not row:
            return
        try:
            if _decrypt(row, "__NO_RECOVERY__") == "OK":
                self._db.execute("DELETE FROM meta WHERE key=?", ("recovery_check",))
                self._db.execute("DELETE FROM meta WHERE key=?", ("dek_wrap_recovery",))
                self._db.commit()
                self._write_backup()
        except Exception:
            pass

    def _migrate_legacy_to_dek(self, master: str) -> str:
        """One-time: re-encrypt entry fields from master-as-key → random DEK."""
        dek = secrets.token_urlsafe(32)
        rows = self._db.execute(
            "SELECT id, enc_password, enc_totp FROM entries").fetchall()
        for eid, enc_pw, enc_otp in rows:
            pw = _decrypt(enc_pw, master)
            new_ep = _encrypt(pw, dek)
            new_eotp = ""
            if enc_otp:
                new_eotp = _encrypt(_decrypt(enc_otp, master), dek)
            self._db.execute(
                "UPDATE entries SET enc_password=?, enc_totp=? WHERE id=?",
                (new_ep, new_eotp, eid))
        self._meta_set("dek_wrap_master", _encrypt(dek, master))
        self._db.commit()
        self._write_backup()
        return dek

    def lock(self):
        self._master       = None
        self._dek          = None
        self._unlocked     = False
        self._via_recovery = False
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None

    # ── entries CRUD ──

    def add_entry(self, title, username, password, url="", notes="",
                  totp_secret="") -> str:
        self._require_unlock()
        if self._via_recovery:
            raise RuntimeError("Set a new master password before editing the vault")
        eid     = secrets.token_hex(8)
        enc_pw  = _encrypt(password, self._dek)
        enc_otp = _encrypt(totp_secret, self._dek) if totp_secret else ""
        self._db.execute(
            "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)",
            (eid, title, username, enc_pw, url, notes, int(time.time()), enc_otp))
        self._db.commit()
        self._write_backup()
        return eid

    def update_entry(self, eid, title=None, username=None, password=None,
                     url=None, notes=None, totp_secret=None):
        self._require_unlock()
        if self._via_recovery:
            raise RuntimeError("Set a new master password before editing the vault")
        row = self._db.execute(
            "SELECT title,username,enc_password,url,notes,enc_totp FROM entries WHERE id=?",
            (eid,)).fetchone()
        if not row:
            return
        t, u, ep, ur, n, eotp = row
        if title       is not None: t    = title
        if username    is not None: u    = username
        if password    is not None: ep   = _encrypt(password, self._dek)
        if url         is not None: ur   = url
        if notes       is not None: n    = notes
        if totp_secret is not None:
            eotp = _encrypt(totp_secret, self._dek) if totp_secret else ""
        self._db.execute(
            "UPDATE entries SET title=?,username=?,enc_password=?,url=?,notes=?,enc_totp=? WHERE id=?",
            (t, u, ep, ur, n, eotp, eid))
        self._db.commit()
        self._write_backup()

    def delete_entry(self, eid):
        self._require_unlock()
        if self._via_recovery:
            raise RuntimeError("Set a new master password before editing the vault")
        self._db.execute("DELETE FROM entries WHERE id=?", (eid,))
        self._db.commit()
        self._write_backup()

    def all_entries(self) -> dict:
        self._require_unlock()
        rows = self._db.execute(
            "SELECT id,title,username,enc_password,url,notes,created,enc_totp FROM entries"
            " ORDER BY title COLLATE NOCASE").fetchall()
        out = {}
        for eid, title, username, enc_pw, url, notes, created, enc_otp in rows:
            try:
                pw = _decrypt(enc_pw, self._dek)
            except Exception:
                pw = "⚠ decryption failed"
            try:
                totp = _decrypt(enc_otp, self._dek) if enc_otp else ""
            except Exception:
                totp = ""
            out[eid] = dict(title=title, username=username, password=pw,
                            totp_secret=totp, url=url, notes=notes, created=created)
        return out

    def entry_count(self) -> int:
        if not self._unlocked or not self._db:
            return 0
        return self._db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    # ── master / recovery management ──

    def change_master(self, old: str, new: str) -> bool:
        """Re-wrap DEK under a new master. Aborts if vault is in recovery mode."""
        if self._via_recovery:
            return False
        if old != self._master or not self._dek:
            return False
        self._require_unlock()
        # Verify DEK still unwraps with old master before rewriting sentinels
        wrap = self._meta_get("dek_wrap_master")
        if not wrap:
            return False
        try:
            if _decrypt(wrap, old) != self._dek:
                return False
        except Exception:
            return False
        self._meta_set("master_check", _encrypt("OK", new))
        self._meta_set("dek_wrap_master", _encrypt(self._dek, new))
        self._db.commit()
        self._master = new
        self._write_backup()
        if tfa.enabled() and tfa._data:
            tfa._write(tfa._data, new)
        return True

    def reset_master_after_recovery(self, new_master: str) -> bool:
        """After recovery unlock: set a new master and re-wrap the DEK."""
        if not self._via_recovery or not self._dek or not self._unlocked:
            return False
        self._meta_set("master_check", _encrypt("OK", new_master))
        self._meta_set("dek_wrap_master", _encrypt(self._dek, new_master))
        self._db.commit()
        self._master       = new_master
        self._via_recovery = False
        self._write_backup()
        return True

    def change_recovery(self, master: str, new_recovery: str) -> bool:
        if master != self._master or not self._dek:
            return False
        self._require_unlock()
        self._meta_set("recovery_check", _encrypt("OK", new_recovery))
        self._meta_set("dek_wrap_recovery", _encrypt(self._dek, new_recovery))
        self._db.commit()
        self._write_backup()
        return True

    def has_recovery(self) -> bool:
        if not self._db:
            return False
        return self._meta_get("recovery_check") is not None

    def get_idle_lock_minutes(self) -> int:
        """0 = disabled. Default 5."""
        if not self._db:
            return 5
        raw = self._meta_get("idle_lock_minutes")
        if raw is None:
            return 5
        try:
            return max(0, int(raw))
        except ValueError:
            return 5

    def set_idle_lock_minutes(self, minutes: int) -> None:
        self._require_unlock()
        if self._via_recovery:
            raise RuntimeError("Set a new master password first")
        self._meta_set("idle_lock_minutes", str(max(0, int(minutes))))
        self._db.commit()

    # ── export / import ──

    def export_encrypted_json(self, path: str, passphrase: str):
        self._require_unlock()
        entries = self.all_entries()
        payload = json.dumps({"exported": int(time.time()), "entries": entries})
        token   = _encrypt(payload, passphrase)
        with open(path, "w") as f:
            json.dump({"localpasswordvault_export": True, "v": 3, "data": token}, f, indent=2)

    def import_encrypted_json(self, path: str, passphrase: str) -> int:
        self._require_unlock()
        if self._via_recovery:
            raise RuntimeError("Set a new master password before importing")
        with open(path, "r") as f:
            outer = json.load(f)
        payload = json.loads(_decrypt(outer["data"], passphrase))
        entries = payload.get("entries", {})
        count = 0
        for e in entries.values():
            self.add_entry(
                e["title"], e.get("username", ""),
                e["password"], e.get("url", ""), e.get("notes", ""),
                totp_secret=e.get("totp_secret", ""),
            )
            count += 1
        return count

    # ── backup ──

    def _write_backup(self):
        try:
            if os.path.exists(VAULT_FILE):
                shutil.copy2(VAULT_FILE, BAK_FILE)
        except Exception:
            pass

    def restore_from_backup(self, passphrase: str) -> bool:
        if not self.copy_backup_over_vault():
            return False
        return self.unlock(passphrase)

    def copy_backup_over_vault(self) -> bool:
        if not os.path.exists(BAK_FILE):
            return False
        try:
            shutil.copy2(BAK_FILE, VAULT_FILE)
            self.lock()
            return True
        except Exception:
            return False

    def backup_exists(self): return os.path.exists(BAK_FILE)

    # ── internals ──

    def _connect(self):
        if self._db is None:
            self._db = sqlite3.connect(VAULT_FILE, check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
            self._migrate()

    def _migrate(self):
        exists = self._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        if not exists:
            return
        cols = [r[1] for r in self._db.execute("PRAGMA table_info(entries)")]
        if "enc_totp" not in cols:
            self._db.execute(
                "ALTER TABLE entries ADD COLUMN enc_totp TEXT NOT NULL DEFAULT ''")
            self._db.commit()

    def _init_schema(self):
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entries (
                id            TEXT PRIMARY KEY,
                title         TEXT NOT NULL,
                username      TEXT NOT NULL DEFAULT '',
                enc_password  TEXT NOT NULL,
                url           TEXT NOT NULL DEFAULT '',
                notes         TEXT NOT NULL DEFAULT '',
                created       INTEGER NOT NULL,
                enc_totp      TEXT NOT NULL DEFAULT ''
            );
        """)
        self._db.commit()

    def _require_unlock(self):
        if not self._unlocked or not self._dek:
            raise RuntimeError("Vault is locked")


vault = VaultDB()
