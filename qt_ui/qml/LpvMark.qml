import QtQuick

// Lock mark. The shackle is the top of a circle, clipped so the body covers the legs.
Item {
    id: root
    implicitWidth: 36
    implicitHeight: 36
    Accessible.ignored: true

    Rectangle {
        anchors.fill: parent
        radius: width * 0.28
        color: lpv.primary
        antialiasing: true
    }

    Item {
        id: shackleClip
        width: parent.width * 0.44
        height: parent.height * 0.30
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: parent.height * 0.15
        clip: true

        Rectangle {
            width: parent.width
            height: parent.width
            radius: width / 2
            color: "transparent"
            border.color: lpv.onPrimary
            border.width: Math.max(2, root.width * 0.07)
            antialiasing: true
        }
    }

    Rectangle {
        width: parent.width * 0.58
        height: parent.height * 0.40
        radius: root.width * 0.12
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: parent.height * 0.15
        color: lpv.accent
        antialiasing: true

        Rectangle {
            width: Math.max(3, parent.width * 0.16)
            height: width
            radius: width / 2
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -height * 0.15
            color: lpv.onPrimary
            antialiasing: true
        }
    }
}
