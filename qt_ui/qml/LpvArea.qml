import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property alias text: area.text
    property string label: ""
    property string placeholderText: ""
    property bool mono: false
    property int lineCount: 6
    property color ink: lpv.inputFg
    spacing: 4

    Label {
        text: root.label
        visible: root.label !== ""
        color: lpv.subtext
        font.family: lpv.uiFamily
        font.pixelSize: 12
        Layout.fillWidth: true
        Accessible.ignored: true
    }

    TextArea {
        id: area
        Layout.fillWidth: true
        implicitHeight: Math.max(96, root.lineCount * 22)
        selectByMouse: true
        wrapMode: TextArea.Wrap
        placeholderText: root.placeholderText
        placeholderTextColor: lpv.inputPh
        color: root.ink
        font.family: root.mono ? lpv.monoFamily : lpv.uiFamily
        font.pixelSize: 14
        Accessible.name: root.label !== "" ? root.label : root.placeholderText
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
                border.width: area.activeFocus ? 1 : 0
                border.color: lpv.ring
                antialiasing: true
            }
        }
    }
}
