import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property alias text: field.text
    property alias placeholderText: field.placeholderText
    property alias echoMode: field.echoMode
    property alias readOnly: field.readOnly
    property string label: ""
    property bool mono: false
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

    TextField {
        id: field
        Layout.fillWidth: true
        implicitHeight: 44
        leftPadding: 14
        rightPadding: 14
        selectByMouse: true
        placeholderTextColor: lpv.inputPh
        color: lpv.inputFg
        font.family: root.mono ? lpv.monoFamily : lpv.uiFamily
        font.pixelSize: 14
        Accessible.name: root.label !== "" ? root.label : placeholderText
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
}
