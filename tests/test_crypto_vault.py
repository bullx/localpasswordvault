"""Crypto, vault storage, backup, and migration tests (no GUI)."""
import os
import sqlite3
import time

import pytest

import config
import totp as totp_mod
import vault_db
from crypto import (
    _decrypt, _encrypt, decrypt_field, encrypt_field, encrypt_file, decrypt_file,
    field_version, gen_password, passphrase_entropy_bits, pw_strength,
)


@pytest.fixture
def isolated_vault(tmp_path, monkeypatch):
    db = tmp_path / "localpasswordvault.db"
    bak = str(db) + ".bak"
    tfa_path = tmp_path / "localpasswordvault.2fa"
    monkeypatch.setattr(config, "VAULT_FILE", str(db))
    monkeypatch.setattr(config, "BAK_FILE", bak)
    monkeypatch.setattr(config, "TFA_FILE", str(tfa_path))
    monkeypatch.setattr(vault_db, "VAULT_FILE", str(db))
    monkeypatch.setattr(vault_db, "BAK_FILE", bak)
    monkeypatch.setattr(totp_mod, "TFA_FILE", str(tfa_path))
    v = vault_db.VaultDB()
    monkeypatch.setattr(vault_db, "vault", v)
    yield v
    v.lock()


def test_encrypt_decrypt_roundtrip():
    token = _encrypt("hello-secret", "passphrase")
    assert _decrypt(token, "passphrase") == "hello-secret"
    with pytest.raises(Exception):
        _decrypt(token, "wrong")


def test_create_without_recovery_has_no_recovery_check(isolated_vault):
    assert isolated_vault.create("MasterPass123!", recovery=None)
    assert isolated_vault.has_recovery() is False
    assert isolated_vault._meta_get("recovery_check") is None
    assert isolated_vault._meta_get("dek_wrap_recovery") is None


def test_master_unlock_and_entry(isolated_vault):
    isolated_vault.create("MasterPass123!", recovery="recovery phrase here")
    isolated_vault.lock()
    assert isolated_vault.unlock("MasterPass123!")
    assert not isolated_vault.unlocked_via_recovery
    eid = isolated_vault.add_entry("Site", "user", "s3cret", totp_secret="JBSWY3DPEHPK3PXP")
    entries = isolated_vault.all_entries()
    assert entries[eid]["password"] == "s3cret"
    assert entries[eid]["totp_secret"] == "JBSWY3DPEHPK3PXP"


def test_recovery_unlock_requires_new_master(isolated_vault):
    isolated_vault.create("MasterPass123!", recovery="recovery phrase here")
    isolated_vault.add_entry("Site", "user", "s3cret")
    isolated_vault.lock()
    assert isolated_vault.unlock("recovery phrase here")
    assert isolated_vault.unlocked_via_recovery
    assert isolated_vault._master is None
    # Entries still decrypt via DEK
    entries = isolated_vault.all_entries()
    assert any(e["password"] == "s3cret" for e in entries.values())
    with pytest.raises(RuntimeError):
        isolated_vault.add_entry("Nope", "u", "p")
    assert isolated_vault.reset_master_after_recovery("NewMasterPass456!")
    assert not isolated_vault.unlocked_via_recovery
    isolated_vault.lock()
    assert isolated_vault.unlock("NewMasterPass456!")
    assert any(e["password"] == "s3cret" for e in isolated_vault.all_entries().values())


def test_import_keeps_totp(isolated_vault, tmp_path):
    isolated_vault.create("MasterPass123!", recovery=None)
    isolated_vault.add_entry("A", "u", "p", totp_secret="JBSWY3DPEHPK3PXP")
    export_path = tmp_path / "export.json"
    isolated_vault.export_encrypted_json(str(export_path), "export-pass")
    # wipe and re-import into same unlocked vault
    for eid in list(isolated_vault.all_entries()):
        isolated_vault.delete_entry(eid)
    n = isolated_vault.import_encrypted_json(str(export_path), "export-pass")
    assert n == 1
    entries = isolated_vault.all_entries()
    assert list(entries.values())[0]["totp_secret"] == "JBSWY3DPEHPK3PXP"


