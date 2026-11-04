import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string variant: "accent"
    property bool alignLeft: false
    property bool compact: false
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    padding: compact ? 4 : 8
    leftPadding: alignLeft ? 14 : (compact ? 10 : 16)
    rightPadding: compact ? 10 : 16
    implicitHeight: compact ? 32 : 40
    font.family: lpv.uiFamily
    font.pixelSize: compact ? 12 : 13
    font.bold: variant === "accent" || variant === "primary" || variant === "danger"
    Accessible.name: text
    Accessible.role: Accessible.Button

    readonly property bool quiet: variant === "ghost" || variant === "nav" || variant === "navOn"
    readonly property bool outlined: variant === "dangerQuiet"
    readonly property color fill: {
        if (!enabled)
            return quiet || outlined ? "transparent" : lpv.surface3
        if (variant === "navOn")
            return lpv.primarySoft
        if (variant === "primary")
            return (hovered || down) ? Qt.darker(lpv.primary, 1.18) : lpv.primary
        if (variant === "danger")
            return (hovered || down) ? Qt.darker(lpv.danger, 1.12) : lpv.danger
        if (outlined)
            return (hovered || down) ? lpv.dangerSoft : "transparent"
        if (quiet)
            return (hovered || down) ? lpv.surface3 : "transparent"
        return (hovered || down) ? lpv.accent2 : lpv.accent
    }
    readonly property color ink: {
        if (!enabled)
            return lpv.subtext
        if (variant === "navOn")
            return lpv.text
        if (variant === "nav")
            return hovered ? lpv.text : lpv.subtext
        if (variant === "primary")
            return lpv.onPrimary
        if (variant === "danger")
            return lpv.onDanger
        if (outlined)
            return lpv.danger
        if (variant === "ghost")
            return lpv.text
        return lpv.onAccent
    }

    contentItem: Text {
        text: control.text
        color: control.ink
        font: control.font
        horizontalAlignment: control.alignLeft ? Text.AlignLeft : Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        leftPadding: (control.variant === "nav" || control.variant === "navOn") ? 8 : 0
    }

    background: Rectangle {
        radius: control.compact ? 8 : 10
        antialiasing: true
        color: control.fill
        border.width: 2
        border.color: {
            if (!control.enabled)
                return "transparent"
            if (control.activeFocus)
                return lpv.ring
            if (control.outlined)
                return lpv.danger
            if (control.variant === "primary" && lpv.mode === "dark")
                return Qt.rgba(1, 1, 1, 0.28)
            return "transparent"
        }

        Rectangle {
            visible: control.variant === "navOn"
            width: 3
            height: Math.max(12, parent.height - 16)
            anchors.left: parent.left
            anchors.leftMargin: 7
            anchors.verticalCenter: parent.verticalCenter
            radius: 2
            color: lpv.accent
            antialiasing: true
        }

        Behavior on color {
            enabled: lpv && !lpv.reduceMotion
            ColorAnimation { duration: 180 }
        }
    }

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
}
