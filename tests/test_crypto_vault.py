"""Minimal crypto / vault unlock tests (no GUI)."""
import pytest

import config
import totp as totp_mod
import vault_db
from crypto import _decrypt, _encrypt


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
