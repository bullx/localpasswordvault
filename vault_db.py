"""
SQLite vault. Entry fields are AES-256-GCM under a random DEK.

The DEK is wrapped with Argon2id under the master password and, optionally,
the recovery passphrase. Titles, usernames, URLs, and notes are encrypted
the same way as passwords. A session cache holds plaintext only while unlocked.
"""
import os, json, time, secrets, sqlite3, re

from config import VAULT_FILE, BAK_FILE
from crypto import _encrypt, _decrypt, encrypt_field, decrypt_field, field_version
from totp import tfa


_COL_OK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_META_DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_ENTRIES_DDL = """
CREATE TABLE entries (
    id            TEXT PRIMARY KEY,
    enc_title     TEXT NOT NULL DEFAULT '',
    enc_username  TEXT NOT NULL DEFAULT '',
    enc_password  TEXT NOT NULL,
    enc_url       TEXT NOT NULL DEFAULT '',
    enc_notes     TEXT NOT NULL DEFAULT '',
    enc_totp      TEXT NOT NULL DEFAULT '',
    created       INTEGER NOT NULL,
    updated       INTEGER NOT NULL
)
"""


def _safe_cols(cols) -> list[str]:
    return [c for c in cols if _COL_OK.fullmatch(c or "")]


class VaultDB:
    def __init__(self):
        self._master = None
        self._dek = None
        self._unlocked = False
        self._via_recovery = False
        self._db = None
        self._cache = None
        self._pending = None          # (kind, dek, passphrase) between 2FA steps
        self._staged_export = None    # (path, payload) so import does not Argon2 twice
        self.last_backup_error = None

    @property
    def unlocked(self):
        return self._unlocked

    @property
    def unlocked_via_recovery(self):
        return self._via_recovery

    def has_pending(self) -> bool:
        return self._pending is not None

    def abort_unlock(self):
        self._pending = None

    def vault_exists(self):
        return os.path.exists(VAULT_FILE)

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
            VAULT_FILE + "-wal", VAULT_FILE + "-shm", VAULT_FILE + "-journal",
            BAK_FILE + "-wal", BAK_FILE + "-shm",
        ):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def verify_passphrase(self, passphrase: str) -> str | None:
        """Returns 'master', 'recovery', or None. Does not unlock or migrate."""
        if not self.vault_exists() or not passphrase:
            return None
        conn = sqlite3.connect(VAULT_FILE, check_same_thread=False)
        try:
            resolved = self._resolve_dek(conn, passphrase)
            return resolved[0] if resolved else None
        finally:
            conn.close()

    def begin_unlock(self, passphrase: str) -> str | None:
        """
        Verify, upgrade legacy rows, and stash the DEK.
        Safe to call off the UI thread. Does not leave the vault unlocked.
        """
        self._pending = None
        if not passphrase or not self.vault_exists():
            return None
        conn = sqlite3.connect(VAULT_FILE, check_same_thread=False)
        try:
            self._prepare(conn)
            resolved = self._resolve_dek(conn, passphrase)
            if not resolved:
                return None
            kind, dek, legacy = resolved
            self._upgrade_entries(conn, dek, passphrase, legacy)
            if kind == "master":
                self._purge_no_recovery_sentinel(conn)
            self._pending = (kind, dek, passphrase)
            return kind
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            self._pending = None
            raise
        finally:
            conn.close()

    def finish_unlock(self) -> bool:
        """Open the session using the DEK stashed by begin_unlock. Call on the UI thread."""
        if not self._pending:
            return False
        kind, dek, passphrase = self._pending
        self._pending = None
        self._connect()
        self._dek = dek
        self._master = passphrase if kind == "master" else None
        self._unlocked = True
        self._via_recovery = kind == "recovery"
        self._cache = None
        return True

    def unlock(self, passphrase: str) -> bool:
        """Verify, upgrade if needed, and open the session."""
        kind = self.begin_unlock(passphrase)
        if not kind:
            return False
        return self.finish_unlock()

    def lock(self):
        self._master = None
        self._dek = None
        self._unlocked = False
        self._via_recovery = False
        self._cache = None
        self._pending = None
        self._staged_export = None
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None

    # ── create ──

    def create(self, master: str, recovery: str | None = None) -> bool:
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
        self._master = master
        self._dek = dek
        self._unlocked = True
        self._via_recovery = False
        self._cache = None
        self._write_backup()
        return True

    # ── entries ──

    def add_entry(self, title, username, password, url="", notes="",
                  totp_secret="", eid=None, created=None, updated=None) -> str:
        self._require_edit()
        eid = eid or secrets.token_hex(8)
        now = int(time.time())
        self._upsert(
            eid, title, username, password, url, notes, totp_secret,
            int(created or now), int(updated or now),
        )
        self._write_backup()
        return eid

    def update_entry(self, eid, title=None, username=None, password=None,
                     url=None, notes=None, totp_secret=None):
        self._require_edit()
        cur = self._read_row(eid)
        if not cur:
            return
        now = int(time.time())
        self._upsert(
            eid,
            cur["title"] if title is None else title,
            cur["username"] if username is None else username,
            cur["password"] if password is None else password,
            cur["url"] if url is None else url,
            cur["notes"] if notes is None else notes,
            cur["totp_secret"] if totp_secret is None else totp_secret,
            cur["created"],
            now,
        )
        self._write_backup()

    def delete_entry(self, eid):
        self._require_edit()
        self._db.execute("DELETE FROM entries WHERE id=?", (eid,))
        self._db.commit()
        self._cache = None
        self._write_backup()

    def all_entries(self) -> dict:
        self._require_unlock()
        data = self._load_all()
        items = sorted(data.items(), key=lambda kv: (kv[1].get("title") or "").casefold())
        return {k: dict(v) for k, v in items}

    def entry_count(self) -> int:
        if not self._unlocked or not self._db:
            return 0
        return self._db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    # ── master / recovery ──

    def change_master(self, old: str, new: str) -> bool:
        if self._via_recovery:
            return False
        if old != self._master or not self._dek:
            return False
        self._require_unlock()
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
        if not self._via_recovery or not self._dek or not self._unlocked:
            return False
        self._meta_set("master_check", _encrypt("OK", new_master))
        self._meta_set("dek_wrap_master", _encrypt(self._dek, new_master))
        self._db.commit()
        self._master = new_master
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
        if any(e.get("decrypt_error") for e in entries.values()):
            raise RuntimeError("Refusing to export: an entry could not be decrypted.")
        public = {}
        for eid, e in entries.items():
            public[eid] = {
                "id": eid,
                "title": e["title"],
                "username": e["username"],
                "password": e["password"],
                "url": e["url"],
                "notes": e["notes"],
                "totp_secret": e["totp_secret"],
                "created": e["created"],
                "updated": e["updated"],
            }
        payload = json.dumps({"exported": int(time.time()), "entries": public})
        token = _encrypt(payload, passphrase)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"localpasswordvault_export": True, "v": 4, "data": token}, f, indent=2)

    def summarize_export(self, path: str, passphrase: str) -> dict:
        """Decrypt an export and remember it for the following import."""
        self._require_unlock()
        payload = self._read_export(path, passphrase)
        self._staged_export = (os.path.abspath(path), payload)
        return {"count": len(payload.get("entries") or {})}

    def clear_staged_export(self):
        self._staged_export = None

    def import_encrypted_json(self, path: str, passphrase: str) -> int:
        """Insert new ids and update matching ids. Returns rows applied."""
        self._require_edit()
        abspath = os.path.abspath(path)
        staged = self._staged_export
        if staged and staged[0] == abspath:
            payload = staged[1]
        else:
            payload = self._read_export(path, passphrase)
        self._staged_export = None
        entries = payload.get("entries") or {}
        existing = {row[0] for row in self._db.execute("SELECT id FROM entries")}
        count = 0
        try:
            for key, e in entries.items():
                eid = str(e.get("id") or key)
                title = e.get("title") or ""
                username = e.get("username") or ""
                password = e.get("password") or ""
                url = e.get("url") or ""
                notes = e.get("notes") or ""
                totp_secret = e.get("totp_secret") or ""
                created = e.get("created")
                updated = e.get("updated")
                if eid in existing:
                    cur = self._read_row(eid)
                    created = created or (cur["created"] if cur else None)
                now = int(time.time())
                self._upsert(
                    eid, title, username, password, url, notes, totp_secret,
                    int(created or now), int(updated or now),
                    commit=False,
                )
                existing.add(eid)
                count += 1
            self._db.commit()
        except Exception:
            self._db.rollback()
            self._cache = None
            raise
        self._cache = None
        self._write_backup()
        return count

    # ── backup ──

    def backup_exists(self):
        return os.path.exists(BAK_FILE)

    def restore_from_backup(self, passphrase: str) -> bool:
        if not self.copy_backup_over_vault():
            return False
        return self.unlock(passphrase)

    def copy_backup_over_vault(self) -> bool:
        if not os.path.exists(BAK_FILE):
            return False
        self.lock()
        try:
            for suf in ("-wal", "-shm", "-journal"):
                path = VAULT_FILE + suf
                if os.path.exists(path):
                    os.remove(path)
            # Backup API writes a self-contained DB. Replace the live file only.
            src = sqlite3.connect(BAK_FILE)
            try:
                if os.path.exists(VAULT_FILE):
                    os.remove(VAULT_FILE)
                dst = sqlite3.connect(VAULT_FILE)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
            for suf in ("-wal", "-shm", "-journal"):
                path = VAULT_FILE + suf
                if os.path.exists(path):
                    os.remove(path)
            return True
        except Exception:
            return False

    # ── internals ──

    def _meta_get(self, key: str, conn=None):
        db = conn or self._db
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _meta_set(self, key: str, value: str, conn=None):
        db = conn or self._db
        db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    def _prepare(self, conn):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute(_META_DDL)
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        if not exists:
            conn.execute(_ENTRIES_DDL)
            conn.commit()
            return
        cols = _safe_cols(r[1] for r in conn.execute("PRAGMA table_info(entries)"))
        if "enc_password" in cols and "enc_totp" not in cols:
            conn.execute("ALTER TABLE entries ADD COLUMN enc_totp TEXT NOT NULL DEFAULT ''")
            conn.commit()

    def _connect(self):
        if self._db is None:
            self._db = sqlite3.connect(VAULT_FILE, check_same_thread=False)
            self._prepare(self._db)

    def _resolve_dek(self, conn, passphrase):
        """Return (kind, dek, legacy_master_fields) or None. Does not write."""
        row = self._meta_get("master_check", conn)
        if row:
            try:
                if _decrypt(row, passphrase) == "OK":
                    wrap = self._meta_get("dek_wrap_master", conn)
                    if wrap:
                        return "master", _decrypt(wrap, passphrase), False
                    return "master", secrets.token_urlsafe(32), True
            except Exception:
                pass
        row = self._meta_get("recovery_check", conn)
        if row:
            try:
                if _decrypt(row, passphrase) == "OK":
                    wrap = self._meta_get("dek_wrap_recovery", conn)
                    if not wrap:
                        return None
                    return "recovery", _decrypt(wrap, passphrase), False
            except Exception:
                pass
        return None

    def _purge_no_recovery_sentinel(self, conn):
        row = self._meta_get("recovery_check", conn)
        if not row:
            return
        try:
            if _decrypt(row, "__NO_RECOVERY__") == "OK":
                conn.execute("DELETE FROM meta WHERE key=?", ("recovery_check",))
                conn.execute("DELETE FROM meta WHERE key=?", ("dek_wrap_recovery",))
                conn.commit()
                self._backup_conn(conn)
        except Exception:
            pass

    def _needs_upgrade(self, conn, cols, legacy: bool) -> bool:
        if legacy or "title" in cols:
            return True
        if "enc_title" not in cols:
            return True
        for col in ("enc_title", "enc_username", "enc_password", "enc_url", "enc_notes", "enc_totp"):
            if col not in cols:
                continue
            for (tok,) in conn.execute(f"SELECT {col} FROM entries"):
                if tok and field_version(tok) != 4:
                    return True
        return False

    def _take_text(self, row: dict, plain: str, enc: str, dek: str, column: str) -> str:
        token = row.get(enc) or ""
        if token:
            version = field_version(token)
            if version == 4:
                return decrypt_field(token, dek, column)
            try:
                return decrypt_field(token, dek, column)
            except Exception:
                pass
        return row.get(plain) or ""

    def _upgrade_entries(self, conn, dek: str, passphrase: str, legacy: bool) -> bool:
        cols = _safe_cols(r[1] for r in conn.execute("PRAGMA table_info(entries)"))
        if not cols or "id" not in cols:
            return False
        if not self._needs_upgrade(conn, cols, legacy):
            return False

        raw_rows = conn.execute(
            "SELECT " + ", ".join(cols) + " FROM entries"
        ).fetchall()
        sealed = []
        for raw in raw_rows:
            row = dict(zip(cols, raw))
            if legacy:
                password = _decrypt(row.get("enc_password") or "", passphrase)
                otp_tok = row.get("enc_totp") or ""
                totp = _decrypt(otp_tok, passphrase) if otp_tok else ""
                title = row.get("title") or ""
                username = row.get("username") or ""
                url = row.get("url") or ""
                notes = row.get("notes") or ""
            else:
                password = self._take_text(row, "password", "enc_password", dek, "password")
                otp_tok = row.get("enc_totp") or ""
                totp = decrypt_field(otp_tok, dek, "totp") if otp_tok else ""
                title = self._take_text(row, "title", "enc_title", dek, "title")
                username = self._take_text(row, "username", "enc_username", dek, "username")
                url = self._take_text(row, "url", "enc_url", dek, "url")
                notes = self._take_text(row, "notes", "enc_notes", dek, "notes")
            created = int(row.get("created") or time.time())
            updated = int(row.get("updated") or created)
            sealed.append(self._seal(
                dek, row["id"], title, username, password, url, notes, totp, created, updated,
            ))

        if legacy:
            self._meta_set("dek_wrap_master", _encrypt(dek, passphrase), conn)

        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("DROP TABLE IF EXISTS entries_v4")
        conn.execute(_ENTRIES_DDL.replace("CREATE TABLE entries", "CREATE TABLE entries_v4", 1))
        conn.executemany(
            "INSERT INTO entries_v4 VALUES (?,?,?,?,?,?,?,?,?)",
            sealed,
        )
        conn.execute("DROP TABLE entries")
        conn.execute("ALTER TABLE entries_v4 RENAME TO entries")
        conn.commit()
        sealed.clear()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        # VACUUM cannot run inside a transaction. Autocommit for this statement only.
        previous_isolation = conn.isolation_level
        try:
            conn.isolation_level = None
            conn.execute("VACUUM")
        except Exception:
            pass
        finally:
            conn.isolation_level = previous_isolation
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA secure_delete=ON")
        self._backup_conn(conn)
        return True

    def _seal(self, dek, eid, title, username, password, url, notes, totp, created, updated):
        return (
            eid,
            encrypt_field(title or "", dek, "title"),
            encrypt_field(username or "", dek, "username"),
            encrypt_field(password or "", dek, "password"),
            encrypt_field(url or "", dek, "url"),
            encrypt_field(notes or "", dek, "notes"),
            encrypt_field(totp, dek, "totp") if totp else "",
            int(created),
            int(updated),
        )

    def _upsert(self, eid, title, username, password, url, notes, totp,
                created, updated, commit=True):
        vals = self._seal(self._dek, eid, title, username, password, url, notes, totp, created, updated)
        exists = self._db.execute("SELECT 1 FROM entries WHERE id=?", (eid,)).fetchone()
        if exists:
            self._db.execute(
                "UPDATE entries SET enc_title=?, enc_username=?, enc_password=?, enc_url=?, "
                "enc_notes=?, enc_totp=?, created=?, updated=? WHERE id=?",
                vals[1:] + (eid,),
            )
        else:
            self._db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?)", vals)
        if commit:
            self._db.commit()
            self._cache = None

    def _read_row(self, eid) -> dict | None:
        row = self._db.execute(
            "SELECT id, enc_title, enc_username, enc_password, enc_url, enc_notes, "
            "enc_totp, created, updated FROM entries WHERE id=?",
            (eid,),
        ).fetchone()
        if not row:
            return None
        decoded = self._decode_row(row)
        return decoded

    def _decode_row(self, row) -> dict:
        eid, et, eu, ep, eurl, en, eotp, created, updated = row
        item = {
            "title": "", "username": "", "password": "", "url": "", "notes": "",
            "totp_secret": "", "created": int(created or 0),
            "updated": int(updated or created or 0), "decrypt_error": False,
        }
        fields = (
            ("title", et, "title"),
            ("username", eu, "username"),
            ("password", ep, "password"),
            ("url", eurl, "url"),
            ("notes", en, "notes"),
        )
        for key, token, column in fields:
            try:
                item[key] = decrypt_field(token, self._dek, column) if token else ""
            except Exception:
                item["decrypt_error"] = True
                if key == "password":
                    item["password"] = ""
        try:
            item["totp_secret"] = decrypt_field(eotp, self._dek, "totp") if eotp else ""
        except Exception:
            item["decrypt_error"] = True
            item["totp_secret"] = ""
        return item

    def _load_all(self) -> dict:
        if self._cache is not None:
            return self._cache
        rows = self._db.execute(
            "SELECT id, enc_title, enc_username, enc_password, enc_url, enc_notes, "
            "enc_totp, created, updated FROM entries"
        ).fetchall()
        out = {}
        for row in rows:
            out[row[0]] = self._decode_row(row)
        self._cache = out
        return out

    def _read_export(self, path: str, passphrase: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            outer = json.load(f)
        if not outer.get("localpasswordvault_export") or "data" not in outer:
            raise ValueError("Not a LocalPasswordVault export")
        payload = json.loads(_decrypt(outer["data"], passphrase))
        if not isinstance(payload, dict) or not isinstance(payload.get("entries", {}), dict):
            raise ValueError("Export payload is invalid")
        return payload

    def _backup_conn(self, conn):
        self.last_backup_error = None
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dest = sqlite3.connect(BAK_FILE)
            try:
                conn.backup(dest)
            finally:
                dest.close()
            for suf in ("-wal", "-shm"):
                path = BAK_FILE + suf
                if os.path.exists(path):
                    os.remove(path)
        except Exception as exc:
            self.last_backup_error = str(exc)

    def _write_backup(self):
        if self._db is not None:
            self._backup_conn(self._db)

    def _require_unlock(self):
        if not self._unlocked or not self._dek:
            raise RuntimeError("Vault is locked")

    def _require_edit(self):
        self._require_unlock()
        if self._via_recovery:
            raise RuntimeError("Set a new master password before editing the vault")


vault = VaultDB()