def test_change_master_aborts_on_wrong_old(isolated_vault):
    isolated_vault.create("MasterPass123!", recovery=None)
    assert isolated_vault.change_master("wrong", "NewMasterPass456!") is False
    isolated_vault.lock()
    assert isolated_vault.unlock("MasterPass123!")


def _vault_bytes() -> bytes:
    blob = b""
    for path in (
        vault_db.VAULT_FILE,
        vault_db.VAULT_FILE + "-wal",
        vault_db.VAULT_FILE + "-shm",
        vault_db.BAK_FILE,
    ):
        if os.path.exists(path):
            with open(path, "rb") as f:
                blob += f.read()
    return blob


def test_field_token_binds_column_and_skips_argon():
    dek = "dek-material-high-entropy-value"
    token = encrypt_field("correct horse", dek, "title")
    assert field_version(token) == 4
    assert decrypt_field(token, dek, "title") == "correct horse"
    with pytest.raises(Exception):
        decrypt_field(token, dek, "password")
    assert b"Argon2id" not in __import__("base64").b64decode(token)


def test_legacy_v3_field_still_decrypts_with_dek():
    dek = "dek-material-high-entropy-value"
    legacy = _encrypt("s3cret", dek)
    assert field_version(legacy) == 3
    assert decrypt_field(legacy, dek, "password") == "s3cret"


def test_metadata_is_not_stored_in_plaintext(isolated_vault):
    marker = "UniqueTitle-9f3c1a7e-DONTLEAK"
    user = "user-9f3c1a7e@example.test"
    secret = "password-9f3c1a7e-value"
    note = "note-9f3c1a7e-private"
    isolated_vault.create("MasterPass123!", recovery="recovery phrase here")
    isolated_vault.add_entry(marker, user, secret, url="https://9f3c1a7e.example", notes=note,
                             totp_secret="JBSWY3DPEHPK3PXP")
    isolated_vault.lock()
    raw = _vault_bytes()
    for needle in (marker, user, secret, note, "JBSWY3DPEHPK3PXP"):
        assert needle.encode() not in raw
    conn = sqlite3.connect(vault_db.VAULT_FILE)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(entries)")]
    conn.close()
    assert "title" not in cols
    assert "enc_title" in cols


def test_many_entries_decrypt_without_per_field_argon(isolated_vault):
    isolated_vault.create("MasterPass123!", recovery=None)
    for i in range(25):
        isolated_vault.add_entry(f"Title {i}", f"user{i}", f"pw-{i}")
    isolated_vault.lock()
    assert isolated_vault.unlock("MasterPass123!")
    started = time.perf_counter()
    entries = isolated_vault.all_entries()
    elapsed = time.perf_counter() - started
    assert len(entries) == 25
    assert elapsed < 2.0
    conn = sqlite3.connect(vault_db.VAULT_FILE)
    version = field_version(conn.execute("SELECT enc_password FROM entries LIMIT 1").fetchone()[0])
    conn.close()
    assert version == 4


def test_backup_restore_keeps_latest_entry(isolated_vault):
    isolated_vault.create("MasterPass123!", recovery=None)
    isolated_vault.add_entry("KeepMeUnique", "user", "pw-keep")
    assert isolated_vault.last_backup_error is None
    assert isolated_vault.backup_exists()
    isolated_vault.lock()
    for suf in ("", "-wal", "-shm", "-journal"):
        path = vault_db.VAULT_FILE + suf
        if os.path.exists(path):
            os.remove(path)
    assert isolated_vault.copy_backup_over_vault()
    assert isolated_vault.unlock("MasterPass123!")
    assert any(e["title"] == "KeepMeUnique" and e["password"] == "pw-keep"
               for e in isolated_vault.all_entries().values())


