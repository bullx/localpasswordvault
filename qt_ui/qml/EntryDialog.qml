import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    parent: Overlay.overlay
    modal: true
    anchors.centerIn: parent
    width: 560
    height: Math.min(720, Overlay.overlay ? Overlay.overlay.height - 48 : 720)
    padding: 20
    standardButtons: Dialog.NoButton
    closePolicy: Popup.CloseOnEscape
    title: ""

    property string editing: ""

    background: Rectangle {
        color: lpv.surface
        radius: 14
        border.color: lpv.border
        border.width: 1
        antialiasing: true
    }

    header: Label {
        text: dialog.editing ? "Edit entry" : "Add entry"
        color: lpv.text
        font.bold: true
        font.pixelSize: 16
        font.family: lpv.uiFamily
        leftPadding: 20
        topPadding: 16
        Accessible.role: Accessible.Heading
    }

    function openFor(eid) {
        editing = eid || ""
        var row = eid ? bridge.entry(eid) : {}
        titleField.text = row.title || ""
        userField.text = row.username || ""
        pwField.text = row.password || ""
        urlField.text = row.url || ""
        notesField.text = row.notes || ""
        totpField.text = row.totp_secret || ""
        if (!eid) {
            var draft = bridge.takeDraftPassword()
            if (draft)
                pwField.text = draft
        }
        errorText.text = ""
        paintStrength()
        paintTotp()
        open()
        titleField.forceField()
    }

    function paintStrength() {
        var info = bridge.strength(pwField.text)
        meter.score = info.score
        meter.label = info.label
        meter.barColor = info.color
    }

    function paintTotp() {
        var info = bridge.totpStatus(totpField.text)
        totpStatus.text = info.text
        totpStatus.color = info.color || lpv.subtext
    }

    contentItem: Flickable {
        clip: true
        contentHeight: form.implicitHeight
        ColumnLayout {
            id: form
            width: dialog.availableWidth
            spacing: 8
            LpvField { id: titleField; Layout.fillWidth: true; label: "Title"; placeholderText: "Title" }
            LpvField { id: userField; Layout.fillWidth: true; label: "Username"; placeholderText: "Username" }
            SecretField {
                id: pwField
                Layout.fillWidth: true
                label: "Password"
                placeholderText: "Password"
                onTextChanged: dialog.paintStrength()
            }
            StrengthMeter { id: meter; Layout.fillWidth: true }
            LpvButton {
                text: "Generate strong password"
                variant: "ghost"
                onClicked: {
                    pwField.text = bridge.generatePassword(20, true, true, true, true, true)
                    dialog.paintStrength()
                }
            }
            LpvField { id: urlField; Layout.fillWidth: true; label: "URL"; placeholderText: "URL" }
            LpvArea { id: notesField; Layout.fillWidth: true; label: "Notes"; lineCount: 4 }
            SecretField {
                id: totpField
                Layout.fillWidth: true
                label: "2FA secret"
                placeholderText: "TOTP secret (base32)"
                onTextChanged: dialog.paintTotp()
            }
            Label {
                id: totpStatus
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: lpv.subtext
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: lpv.subtext
                font.pixelSize: 11
                text: "Paste the secret from the site's 2FA setup. Leave blank if there is none."
            }
            Label {
                id: errorText
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: lpv.danger
                font.pixelSize: 12
                visible: text !== ""
            }
            Timer {
                interval: 1000
                repeat: true
                running: dialog.opened && totpField.text.trim() !== ""
                onTriggered: dialog.paintTotp()
            }
        }
    }

    footer: RowLayout {
        spacing: 8
        Item { Layout.fillWidth: true }
        LpvButton { text: "Cancel"; variant: "ghost"; onClicked: dialog.close() }
        LpvButton {
            text: "Save"
            onClicked: {
                var err = bridge.saveEntry(
                    dialog.editing, titleField.text, userField.text, pwField.text,
                    urlField.text, notesField.text, totpField.text
                )
                if (err)
                    errorText.text = err
                else
                    dialog.close()
            }
        }
    }
}
