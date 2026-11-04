import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    spacing: 10
    font.family: lpv.uiFamily
    font.pixelSize: 13
    hoverEnabled: true
    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        y: control.height / 2 - height / 2
        radius: 5
        antialiasing: true
        color: control.checked ? lpv.accent : lpv.inputBg
        border.width: 1
        border.color: control.activeFocus ? lpv.ring : (control.checked ? lpv.accent : lpv.border)
        Canvas {
            id: tick
            anchors.fill: parent
            anchors.margins: 3
            visible: control.checked
            onVisibleChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)
                ctx.strokeStyle = lpv.onAccent
                ctx.lineWidth = 2
                ctx.lineCap = "round"
                ctx.lineJoin = "round"
                ctx.beginPath()
                ctx.moveTo(width * 0.18, height * 0.52)
                ctx.lineTo(width * 0.42, height * 0.76)
                ctx.lineTo(width * 0.84, height * 0.26)
                ctx.stroke()
            }
            Connections {
                target: lpv
                function onChanged() { tick.requestPaint() }
            }
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
