import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property int cell: 4
    readonly property int modules: bridge.qrRows.length
    color: "white"
    radius: 8
    implicitWidth: Math.max(48, modules * cell + 16)
    implicitHeight: implicitWidth
    border.color: lpv.border
    border.width: 1
    antialiasing: true
    Accessible.name: "Authenticator QR code"
    Accessible.role: Accessible.Graphic

    Canvas {
        id: canvas
        anchors.centerIn: parent
        width: root.modules * root.cell
        height: width
        onWidthChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            if (!ctx)
                return
            ctx.clearRect(0, 0, width, height)
            var rows = bridge.qrRows
            for (var y = 0; y < rows.length; y++) {
                var bits = rows[y]
                for (var x = 0; x < bits.length; x++) {
                    ctx.fillStyle = bits.charAt(x) === "1" ? "#000000" : "#FFFFFF"
                    ctx.fillRect(x * root.cell, y * root.cell, root.cell, root.cell)
                }
            }
        }
    }

    Connections {
        target: bridge
        function onQrChanged() { canvas.requestPaint() }
    }

    Label {
        anchors.centerIn: parent
        width: parent.width - 24
        visible: root.modules === 0
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        color: "#334155"
        text: "QR code is unavailable. Use the manual key below."
    }
}
