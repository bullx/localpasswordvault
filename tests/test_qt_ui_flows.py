"""Drive the Qt Quick window through the vault screens."""
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


@pytest.fixture
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _Ui:
    def __init__(self, app, engine, bridge):
        from PySide6.QtCore import qInstallMessageHandler
        self.app = app
        self.engine = engine
        self.bridge = bridge
        self.errors = []

        def handler(_mode, _ctx, message):
            text = str(message)
            if "font directory" in text or "Qt no longer ships fonts" in text:
                return
            if "Error:" in text or "TypeError" in text or "ReferenceError" in text:
                self.errors.append(text)

        qInstallMessageHandler(handler)

    @property
    def window(self):
        return self.engine.rootObjects()[0]

    def pump(self, ms=50):
        from PySide6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def wait(self, predicate, timeout=90):
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
        self.assert_clean()
        return bool(predicate())

    def assert_clean(self):
        assert not self.errors, "\n".join(self.errors[:12])

    def objects(self):
        found = []
        seen = set()

        def walk(obj):
            marker = id(obj)
            if marker in seen:
                return
            seen.add(marker)
            found.append(obj)
            kids = []
            child_items = getattr(obj, "childItems", None)
            if child_items is not None:
                try:
                    kids.extend(child_items())
                except Exception:
                    pass
            try:
                kids.extend(obj.children())
            except Exception:
                pass
            for child in kids:
                walk(child)

        walk(self.window)
        return found

    def visible(self, obj):
        node = obj
        while node is not None:
            if node.property("visible") is False:
                return False
            node = node.parent()
        return True

    def find(self, text=None, class_part=None, object_name=None):
        hits = []
        for obj in self.objects():
            if object_name is not None and obj.objectName() != object_name:
                continue
            if text is not None and obj.property("text") != text:
                continue
            if class_part is not None and class_part not in obj.metaObject().className():
                continue
            if not self.visible(obj):
                continue
            hits.append(obj)
        return hits

    def require(self, text, class_part=None):
        hits = self.find(text=text, class_part=class_part)
        assert hits, f"no visible item with text {text!r}"
        return hits[-1]

    def click(self, obj):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest
        signal = getattr(obj, "clicked", None)
        class_name = obj.metaObject().className()
        if signal is not None and (class_name.startswith("LpvButton") or class_name.startswith("LpvRadio")):
            signal.emit()
            self.pump()
            self.assert_clean()
            return
        assert isinstance(obj, QQuickItem), obj.metaObject().className()
        center = obj.mapToScene(QPointF(max(obj.width(), 1) / 2, max(obj.height(), 1) / 2))
        QTest.mouseClick(
            self.window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            center.toPoint(),
        )
        self.pump()
        self.assert_clean()

    def click_text(self, text, class_part=None):
        self.click(self.require(text, class_part))

    def fields(self, class_part, placeholder=None):
        hits = []
        for obj in self.objects():
            if class_part not in obj.metaObject().className():
                continue
            if not self.visible(obj):
                continue
            if placeholder is not None and obj.property("placeholderText") != placeholder:
                continue
            hits.append(obj)
        return hits

    def field(self, placeholder):
        hits = self.fields("TextField", placeholder) or self.fields("TextArea", placeholder)
        assert hits, f"no visible field {placeholder!r}"
        return hits[-1]

    def set_field(self, obj, value):
        assert obj.setProperty("text", value)
        self.pump(20)


