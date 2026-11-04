import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    Dialog {
        id: setupDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 560
        padding: 24
        visible: bridge.setupOpen
        closePolicy: Popup.CloseOnEscape
        standardButtons: Dialog.NoButton
        onRejected: bridge.cancelSetup()
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }

        contentItem: ColumnLayout {
            spacing: 10
            Label {
                text: bridge.setupPage === 0 ? "Step 1 of 3 — Scan into Authenticator"
                    : bridge.setupPage === 1 ? "Step 2 of 3 — Verify it works"
                    : "Step 3 of 3 — Save your recovery codes"
                color: lpv.accent
                font.bold: true
                font.pixelSize: 16
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            ColumnLayout {
                visible: bridge.setupPage === 0
                Layout.fillWidth: true
                spacing: 8
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: lpv.subtext
                    text: "Open your authenticator app, add an account, and scan the code below."
                }
                QrGrid { Layout.alignment: Qt.AlignHCenter; cell: 5 }
                Label { text: "Or enter the key manually in your app:"; color: lpv.subtext; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: bridge.setupSecret
                        color: lpv.accent
                        font.family: lpv.monoFamily
                        font.bold: true
                        font.pixelSize: 13
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                    LpvButton {
                        text: secretCopied ? "Copied" : "Copy"
                        variant: "ghost"
                        onClicked: {
                            if (bridge.copyText(bridge.setupSecret)) {
                                secretCopied = true
                                secretTimer.restart()
                            }
                        }
                        property bool secretCopied: false
                        Timer { id: secretTimer; interval: 1200; onTriggered: parent.secretCopied = false }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    LpvButton { text: "Cancel"; variant: "ghost"; onClicked: bridge.cancelSetup() }
                    Item { Layout.fillWidth: true }
                    LpvButton { text: "Next — Verify code"; onClicked: bridge.setupAdvance() }
                }
            }

            ColumnLayout {
                visible: bridge.setupPage === 1
                Layout.fillWidth: true
                spacing: 8
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: lpv.subtext
                    text: "Enter the 6-digit code now showing in your authenticator app."
                }
                LpvField {
                    id: verifyField
                    Layout.fillWidth: true
                    label: "Authenticator Code"
                    placeholderText: "000 000"
                    mono: true
                    onAccepted: bridge.verifySetup(text)
                }
                Label {
                    visible: bridge.setupError !== ""
                    text: bridge.setupError
                    color: lpv.danger
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    LpvButton { text: "Back"; variant: "ghost"; onClicked: bridge.setupBack() }
                    Item { Layout.fillWidth: true }
                    LpvButton { text: "Verify"; onClicked: bridge.verifySetup(verifyField.text) }
                }
            }

            ColumnLayout {
                visible: bridge.setupPage === 2
                Layout.fillWidth: true
                spacing: 8
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: lpv.danger
                    font.bold: true
                    text: "These 10 codes are your backup if you lose your phone. Each can be used once. Store them somewhere safe. They will not be shown again."
                }
                Label {
                    Layout.fillWidth: true
                    color: lpv.accent
                    font.family: lpv.monoFamily
                    font.bold: true
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    text: bridge.setupCodesText()
                }
                LpvButton {
                    text: codesCopied ? "Copied" : "Copy all codes"
                    variant: "ghost"
                    onClicked: {
                        if (bridge.copyText(bridge.setupCodesText())) {
                            codesCopied = true
                            codesTimer.restart()
                        }
                    }
                    property bool codesCopied: false
                    Timer { id: codesTimer; interval: 1200; onTriggered: parent.codesCopied = false }
                }
                LpvCheck { id: saved; text: "I have saved my recovery codes" }
                Label {
                    visible: bridge.setupError !== ""
                    text: bridge.setupError
                    color: lpv.danger
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                LpvButton {
                    Layout.fillWidth: true
                    text: bridge.busy ? "Working…" : "Done — 2FA is active"
                    enabled: !bridge.busy
                    onClicked: bridge.finishSetup(saved.checked)
                }
            }
        }
    }

    Dialog {
        id: transferDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 460
        padding: 24
        visible: bridge.transferOpen
        closePolicy: Popup.CloseOnEscape
        standardButtons: Dialog.NoButton
        onRejected: bridge.closeTransfer()
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }
        contentItem: ColumnLayout {
            spacing: 10
            Label { text: "Transfer authenticator"; color: lpv.text; font.bold: true; font.pixelSize: 16 }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: lpv.subtext
                text: "Scan this QR code into your new authenticator app. Both apps will then generate the same codes."
            }
            QrGrid { Layout.alignment: Qt.AlignHCenter; cell: 5 }
            Label { text: "Manual key:"; color: lpv.subtext; font.pixelSize: 12 }
            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: bridge.transferSecret
                    color: lpv.accent
                    font.family: lpv.monoFamily
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideMiddle
                }
                LpvButton {
                    text: "Copy"
                    variant: "ghost"
                    onClicked: bridge.copyText(bridge.transferSecret)
                }
            }
            LpvButton { Layout.fillWidth: true; text: "Close"; onClicked: bridge.closeTransfer() }
        }
    }

    Dialog {
        id: codesDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 480
        padding: 24
        visible: bridge.codesOpen
        closePolicy: Popup.NoAutoClose
        standardButtons: Dialog.NoButton
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }
        contentItem: ColumnLayout {
            spacing: 10
            Label {
                text: bridge.codesRegenerated ? "Recovery codes regenerated" : "Recovery codes"
                color: lpv.text
                font.bold: true
                font.pixelSize: 16
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: lpv.danger
                font.bold: true
                text: bridge.codesRegenerated
                      ? "Each code can be used once. Save them somewhere safe. Old codes are now invalid."
                      : "Each code can be used once to bypass the authenticator. Save them somewhere safe — they will not be shown again."
            }
            Label {
                Layout.fillWidth: true
                color: lpv.accent
                font.family: lpv.monoFamily
                font.bold: true
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                text: bridge.issuedCodesText()
            }
            LpvButton {
                text: "Copy all codes"
                variant: "ghost"
                onClicked: bridge.copyText(bridge.issuedCodesText())
            }
            LpvButton { Layout.fillWidth: true; text: "Close"; onClicked: bridge.closeIssuedCodes() }
        }
    }

    Dialog {
        id: actionDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 460
        padding: 24
        visible: bridge.codeActionOpen
        closePolicy: Popup.CloseOnEscape
        standardButtons: Dialog.NoButton
        onRejected: bridge.closeCodeAction()
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }
        contentItem: ColumnLayout {
            spacing: 8
            Label {
                text: bridge.codeActionTitle
                color: bridge.codeActionDanger ? lpv.danger : lpv.accent
                font.bold: true
                font.pixelSize: 16
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Label {
                text: bridge.codeActionBody
                color: lpv.subtext
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            LpvField {
                id: actionCode
                Layout.fillWidth: true
                label: "Authenticator Code"
                placeholderText: "000 000"
                mono: true
                onAccepted: bridge.submitCodeAction(text)
            }
            Label {
                visible: bridge.codeActionError !== ""
                text: bridge.codeActionError
                color: lpv.danger
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                LpvButton { text: "Cancel"; variant: "ghost"; onClicked: bridge.closeCodeAction() }
                Item { Layout.fillWidth: true }
                LpvButton {
                    text: bridge.busy ? "Working…" : bridge.codeActionButton
                    variant: bridge.codeActionDanger ? "danger" : "accent"
                    enabled: !bridge.busy
                    onClicked: bridge.submitCodeAction(actionCode.text)
                }
            }
        }
    }

    Dialog {
        id: disableDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 480
        padding: 24
        visible: bridge.disableOpen
        closePolicy: Popup.CloseOnEscape
        standardButtons: Dialog.NoButton
        onRejected: bridge.closeDisable2fa()
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }
        contentItem: ColumnLayout {
            spacing: 8
            Label {
                text: "Disable two-factor authentication"
                color: lpv.danger
                font.bold: true
                font.pixelSize: 16
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: lpv.subtext
                text: "This will delete localpasswordvault.2fa and remove 2FA protection. Your vault will be protected by the master password only."
            }
            LpvField {
                id: disableCode
                Layout.fillWidth: true
                label: "Authenticator Code"
                placeholderText: "000 000"
                mono: true
            }
            LpvField {
                id: disableWord
                Layout.fillWidth: true
                label: "Type DISABLE to confirm"
                placeholderText: "DISABLE"
                onAccepted: bridge.submitDisable2fa(disableCode.text, text)
            }
            Label {
                visible: bridge.disableError !== ""
                text: bridge.disableError
                color: lpv.danger
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                LpvButton { text: "Cancel"; variant: "ghost"; onClicked: bridge.closeDisable2fa() }
                Item { Layout.fillWidth: true }
                LpvButton {
                    text: "Disable 2FA"
                    variant: "danger"
                    onClicked: bridge.submitDisable2fa(disableCode.text, disableWord.text)
                }
            }
        }
    }
}
