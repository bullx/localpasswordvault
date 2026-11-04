import QtQuick
import QtQuick.Controls

RadioButton {
    id: control
    spacing: 8
    font.family: lpv.uiFamily
    font.pixelSize: 13
    hoverEnabled: true
    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        y: control.height / 2 - height / 2
        radius: 9
        antialiasing: true
        color: lpv.inputBg
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? lpv.ring : (control.checked ? lpv.accent : lpv.border)
        Rectangle {
            visible: control.checked
            width: 8
            height: 8
            radius: 4
            anchors.centerIn: parent
            color: lpv.accent
            antialiasing: true
        }
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: lpv.text
        leftPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
