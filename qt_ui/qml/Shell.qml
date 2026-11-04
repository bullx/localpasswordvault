import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 256
            Layout.fillHeight: true
            color: lpv.surface2

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: lpv.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                anchors.topMargin: 20
                anchors.bottomMargin: 16
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 18
                    spacing: 12

                    LpvMark {
                        width: 36
                        height: 36
                    }

                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Label {
                            text: "LOCAL VAULT"
                            color: lpv.subtext
                            font.family: lpv.uiFamily
                            font.pixelSize: 10
                            font.letterSpacing: 1.2
                        }
                        Label {
                            text: "Password Vault"
                            color: lpv.text
                            font.family: lpv.uiFamily
                            font.pixelSize: 15
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }

                Label {
                    text: bridge.entryCountText
                    color: lpv.subtext
                    font.family: lpv.uiFamily
                    font.pixelSize: 12
                }
                Label {
                    text: bridge.idleLabel
                    color: lpv.subtext
                    font.family: lpv.uiFamily
                    font.pixelSize: 12
                    Layout.bottomMargin: 12
                }

                LpvButton {
                    Layout.fillWidth: true
                    text: "Vault"
                    alignLeft: true
                    variant: bridge.page === "Vault" ? "navOn" : "nav"
                    Accessible.checkable: true
                    Accessible.checked: bridge.page === "Vault"
                    onClicked: bridge.setPage("Vault")
                }
                LpvButton {
                    Layout.fillWidth: true
                    text: "Encrypt"
                    alignLeft: true
                    variant: bridge.page === "Encrypt" ? "navOn" : "nav"
                    Accessible.checkable: true
                    Accessible.checked: bridge.page === "Encrypt"
                    onClicked: bridge.setPage("Encrypt")
                }
                LpvButton {
                    Layout.fillWidth: true
                    text: "Generate"
                    alignLeft: true
                    variant: bridge.page === "Generate" ? "navOn" : "nav"
                    Accessible.checkable: true
                    Accessible.checked: bridge.page === "Generate"
                    onClicked: bridge.setPage("Generate")
                }
                LpvButton {
                    Layout.fillWidth: true
                    text: "Settings"
                    alignLeft: true
                    variant: bridge.page === "Settings" ? "navOn" : "nav"
                    Accessible.checkable: true
                    Accessible.checked: bridge.page === "Settings"
                    onClicked: bridge.setPage("Settings")
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: pathLabel.implicitHeight + 20
                    radius: 10
                    color: lpv.surface
                    border.color: lpv.border
                    border.width: 1
                    antialiasing: true
                    Layout.bottomMargin: 12

                    Label {
                        id: pathLabel
                        property bool pathCopied: false
                        objectName: "vaultPath"
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 12
                        text: pathLabel.pathCopied ? "Copied" : bridge.pathShort
                        color: pathLabel.pathCopied ? lpv.accent : lpv.subtext
                        font.family: lpv.uiFamily
                        font.pixelSize: 12
                        elide: Text.ElideMiddle
                        Accessible.name: "Vault path " + bridge.vaultPath
                        HoverHandler {
                            id: pathHover
                            cursorShape: Qt.PointingHandCursor
                        }
                        TapHandler {
                            onTapped: {
                                if (bridge.copyText(bridge.vaultPath)) {
                                    pathLabel.pathCopied = true
                                    pathTimer.restart()
                                }
                            }
                        }
                        ToolTip.visible: pathHover.hovered
                        ToolTip.text: bridge.vaultPath
                        ToolTip.delay: 400
                        Timer { id: pathTimer; interval: 1200; onTriggered: pathLabel.pathCopied = false }
                    }
                }

                LpvButton {
                    Layout.fillWidth: true
                    text: "Lock"
                    variant: "dangerQuiet"
                    alignLeft: true
                    onClicked: bridge.lockVault()
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: bridge.pageIndex
            VaultPage {}
            EncryptPage {}
            GeneratePage {}
            SettingsPage {}
        }
    }
}
