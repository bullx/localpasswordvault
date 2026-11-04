import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property int score: 0
    property string label: ""
    property color barColor: lpv.subtext
    spacing: 4
    Layout.fillWidth: true

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 6
        radius: 3
        color: lpv.surface3
        clip: true
        antialiasing: true
        Accessible.ignored: true
        Rectangle {
            width: parent.width * Math.max(0, Math.min(100, root.score)) / 100
            height: parent.height
            radius: 3
            color: root.barColor
            antialiasing: true
        }
    }

    Label {
        text: root.label === "" ? "" : root.label + (root.score > 0 ? "  ·  " + root.score : "")
        visible: root.label !== ""
        color: root.barColor
        font.family: lpv.uiFamily
        font.pixelSize: 12
        font.bold: true
        Accessible.name: root.label
    }
}
