import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: root
    property string mode: "encrypt"

    function levelColor(level) {
        return lpv.subtext
    }

    Connections {
        target: bridge
        function onTextReady(output) {
            result.text = output
        }
    }

    Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight + 48
        clip: true

        ColumnLayout {
            id: column
            width: Math.min(parent.width, 840)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.topMargin: 24
                Label {
                    text: "Text and file encryption"
                    color: lpv.text
                    font.pixelSize: 20
                    font.bold: true
                    font.family: lpv.uiFamily
                }
                Label {
                    text: "Argon2id · AES-256-GCM"
                    color: lpv.subtext
                    font.pixelSize: 12
                }
            }

            RowLayout {
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 12
                Label { text: "Operation"; color: lpv.subtext; font.pixelSize: 12 }
                Rectangle {
                    radius: 10
                    color: lpv.surface2
                    border.color: lpv.border
                    border.width: 1
                    antialiasing: true
                    implicitWidth: modeRow.implicitWidth + 8
                    implicitHeight: 48
                    RowLayout {
                        id: modeRow
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 4
                        LpvButton {
                            text: "Encrypt"
                            variant: root.mode === "encrypt" ? "primary" : "ghost"
                            onClicked: root.mode = "encrypt"
                        }
                        LpvButton {
                            text: "Decrypt"
                            variant: root.mode === "decrypt" ? "primary" : "ghost"
                            onClicked: root.mode = "decrypt"
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                implicitHeight: passCol.implicitHeight + 32
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                ColumnLayout {
                    id: passCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    SecretField {
                        id: phrase
                        Layout.fillWidth: true
                        label: "Passphrase"
                        placeholderText: "Passphrase for this encryption"
                        onTextChanged: {
                            var info = bridge.strength(text)
                            meter.score = info.score
                            meter.label = info.label
                            meter.barColor = info.color
                        }
                    }
                    StrengthMeter { id: meter; Layout.fillWidth: true }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                implicitHeight: inCol.implicitHeight + 32
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                ColumnLayout {
                    id: inCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    LpvArea {
                        id: input
                        Layout.fillWidth: true
                        label: "Input"
                        mono: true
                        ink: lpv.inputFg
                        lineCount: 6
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                LpvButton {
                    text: bridge.busy ? "Working…" : (root.mode === "encrypt" ? "Encrypt text" : "Decrypt text")
                    variant: root.mode === "encrypt" ? "accent" : "primary"
                    enabled: !bridge.busy
                    onClicked: bridge.encryptText(phrase.text, input.text, root.mode === "encrypt")
                }
                LpvButton {
                    text: "Swap"
                    variant: "ghost"
                    onClicked: {
                        var out = result.text.trim()
                        if (!out)
                            return
                        input.text = out
                        root.mode = root.mode === "encrypt" ? "decrypt" : "encrypt"
                    }
                }
                LpvButton {
                    text: "Clear"
                    variant: "ghost"
                    onClicked: {
                        input.text = ""
                        result.text = ""
                    }
                }
                Item { Layout.fillWidth: true }
                LpvButton {
                    text: copied ? "Copied" : "Copy output"
                    variant: "ghost"
                    onClicked: {
                        if (bridge.copyText(result.text.trim())) {
                            copied = true
                            copyTimer.restart()
                        }
                    }
                    property bool copied: false
                    Timer { id: copyTimer; interval: 1200; onTriggered: parent.copied = false }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                implicitHeight: fileCol.implicitHeight + 32
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                ColumnLayout {
                    id: fileCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "File mode"; color: lpv.text; font.bold: true; font.pixelSize: 14 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "Encrypts any file. Output is a binary LPVF envelope, not a text token."
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Input"; color: lpv.subtext; font.pixelSize: 12; Layout.preferredWidth: 70 }
                        LpvField { id: inPath; Layout.fillWidth: true }
                        LpvButton { text: "Browse"; variant: "ghost"; onClicked: openIn.open() }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Output"; color: lpv.subtext; font.pixelSize: 12; Layout.preferredWidth: 70 }
                        LpvField { id: outPath; Layout.fillWidth: true }
                        LpvButton { text: "Browse"; variant: "ghost"; onClicked: openOut.open() }
                    }
                    RowLayout {
                        LpvButton {
                            text: "Encrypt file"
                            enabled: !bridge.busy
                            onClicked: bridge.encryptFile(phrase.text, inPath.text, outPath.text, true)
                        }
                        LpvButton {
                            text: "Decrypt file"
                            variant: "primary"
                            enabled: !bridge.busy
                            onClicked: bridge.encryptFile(phrase.text, inPath.text, outPath.text, false)
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                implicitHeight: outCol.implicitHeight + 32
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                ColumnLayout {
                    id: outCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    LpvArea {
                        id: result
                        Layout.fillWidth: true
                        label: root.mode === "encrypt" ? "Output — encrypted token" : "Output — decrypted text"
                        mono: true
                        ink: lpv.text
                        lineCount: 6
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.bottomMargin: 24
                implicitHeight: infoCol.implicitHeight + 24
                color: lpv.surface2
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                ColumnLayout {
                    id: infoCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    Label { text: "Encryption details"; color: lpv.accent; font.bold: true; font.pixelSize: 12 }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: lpv.subtext
                        font.pixelSize: 12
                        text: "Text: Argon2id + AES-256-GCM, fresh salt and nonce, base64 token.\nFiles: one Argon2id derivation, then 1 MiB authenticated chunks.\nVault entries use a separate data key. This passphrase is not the master password."
                    }
                }
            }
        }
    }

    FileDialog {
        id: openIn
        title: "Input file"
        fileMode: FileDialog.OpenFile
        onAccepted: inPath.text = bridge.localPath(selectedFile.toString())
    }
    FileDialog {
        id: openOut
        title: "Output file"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "lpv"
        onAccepted: outPath.text = bridge.localPath(selectedFile.toString())
    }
}
