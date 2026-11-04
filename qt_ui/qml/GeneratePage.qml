import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property int length: 20
    property var history: []
    property string phrase: ""
    property string bitsText: ""
    property int words: 5

    function paint(secret) {
        var info = bridge.strength(secret)
        meter.score = info.score
        meter.label = info.label
        meter.barColor = info.color
    }

    function generate() {
        var secret = bridge.generatePassword(length, upper.checked, lower.checked, digits.checked, symbols.checked, noAmb.checked)
        output.value = secret
        paint(secret)
        var next = [secret]
        for (var i = 0; i < history.length && next.length < 6; i++) {
            if (history[i] !== secret)
                next.push(history[i])
        }
        history = next
    }

    function generatePhrase() {
        var info = bridge.generatePassphrase(words)
        phrase = info.phrase
        bitsText = info.bitsText
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
                text: "Password generator"
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
                implicitHeight: opt.implicitHeight + 32
                ColumnLayout {
                    id: opt
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Length"; color: lpv.subtext; font.pixelSize: 12 }
                        Label { text: String(root.length); color: lpv.accent; font.bold: true; font.pixelSize: 14 }
                        Slider {
                            id: lengthSlider
                            Layout.fillWidth: true
                            from: 8
                            to: 64
                            stepSize: 1
                            value: 20
                            onValueChanged: root.length = Math.round(value)
                            Accessible.name: "Password length"
                            background: Rectangle {
                                x: lengthSlider.leftPadding
                                y: lengthSlider.topPadding + lengthSlider.availableHeight / 2 - height / 2
                                width: lengthSlider.availableWidth
                                height: 6
                                radius: 3
                                color: lpv.surface3
                                antialiasing: true
                                Rectangle {
                                    width: lengthSlider.visualPosition * parent.width
                                    height: parent.height
                                    radius: 3
                                    color: lpv.accent
                                }
                            }
                            handle: Rectangle {
                                x: lengthSlider.leftPadding + lengthSlider.visualPosition * (lengthSlider.availableWidth - width)
                                y: lengthSlider.topPadding + lengthSlider.availableHeight / 2 - height / 2
                                width: 18
                                height: 18
                                radius: 9
                                color: lpv.surface
                                border.color: lengthSlider.activeFocus ? lpv.ring : lpv.accent
                                border.width: 2
                                antialiasing: true
                            }
                        }
                    }
                    LpvCheck { id: upper; text: "Uppercase"; checked: true; onClicked: root.generate() }
                    LpvCheck { id: lower; text: "Lowercase"; checked: true; onClicked: root.generate() }
                    LpvCheck { id: digits; text: "Digits"; checked: true; onClicked: root.generate() }
                    LpvCheck { id: symbols; text: "Symbols"; checked: true; onClicked: root.generate() }
                    LpvCheck { id: noAmb; text: "No ambiguous characters (0 O 1 l I)"; checked: true; onClicked: root.generate() }
                    LpvButton { text: "Generate password"; onClicked: root.generate() }
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
                implicitHeight: outBox.implicitHeight + 32
                ColumnLayout {
                    id: outBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: output.implicitHeight + 24
                        color: lpv.surface2
                        radius: 10
                        border.color: lpv.border
                        border.width: 1
                        antialiasing: true
                        Label {
                            id: output
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 10
                            wrapMode: Text.WrapAnywhere
                            color: lpv.text
                            font.family: lpv.monoFamily
                            font.pixelSize: 16
                            font.bold: true
                            property string value: ""
                            text: value
                            Accessible.name: "Generated password"
                        }
                    }
                    StrengthMeter { id: meter; Layout.fillWidth: true }
                    RowLayout {
                        LpvButton {
                            text: pwCopied ? "Copied" : "Copy"
                            variant: "ghost"
                            onClicked: {
                                if (bridge.copyText(output.value)) {
                                    pwCopied = true
                                    pwTimer.restart()
                                }
                            }
                            property bool pwCopied: false
                            Timer { id: pwTimer; interval: 1200; onTriggered: parent.pwCopied = false }
                        }
                        LpvButton {
                            text: "Save to vault"
                            variant: "ghost"
                            onClicked: bridge.saveGeneratedToVault(output.value)
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
                implicitHeight: hist.implicitHeight + 32
                ColumnLayout {
                    id: hist
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "History (this session only)"; color: lpv.subtext; font.pixelSize: 12; Layout.fillWidth: true }
                        LpvButton {
                            text: "Clear history"
                            variant: "ghost"
                            onClicked: root.history = []
                        }
                    }
                    Label {
                        visible: root.history.length === 0
                        text: "History is empty."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    ListView {
                        Layout.fillWidth: true
                        implicitHeight: contentHeight
                        model: root.history
                        interactive: false
                        spacing: 4
                        delegate: Item {
                            required property string modelData
                            width: ListView.view.width
                            height: 36
                            Label {
                                anchors.left: parent.left
                                anchors.right: copyBtn.left
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData
                                color: lpv.text
                                font.family: lpv.monoFamily
                                font.pixelSize: 12
                                elide: Text.ElideMiddle
                            }
                            LpvButton {
                                id: copyBtn
                                property bool copied: false
                                compact: true
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: copied ? "Copied" : "Copy"
                                variant: "ghost"
                                onClicked: {
                                    if (bridge.copyText(modelData)) {
                                        copied = true
                                        timer.restart()
                                    }
                                }
                                Timer { id: timer; interval: 1200; onTriggered: copyBtn.copied = false }
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
                implicitHeight: phraseBox.implicitHeight + 32
                ColumnLayout {
                    id: phraseBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8
                    Label { text: "Passphrase generator"; color: lpv.text; font.bold: true; font.pixelSize: 14 }
                    Label {
                        text: "Random words from a " + bridge.wordlistSize + "-word list."
                        color: lpv.subtext
                        font.pixelSize: 12
                    }
                    RowLayout {
                        Label { text: "Words"; color: lpv.subtext; font.pixelSize: 12 }
                        LpvRadio { text: "4"; checked: root.words === 4; onClicked: { root.words = 4; root.generatePhrase() } }
                        LpvRadio { text: "5"; checked: root.words === 5; onClicked: { root.words = 5; root.generatePhrase() } }
                        LpvRadio { text: "6"; checked: root.words === 6; onClicked: { root.words = 6; root.generatePhrase() } }
                        LpvRadio { text: "7"; checked: root.words === 7; onClicked: { root.words = 7; root.generatePhrase() } }
                        LpvRadio { text: "8"; checked: root.words === 8; onClicked: { root.words = 8; root.generatePhrase() } }
                    }
                    LpvButton { text: "Generate passphrase"; onClicked: root.generatePhrase() }
                    Rectangle {
                        Layout.fillWidth: true
                        color: lpv.surface2
                        radius: 10
                        border.color: lpv.border
                        border.width: 1
                        antialiasing: true
                        implicitHeight: phraseLabel.implicitHeight + 24
                        Label {
                            id: phraseLabel
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 10
                            wrapMode: Text.Wrap
                            text: root.phrase
                            color: lpv.text
                            font.family: lpv.monoFamily
                            font.bold: true
                            font.pixelSize: 14
                            Accessible.name: "Generated passphrase"
                        }
                    }
                    Label { text: root.bitsText; color: lpv.subtext; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    RowLayout {
                        LpvButton {
                            text: phraseCopied ? "Copied" : "Copy"
                            variant: "ghost"
                            onClicked: {
                                if (bridge.copyText(root.phrase)) {
                                    phraseCopied = true
                                    phraseTimer.restart()
                                }
                            }
                            property bool phraseCopied: false
                            Timer { id: phraseTimer; interval: 1200; onTriggered: parent.phraseCopied = false }
                        }
                        LpvButton {
                            text: "Save to vault"
                            variant: "ghost"
                            onClicked: bridge.saveGeneratedToVault(root.phrase)
                        }
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        generate()
        generatePhrase()
    }
}