def test_qt_ui_flows(isolated_vault, tmp_path, monkeypatch, qt_app):
    previous = config.get_theme()
    monkeypatch.setattr(config, "PREFS_FILE", str(tmp_path / "prefs.json"))
    from qt_ui.main import build

    engine, bridge, _palette = build(qt_app)
    ui = _Ui(qt_app, engine, bridge)
    try:
        assert engine.rootObjects()
        ui.pump(150)
        ui.assert_clean()
        assert bridge.screen == "create"

        ui.set_field(ui.field("Choose a strong master password"), "MasterPass123!")
        ui.set_field(ui.field("Confirm master password"), "MasterPass123!")
        ui.set_field(ui.field("e.g. My dog Biscuit was born in 2015"), "recovery phrase here")
        ui.set_field(ui.field("Confirm recovery passphrase"), "recovery phrase here")
        ui.click_text("Create Vault")
        assert ui.wait(lambda: bridge.screen == "main" or bridge.noticeLevel == "danger")
        assert bridge.screen == "main", bridge.notice
        ui.pump(150)

        for page in ("Encrypt", "Generate", "Settings", "Vault"):
            ui.click_text(page, "LpvButton")
            assert bridge.page == page
            ui.pump(40)

        path = ui.find(object_name="vaultPath")
        assert path, "vault path chip missing"
        ui.click(path[0])
        assert path[0].property("text") == "Copied"
        ui.assert_clean()

        ui.click_text("Add entry", "LpvButton")
        ui.pump(80)
        ui.set_field(ui.field("Title"), "Example")
        ui.set_field(ui.field("Password"), "s3cret-pass")
        ui.click_text("Save", "LpvButton")
        ui.pump(80)
        assert any(row["title"] == "Example" and row["password"] == "s3cret-pass" for row in bridge.entries)
        assert ui.find(text="Example"), "saved entry is not shown in the list"

        ui.set_field(ui.field("Search title, username, URL, or notes"), "Example")
        ui.pump(40)
        ui.click_text("Encrypt", "LpvButton")
        ui.set_field(ui.field("Passphrase for this encryption"), "passphrase")
        areas = ui.fields("TextArea")
        assert areas
        ui.set_field(areas[0], "hello-secret")
        ui.click_text("Encrypt text", "LpvButton")
        assert ui.wait(lambda: any((item.property("text") or "").startswith("ey") or len(item.property("text") or "") > 20 for item in ui.fields("TextArea")))
        token = ""
        for item in ui.fields("TextArea"):
            value = item.property("text") or ""
            if value and value != "hello-secret":
                token = value
        assert token

        ui.click_text("Generate", "LpvButton")
        ui.pump(40)
        ui.click_text("Generate password", "LpvButton")
        words = ui.require("6", "Radio")
        ui.click(words)
        assert words.property("checked") is True
        ui.click_text("Generate passphrase", "LpvButton")
        ui.assert_clean()

        ui.click_text("Settings", "LpvButton")
        ui.click_text("Dark", "LpvButton")
        assert config.get_theme() == "dark"
        ui.click_text("Light", "LpvButton")
        assert config.get_theme() == "light"
        assert ui.find(text="Argon2id"), "security details are not shown"
        ui.click_text("Enable two-factor authentication", "LpvButton")
        ui.pump(80)
        assert ui.find(text="Step 1 of 3 — Scan into Authenticator")
        ui.click_text("Cancel", "LpvButton")
        ui.pump(40)
        ui.assert_clean()

        ui.click_text("Lock", "LpvButton")
        assert bridge.screen == "unlock"
        ui.pump(80)
        ui.set_field(ui.field("Master password or recovery passphrase"), "recovery phrase here")
        ui.click_text("Unlock Vault", "LpvButton")
        assert ui.wait(lambda: bridge.screen == "reset_master" or bridge.noticeLevel == "danger")
        assert bridge.screen == "reset_master", bridge.notice
        ui.set_field(ui.field("New master password"), "NewMasterPass456!")
        ui.set_field(ui.field("Confirm new master password"), "NewMasterPass456!")
        ui.click_text("Save master & open vault", "LpvButton")
        assert ui.wait(lambda: bridge.screen == "main" or bridge.noticeLevel == "danger")
        assert bridge.screen == "main", bridge.notice
        assert any(row["password"] == "s3cret-pass" for row in bridge.entries)
        ui.assert_clean()
    finally:
        config.save_theme(previous)
        engine.deleteLater()
        qt_app.processEvents()
