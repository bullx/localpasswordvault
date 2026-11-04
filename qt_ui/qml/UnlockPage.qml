import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    function levelColor(level) {
        if (level === "danger")
            return lpv.danger
        if (level === "success")
            return lpv.success
        return lpv.subtext
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 48)
        spacing: 8

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 12
            LpvMark {
                width: 40
                height: 40
            }
            ColumnLayout {
                spacing: 0
                Label {
                    text: "LocalPasswordVault"
                    color: lpv.text
                    font.family: lpv.uiFamily
                    font.pixelSize: 22
                    font.bold: true
                    Accessible.role: Accessible.Heading
                }
                Label {
                    text: "Argon2id and AES-256-GCM. Nothing leaves this computer."
                    color: lpv.subtext
                    font.family: lpv.uiFamily
                    font.pixelSize: 12
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.topMargin: 8
            implicitHeight: cardShell.implicitHeight + 10

            Rectangle {
                x: 0
                y: 8
                width: cardShell.width
                height: cardShell.height
                radius: 16
                color: lpv.mode === "dark" ? "#000000" : lpv.text
                opacity: lpv.mode === "dark" ? 0.40 : 0.08
                antialiasing: true
            }

            Rectangle {
                id: cardShell
                width: parent.width
                implicitHeight: card.implicitHeight + 56
                color: lpv.surface
                radius: 16
                border.color: lpv.border
                border.width: 1
                antialiasing: true

            ColumnLayout {
                id: card
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 28
                spacing: 8

                // Damaged vault
                ColumnLayout {
                    visible: bridge.screen === "corrupt"
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Vault file is damaged"
                        color: lpv.danger
                        font.bold: true
                        font.pixelSize: 16
                        font.family: lpv.uiFamily
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        font.family: lpv.uiFamily
                        text: "The vault database exists but has no password set. No master or recovery password can unlock it. This usually happens after a failed setup or migration. Your entries are not in this file (it is empty)."
                    }
                    LpvButton {
                        visible: bridge.backupHasPassword
                        text: "Restore from backup"
                        variant: "ghost"
                        alignLeft: true
                        onClicked: bridge.requestRestoreCorrupt()
                    }
                    LpvButton {
                        Layout.fillWidth: true
                        text: "Create a new vault"
                        variant: "accent"
                        onClicked: bridge.requestResetDamaged()
                    }
                }

                // Create
                ColumnLayout {
                    visible: bridge.screen === "create"
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Create your vault"
                        color: lpv.text
                        font.bold: true
                        font.pixelSize: 16
                        font.family: lpv.uiFamily
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "Master password is never stored — only its derived key is used."
                    }
                    SecretField {
                        id: createPw
                        Layout.fillWidth: true
                        label: "Master Password"
                        placeholderText: "Choose a strong master password"
                        onTextChanged: root._paintStrength(text, createMeter)
                        onAccepted: createPw2.forceField()
                    }
                    SecretField {
                        id: createPw2
                        Layout.fillWidth: true
                        label: "Confirm Master Password"
                        placeholderText: "Confirm master password"
                        onAccepted: createRec.forceField()
                    }
                    StrengthMeter { id: createMeter; Layout.fillWidth: true }
                    Label {
                        text: "Recovery Passphrase (optional but strongly recommended)"
                        color: lpv.text
                        font.bold: true
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "A second passphrase that can unlock the vault if you forget the master. Choose something memorable. It is never stored. If you skip this, there is no fallback."
                    }
                    SecretField {
                        id: createRec
                        Layout.fillWidth: true
                        label: "Recovery Passphrase"
                        placeholderText: "e.g. My dog Biscuit was born in 2015"
                    }
                    SecretField {
                        id: createRec2
                        Layout.fillWidth: true
                        label: "Confirm Recovery Passphrase"
                        placeholderText: "Confirm recovery passphrase"
                        onAccepted: root._submitCreate()
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        visible: bridge.notice !== "" && bridge.screen === "create"
                        text: bridge.notice
                        color: root.levelColor(bridge.noticeLevel)
                        font.pixelSize: 12
                        Accessible.role: Accessible.AlertMessage
                    }
                    LpvButton {
                        Layout.fillWidth: true
                        text: bridge.busy ? "Working…" : "Create Vault"
                        enabled: !bridge.busy
                        onClicked: root._submitCreate()
                    }
                    BusyIndicator {
                        visible: bridge.busy && bridge.screen === "create"
                        running: visible && !lpv.reduceMotion
                        Layout.alignment: Qt.AlignHCenter
                    }
                }

                // Password
                ColumnLayout {
                    visible: bridge.screen === "unlock"
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Unlock your vault"
                        color: lpv.text
                        font.bold: true
                        font.pixelSize: 16
                        font.family: lpv.uiFamily
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: bridge.twoFaFile
                              ? "Enter master password, then verify with your Authenticator app. Recovery passphrase skips 2FA but requires setting a new master."
                              : "Enter master password OR recovery passphrase."
                    }
                    SecretField {
                        id: unlockPw
                        Layout.fillWidth: true
                        label: "Password / Recovery Passphrase"
                        placeholderText: "Master password or recovery passphrase"
                        onAccepted: bridge.submitUnlock(text)
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        visible: bridge.notice !== "" && bridge.screen === "unlock"
                        text: bridge.notice
                        color: root.levelColor(bridge.noticeLevel)
                        font.pixelSize: 12
                        Accessible.role: Accessible.AlertMessage
                    }
                    LpvButton {
                        Layout.fillWidth: true
                        text: bridge.busy ? "Working…" : (bridge.twoFaFile ? "Next" : "Unlock Vault")
                        enabled: !bridge.busy
                        onClicked: bridge.submitUnlock(unlockPw.text)
                    }
                    BusyIndicator {
                        visible: bridge.busy && bridge.screen === "unlock"
                        running: visible && !lpv.reduceMotion
                        Layout.alignment: Qt.AlignHCenter
                    }
                    ColumnLayout {
                        visible: bridge.backupAvailable
                        Layout.fillWidth: true
                        spacing: 6
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: lpv.border }
                        Label {
                            text: "Vault file corrupted? Use backup:"
                            color: lpv.subtext
                            font.pixelSize: 12
                        }
                        LpvButton {
                            text: "Restore from backup"
                            variant: "ghost"
                            alignLeft: true
                            enabled: !bridge.busy
                            onClicked: bridge.restoreBackup(unlockPw.text)
                        }
                    }
                }

                // TOTP
                ColumnLayout {
                    visible: bridge.screen === "totp"
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Two-Factor Verification"
                        color: lpv.text
                        font.bold: true
                        font.pixelSize: 16
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "Enter the 6-digit code from your Authenticator app."
                    }
                    LpvField {
                        id: otp
                        Layout.fillWidth: true
                        label: "Authenticator Code"
                        placeholderText: "000 000"
                        mono: true
                        onAccepted: bridge.submitTotp(text)
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        visible: bridge.notice !== "" && bridge.screen === "totp"
                        text: bridge.notice
                        color: root.levelColor(bridge.noticeLevel)
                        font.pixelSize: 12
                    }
                    LpvButton {
                        Layout.fillWidth: true
                        text: "Verify & Unlock"
                        enabled: !bridge.busy
                        onClicked: bridge.submitTotp(otp.text)
                    }
                    Label { text: "Lost phone?"; font.bold: true; color: lpv.subtext; font.pixelSize: 12 }
                    LpvButton {
                        text: "Use a recovery code instead"
                        variant: "ghost"
                        alignLeft: true
                        onClicked: bridge.showRecoveryCodeStep()
                    }
                    LpvButton {
                        text: "Back"
                        variant: "ghost"
                        alignLeft: true
                        onClicked: bridge.backToPassword()
                    }
                }

                // Recovery code
                ColumnLayout {
                    visible: bridge.screen === "recovery_code"
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Recovery Code"
                        color: lpv.text
                        font.bold: true
                        font.pixelSize: 16
                    }
                    Label {
                        visible: !bridge.unlockCodesOn
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.danger
                        font.pixelSize: 12
                        text: "Recovery codes are disabled for this vault. Re-enable them from Settings after you unlock with the authenticator."
                    }
                    Label {
                        visible: bridge.unlockCodesOn
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "Enter one of your 10 recovery codes (" + bridge.unlockCodesLeft + " remaining). Each code can only be used once."
                    }
                    LpvField {
                        id: recCode
                        visible: bridge.unlockCodesOn
                        Layout.fillWidth: true
                        label: "Recovery Code (e.g. A3KP-9XMZ-Q72W)"
                        placeholderText: "XXXX-XXXX-XXXX"
                        mono: true
                        onAccepted: bridge.submitRecoveryCode(text)
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        visible: bridge.notice !== "" && bridge.screen === "recovery_code"
                        text: bridge.notice
                        color: root.levelColor(bridge.noticeLevel)
                        font.pixelSize: 12
                    }
                    LpvButton {
                        visible: bridge.unlockCodesOn
                        Layout.fillWidth: true
                        text: bridge.busy ? "Working…" : "Unlock with Recovery Code"
                        enabled: !bridge.busy
                        onClicked: bridge.submitRecoveryCode(recCode.text)
                    }
                    LpvButton {
                        text: "Back to Authenticator"
                        variant: "ghost"
                        alignLeft: true
                        onClicked: bridge.showTotpStep()
                    }
                }

                // Forced new master
                ColumnLayout {
                    visible: bridge.screen === "reset_master"
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Set a new master password"
                        color: lpv.text
                        font.bold: true
                        font.pixelSize: 16
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "You unlocked with the recovery passphrase. Choose a new master password before opening the vault. Your entries stay encrypted; only the unlock secrets change."
                    }
                    SecretField {
                        id: newMaster
                        Layout.fillWidth: true
                        label: "New Master Password"
                        placeholderText: "New master password"
                        onTextChanged: root._paintStrength(text, resetMeter)
                    }
                    SecretField {
                        id: newMaster2
                        Layout.fillWidth: true
                        label: "Confirm New Master Password"
                        placeholderText: "Confirm new master password"
                        onAccepted: bridge.submitNewMaster(newMaster.text, text)
                    }
                    StrengthMeter { id: resetMeter; Layout.fillWidth: true }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        visible: bridge.notice !== "" && bridge.screen === "reset_master"
                        text: bridge.notice
                        color: root.levelColor(bridge.noticeLevel)
                        font.pixelSize: 12
                    }
                    LpvButton {
                        Layout.fillWidth: true
                        text: bridge.busy ? "Working…" : "Save master & open vault"
                        enabled: !bridge.busy
                        onClicked: bridge.submitNewMaster(newMaster.text, newMaster2.text)
                    }
                }
            }
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            elide: Text.ElideMiddle
            maximumLineCount: 2
            horizontalAlignment: Text.AlignHCenter
            color: lpv.subtext
            font.pixelSize: 11
            font.family: lpv.uiFamily
            text: bridge.footerLine
        }
    }

    function _paintStrength(secret, meter) {
        var info = bridge.strength(secret)
        meter.score = info.score
        meter.label = info.label
        meter.barColor = info.color
    }

    function _submitCreate() {
        bridge.submitCreate(createPw.text, createPw2.text, createRec.text, createRec2.text)
    }

    property string seen: ""
    Connections {
        target: bridge
        function onStateChanged() {
            if (bridge.screen === root.seen)
                return
            root.seen = bridge.screen
            if (bridge.screen === "unlock")
                unlockPw.forceField()
            else if (bridge.screen === "create")
                createPw.forceField()
            else if (bridge.screen === "totp")
                otp.forceField()
            else if (bridge.screen === "recovery_code" && bridge.unlockCodesOn)
                recCode.forceField()
            else if (bridge.screen === "reset_master")
                newMaster.forceField()
        }
    }

    Component.onCompleted: {
        seen = bridge.screen
        if (bridge.screen === "unlock")
            unlockPw.forceField()
        else if (bridge.screen === "create")
            createPw.forceField()
    }
}