def test_import_updates_matching_id(isolated_vault, tmp_path):
    isolated_vault.create("MasterPass123!", recovery=None)
    isolated_vault.add_entry("A", "u", "p", totp_secret="JBSWY3DPEHPK3PXP")
    export_path = tmp_path / "export.json"
    isolated_vault.export_encrypted_json(str(export_path), "export-pass")
    raw = export_path.read_bytes()
    assert b"JBSWY3DPEHPK3PXP" not in raw
    isolated_vault.add_entry("Other", "o", "x")
    n = isolated_vault.import_encrypted_json(str(export_path), "export-pass")
    assert n == 1
    assert isolated_vault.entry_count() == 2
    again = isolated_vault.import_encrypted_json(str(export_path), "export-pass")
    assert again == 1
    assert isolated_vault.entry_count() == 2
    secrets = {e["totp_secret"] for e in isolated_vault.all_entries().values()}
    assert "JBSWY3DPEHPK3PXP" in secrets


def test_upgrade_plaintext_metadata_vault(isolated_vault):
    dek = "legacy-dek-value-0123456789"
    master = "MasterPass123!"
    conn = sqlite3.connect(vault_db.VAULT_FILE)
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE entries (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            enc_password TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created INTEGER NOT NULL,
            enc_totp TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.execute("INSERT INTO meta VALUES (?,?)", ("master_check", _encrypt("OK", master)))
    conn.execute("INSERT INTO meta VALUES (?,?)", ("dek_wrap_master", _encrypt(dek, master)))
    conn.execute(
        "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)",
        ("abc", "PlainTitleMarker", "plain-user", _encrypt("legacy-pw", dek),
         "https://plain.example", "plain-note", 1, ""),
    )
    conn.commit()
    conn.close()
    assert isolated_vault.unlock(master)
    entries = isolated_vault.all_entries()
    assert entries["abc"]["title"] == "PlainTitleMarker"
    assert entries["abc"]["password"] == "legacy-pw"
    assert entries["abc"]["username"] == "plain-user"
    isolated_vault.lock()
    raw = _vault_bytes()
    for needle in (b"PlainTitleMarker", b"plain-user", b"legacy-pw", b"plain-note"):
        assert needle not in raw


def test_upgrade_master_keyed_legacy_vault(isolated_vault):
    master = "MasterPass123!"
    conn = sqlite3.connect(vault_db.VAULT_FILE)
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE entries (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            enc_password TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created INTEGER NOT NULL
        );
    """)
    conn.execute("INSERT INTO meta VALUES (?,?)", ("master_check", _encrypt("OK", master)))
    conn.execute(
        "INSERT INTO entries VALUES (?,?,?,?,?,?,?)",
        ("id1", "OldTitleMarker", "old-user", _encrypt("old-secret", master), "", "", 1),
    )
    conn.commit()
    conn.close()
    assert isolated_vault.unlock(master)
    got = isolated_vault.all_entries()["id1"]
    assert got["title"] == "OldTitleMarker"
    assert got["password"] == "old-secret"
    isolated_vault.lock()
    assert isolated_vault.unlock(master)
    assert isolated_vault.all_entries()["id1"]["password"] == "old-secret"


def test_binary_file_roundtrip_and_tamper(tmp_path):
    src = tmp_path / "plain.bin"
    enc = tmp_path / "cipher.lpv"
    out = tmp_path / "back.bin"
    payload = os.urandom(64) + b"\x00\xff" + (b"A" * (1024 * 1024 + 100))
    src.write_bytes(payload)
    encrypt_file(str(src), str(enc), "file-passphrase")
    decrypt_file(str(enc), str(out), "file-passphrase")
    assert out.read_bytes() == payload
    blob = bytearray(enc.read_bytes())
    blob[-8] ^= 0x5A
    enc.write_bytes(blob)
    with pytest.raises(Exception):
        decrypt_file(str(enc), str(tmp_path / "bad.bin"), "file-passphrase")
    with pytest.raises(ValueError):
        encrypt_file(str(src), str(src), "file-passphrase")


def test_strength_and_generator_edges():
    score, label, _ = pw_strength("password")
    assert score < 30 and label == "Very Weak"
    pw = gen_password(4, upper=True, lower=True, digits=True, symbols=True, no_amb=True)
    assert len(pw) >= 4
    bits = passphrase_entropy_bits(5, 2048)
    assert 50 < bits < 60
