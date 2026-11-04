"""Temp-vault smoke for the Qt bridge: unlock, entry, encrypt, theme, lock."""
import os

import pytest

import config
import totp as totp_mod
import vault_db


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
    vault = vault_db.VaultDB()
    monkeypatch.setattr(vault_db, "vault", vault)
    yield vault
    vault.lock()


def _wait(predicate, timeout=120):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    poll = QTimer()
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    timer.start(int(timeout * 1000))
    poll.start(30)
    loop.exec()
    poll.stop()
    timer.stop()
    return bool(predicate())


@pytest.fixture
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_qt_bridge_smoke(isolated_vault, tmp_path, monkeypatch, qt_app):
    previous = config.get_theme()
    monkeypatch.setattr(config, "PREFS_FILE", str(tmp_path / "prefs.json"))
    from qt_ui.main import build

    engine = None
    try:
        engine, bridge, _palette = build(qt_app)
        assert engine.rootObjects(), "Qt Quick window failed to load"
        assert bridge.screen == "create"

        bridge.submitCreate(
            "MasterPass123!", "MasterPass123!",
            "recovery phrase here", "recovery phrase here",
        )
        assert _wait(lambda: bridge.screen == "main" or bridge.noticeLevel == "danger")
        assert bridge.screen == "main", bridge.notice
        assert vault_db.vault.unlocked

        error = bridge.saveEntry("", "Site", "user", "s3cret", "https://example.com", "note", "")
        assert error == ""
        rows = list(bridge.entries)
        assert any(row["password"] == "s3cret" and row["title"] == "Site" for row in rows)

        captured = {}

        def take(text):
            captured["text"] = text

        bridge.textReady.connect(take)
        bridge.encryptText("passphrase", "hello-secret", True)
        assert _wait(lambda: "text" in captured)
        token = captured.pop("text")
        assert token and token != "hello-secret"

        bridge.encryptText("passphrase", token, False)
        assert _wait(lambda: captured.get("text") == "hello-secret")

        bridge.setTheme("dark")
        assert config.get_theme() == "dark"
        bridge.setTheme("light")
        assert config.get_theme() == "light"

        bridge.lockVault()
        assert not vault_db.vault.unlocked
        assert bridge.screen == "unlock"
        if bridge._runner is not None:
            bridge._runner.wait(5000)
    finally:
        config.save_theme(previous)
        if engine is not None:
            engine.deleteLater()
