import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property alias text: field.text
    property string label: ""
    property string placeholderText: ""
    property bool revealed: false
    signal accepted()
    spacing: 4

    function forceField() {
        field.forceActiveFocus()
    }

    Label {
        text: root.label
        visible: root.label !== ""
        color: lpv.subtext
        font.family: lpv.uiFamily
        font.pixelSize: 12
        Layout.fillWidth: true
        Accessible.ignored: true
    }

    Item {
        Layout.fillWidth: true
        implicitHeight: 44

        TextField {
            id: field
            anchors.fill: parent
            selectByMouse: true
            placeholderText: root.placeholderText
            placeholderTextColor: lpv.inputPh
            color: lpv.inputFg
            echoMode: root.revealed ? TextInput.Normal : TextInput.Password
            font.family: lpv.monoFamily
            font.pixelSize: 14
            leftPadding: 14
            rightPadding: reveal.width + 12
            Accessible.name: root.label !== "" ? root.label : root.placeholderText
            Accessible.description: root.revealed ? "Visible" : "Hidden"
            background: Rectangle {
                radius: 10
                antialiasing: true
                color: lpv.inputBg
                border.width: 1
                border.color: lpv.border
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    radius: 9
                    color: "transparent"
                    border.width: field.activeFocus ? 1 : 0
                    border.color: lpv.ring
                    antialiasing: true
                }
            }
            Keys.onReturnPressed: root.accepted()
            Keys.onEnterPressed: root.accepted()
        }

        LpvButton {
            id: reveal
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            implicitWidth: 58
            text: root.revealed ? "Hide" : "Show"
            variant: "ghost"
            compact: true
            Accessible.name: root.revealed ? "Hide secret" : "Show secret"
            onClicked: root.revealed = !root.revealed
        }
    }
}
