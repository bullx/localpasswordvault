import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: root

    function levelColor(level) {
        if (level === "danger")
            return lpv.danger
        if (level === "success")
            return lpv.success
        if (level === "warning")
            return lpv.warning
        return lpv.subtext
    }

    Connections {
        target: bridge
        function onClearFields(which) {
            if (which === "master") {
                oldPw.text = ""
                newPw.text = ""
                newPw2.text = ""
            } else if (which === "recovery") {
                recAuth.text = ""
                recNew.text = ""
                recNew2.text = ""
            }
        }
    }

    Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight + 32
        clip: true

        ColumnLayout {
            id: column
            width: Math.min(parent.width, 840)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 16

            Label {
                text: "Settings and security"
                color: lpv.text
                font.pixelSize: 20
                font.bold: true
                Layout.leftMargin: 24
                Layout.topMargin: 24
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: themeBox.implicitHeight + 32
                ColumnLayout {
                    id: themeBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Appearance"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "Light or dark. Colors update immediately."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    Rectangle {
                        radius: 10
                        color: lpv.surface2
                        border.color: lpv.border
                        border.width: 1
                        antialiasing: true
                        implicitWidth: themeRow.implicitWidth + 8
                        implicitHeight: 48
                        RowLayout {
                            id: themeRow
                            anchors.fill: parent
                            anchors.margins: 4
                            spacing: 4
                            LpvButton {
                                text: "Light"
                                variant: lpv.mode === "light" ? "primary" : "ghost"
                                onClicked: bridge.setTheme("light")
                            }
                            LpvButton {
                                text: "Dark"
                                variant: lpv.mode === "dark" ? "primary" : "ghost"
                                onClicked: bridge.setTheme("dark")
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: masterBox.implicitHeight + 32
                ColumnLayout {
                    id: masterBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Change Master Password"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "Re-wraps the vault key under your new master password."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    SecretField { id: oldPw; Layout.fillWidth: true; placeholderText: "Current master password" }
                    SecretField {
                        id: newPw
                        Layout.fillWidth: true
                        placeholderText: "New master password"
                        onTextChanged: {
                            var info = bridge.strength(text)
                            masterMeter.score = info.score
                            masterMeter.label = info.label
                            masterMeter.barColor = info.color
                        }
                    }
                    SecretField { id: newPw2; Layout.fillWidth: true; placeholderText: "Confirm new password" }
                    StrengthMeter { id: masterMeter; Layout.fillWidth: true }
                    Label {
                        visible: bridge.masterMessage !== ""
                        text: bridge.masterMessage
                        color: root.levelColor(bridge.masterLevel)
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    LpvButton {
                        text: "Change Master Password"
                        variant: "primary"
                        enabled: !bridge.busy
                        onClicked: bridge.changeMaster(oldPw.text, newPw.text, newPw2.text)
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: recBox.implicitHeight + 32
                ColumnLayout {
                    id: recBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Recovery Passphrase"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "A second passphrase that can unlock the vault if you forget the master."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    Label {
                        text: bridge.recoverySet ? "Recovery passphrase is set." : "No recovery passphrase set."
                        color: bridge.recoverySet ? lpv.success : lpv.warning
                        font.pixelSize: 12
                    }
                    SecretField { id: recAuth; Layout.fillWidth: true; label: "Master password (to authorise change)"; placeholderText: "Master password" }
                    SecretField { id: recNew; Layout.fillWidth: true; label: "New recovery passphrase"; placeholderText: "e.g. My dog Biscuit was born in 2015" }
                    SecretField { id: recNew2; Layout.fillWidth: true; label: "Confirm recovery passphrase"; placeholderText: "Confirm recovery passphrase" }
                    Label {
                        visible: bridge.recoveryMessage !== ""
                        text: bridge.recoveryMessage
                        color: root.levelColor(bridge.recoveryLevel)
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    LpvButton {
                        text: "Save Recovery Passphrase"
                        variant: "primary"
                        enabled: !bridge.busy
                        onClicked: bridge.changeRecovery(recAuth.text, recNew.text, recNew2.text)
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: idleBox.implicitHeight + 32
                ColumnLayout {
                    id: idleBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Idle Auto-Lock"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "Lock the vault after a period without keyboard or mouse activity."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    RowLayout {
                        Label { text: "Minutes (0 = disabled)"; color: lpv.subtext; font.pixelSize: 12 }
                        LpvField { id: idleField; Layout.preferredWidth: 80 }
                        LpvButton { text: "Save"; variant: "ghost"; onClicked: bridge.setIdleMinutes(idleField.text) }
                    }
                    Label {
                        visible: bridge.idleMessage !== ""
                        text: bridge.idleMessage
                        color: root.levelColor(bridge.idleLevel)
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: expBox.implicitHeight + 32
                ColumnLayout {
                    id: expBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Export Vault"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "Encrypted JSON — importable on any LocalPasswordVault installation. Export encrypts every entry with a passphrase you choose. The file is useless without that passphrase. Importing the same file again updates matching entries instead of duplicating them."
                    }
                    SecretField { id: expPw; Layout.fillWidth: true; placeholderText: "Export passphrase (can differ from master)" }
                    SecretField { id: expPw2; Layout.fillWidth: true; placeholderText: "Confirm export passphrase" }
                    Label {
                        visible: bridge.exportMessage !== ""
                        text: bridge.exportMessage
                        color: root.levelColor(bridge.exportLevel)
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                    }
                    RowLayout {
                        LpvButton {
                            text: "Export to file…"
                            variant: "ghost"
                            enabled: !bridge.busy
                            onClicked: saveExport.open()
                        }
                        LpvButton {
                            text: "Import from file…"
                            variant: "ghost"
                            enabled: !bridge.busy
                            onClicked: openImport.open()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: bakBox.implicitHeight + 32
                ColumnLayout {
                    id: bakBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Backup"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        text: "Auto-backup is written next to the vault after every change."
                        color: lpv.subtext
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        font.pixelSize: 12
                    }
                    Label {
                        text: bridge.backupText
                        color: bridge.backupOk ? lpv.success : lpv.danger
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                        font.pixelSize: 12
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "The backup uses the same master password as the vault. It is a consistent SQLite snapshot, including the latest save. Restore it from the unlock screen if the vault file is damaged."
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: tfaBox.implicitHeight + 32
                ColumnLayout {
                    id: tfaBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Two-Factor Authentication (App 2FA)"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    Label {
                        text: "Require an authenticator code every time you unlock the vault."
                        color: lpv.subtext
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        font.pixelSize: 12
                    }

                    ColumnLayout {
                        visible: !bridge.twoFaOn
                        Layout.fillWidth: true
                        spacing: 8
                        Label { text: "Two-factor authentication is off."; color: lpv.subtext; font.pixelSize: 14 }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            color: lpv.subtext
                            font.pixelSize: 12
                            text: "When enabled, every unlock needs the master password and a 6-digit code from an authenticator app. The TOTP secret is stored in localpasswordvault.2fa, encrypted with the master password. Recovery passphrase unlock skips the authenticator and then requires a new master password."
                        }
                        LpvButton { text: "Enable two-factor authentication"; onClicked: bridge.startSetup() }
                    }

                    ColumnLayout {
                        visible: bridge.twoFaOn
                        Layout.fillWidth: true
                        spacing: 8
                        Label { text: "Two-factor authentication is on."; color: lpv.success; font.bold: true; font.pixelSize: 14 }
                        Label {
                            text: bridge.twoFaCodesOn
                                  ? (bridge.twoFaRemaining + "/10 recovery codes remaining")
                                  : "Recovery codes are disabled"
                            color: !bridge.twoFaCodesOn ? lpv.danger
                                 : (bridge.twoFaRemaining > 3 ? lpv.success : (bridge.twoFaRemaining > 0 ? lpv.warning : lpv.danger))
                            font.pixelSize: 12
                        }
                        Label { text: "Transfer to a new phone"; color: lpv.text; font.bold: true; font.pixelSize: 13 }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: "Shows the QR code for a new authenticator app. You must already be unlocked."
                            color: lpv.subtext
                            font.pixelSize: 12
                        }
                        LpvButton { text: "Show transfer QR"; variant: "ghost"; onClicked: bridge.showTransfer() }
                        Label { text: "Recovery codes"; color: lpv.text; font.bold: true; font.pixelSize: 13 }
                        Label { text: "Each code works once if you lose the authenticator."; color: lpv.subtext; font.pixelSize: 12 }
                        RowLayout {
                            LpvButton { text: "Regenerate codes"; variant: "ghost"; onClicked: bridge.startCodeAction("regen") }
                            LpvButton {
                                text: bridge.twoFaCodesOn ? "Disable codes" : "Enable codes"
                                variant: "ghost"
                                onClicked: bridge.startCodeAction(bridge.twoFaCodesOn ? "disable_codes" : "enable_codes")
                            }
                        }
                        Label { text: "Danger zone"; color: lpv.danger; font.bold: true; font.pixelSize: 13 }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: "Disabling 2FA removes the .2fa file. You can turn it on again later."
                            color: lpv.subtext
                            font.pixelSize: 12
                        }
                        LpvButton { text: "Disable 2FA…"; variant: "danger"; onClicked: bridge.openDisable2fa() }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: sec.implicitHeight + 32
                ColumnLayout {
                    id: sec
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 10
                    Label { text: "Security Architecture"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
                    ListView {
                        Layout.fillWidth: true
                        implicitHeight: contentHeight
                        model: bridge.securityRows
                        interactive: false
                        spacing: 10
                        delegate: Column {
                            required property var modelData
                            width: ListView.view.width
                            spacing: 2
                            Label {
                                width: parent.width
                                text: modelData.name
                                color: lpv.subtext
                                font.pixelSize: 12
                                font.bold: true
                                font.family: lpv.uiFamily
                            }
                            Label {
                                width: parent.width
                                text: modelData.value
                                color: lpv.text
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                font.family: lpv.uiFamily
                            }
                            Label {
                                width: parent.width
                                text: modelData.detail
                                color: lpv.subtext
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                font.family: lpv.uiFamily
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.bottomMargin: 24
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                implicitHeight: danger.implicitHeight + 32
                ColumnLayout {
                    id: danger
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Danger zone"; color: lpv.danger; font.bold: true; font.pixelSize: 16 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "Lock the vault. This clears the master password from memory and the clipboard."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    LpvButton { text: "Lock vault"; variant: "danger"; onClicked: bridge.requestLockConfirm() }
                }
            }
        }
    }

    FileDialog {
        id: saveExport
        title: "Save encrypted export"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Encrypted JSON (*.json)"]
        defaultSuffix: "json"
        onAccepted: bridge.exportVault(bridge.localPath(selectedFile.toString()), expPw.text, expPw2.text)
    }
    FileDialog {
        id: openImport
        title: "Open encrypted export"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Encrypted JSON (*.json)"]
        onAccepted: bridge.importVault(bridge.localPath(selectedFile.toString()), expPw.text)
    }

    Component.onCompleted: idleField.text = bridge.idleMinutesValue
}
