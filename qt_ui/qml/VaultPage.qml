import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property string selectedId: ""
    property string query: ""

    function matches(entry) {
        var q = root.query.toLowerCase().trim()
        if (!q)
            return true
        var hay
        if (entry.decrypt_error && !entry.title)
            hay = "could not decrypt"
        else
            hay = [entry.title, entry.username, entry.url, entry.notes].join(" ").toLowerCase()
        return hay.indexOf(q) !== -1
    }

    readonly property var shown: {
        var out = []
        var rows = bridge.entries
        for (var i = 0; i < rows.length; i++) {
            if (matches(rows[i]))
                out.push(rows[i])
        }
        return out
    }

    readonly property var current: {
        var rows = bridge.entries
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].id === selectedId)
                return rows[i]
        }
        return null
    }

    Connections {
        target: bridge
        function onEntriesChanged() {
            var rows = bridge.entries
            for (var i = 0; i < rows.length; i++) {
                if (rows[i].id === root.selectedId)
                    return
            }
            root.selectedId = ""
        }
        function onSearchFocusRequested() {
            search.forceField()
        }
    }

    Shortcut {
        sequence: "Delete"
        enabled: root.selectedId !== "" && bridge.page === "Vault"
        context: Qt.WindowShortcut
        onActivated: {
            var item = root.Window.activeFocusItem
            var name = item ? item.toString() : ""
            if (name.indexOf("TextField") !== -1 || name.indexOf("TextArea") !== -1 || name.indexOf("TextInput") !== -1)
                return
            bridge.requestDelete(root.selectedId)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Password vault"
                color: lpv.text
                font.family: lpv.uiFamily
                font.pixelSize: 20
                font.bold: true
                Accessible.role: Accessible.Heading
            }
            Item { Layout.fillWidth: true }
            LpvButton {
                text: "Add entry"
                onClicked: bridge.newEntry()
            }
        }

        LpvField {
            id: search
            Layout.fillWidth: true
            placeholderText: "Search title, username, URL, or notes"
            Accessible.name: "Search entries"
            onTextChanged: root.query = text
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            Rectangle {
                Layout.preferredWidth: 320
                Layout.minimumWidth: 240
                Layout.fillHeight: true
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true
                clip: true

                ListView {
                    id: list
                    anchors.fill: parent
                    anchors.margins: 4
                    model: root.shown
                    spacing: 4
                    clip: true
                    currentIndex: -1
                    boundsBehavior: Flickable.StopAtBounds

                    Label {
                        anchors.centerIn: parent
                        visible: list.count === 0
                        color: lpv.subtext
                        text: root.query.trim() !== "" ? "No matching entries" : "No entries yet"
                    }

                    delegate: Rectangle {
                        id: entryRow
                        required property var modelData
                        width: list.width
                        height: row.implicitHeight + 16
                        radius: 8
                        clip: true
                        antialiasing: true
                        color: modelData.id === root.selectedId ? lpv.primarySoft
                             : (rowHover.hovered ? lpv.surface3 : "transparent")

                        HoverHandler {
                            id: rowHover
                            cursorShape: Qt.PointingHandCursor
                        }

                        Rectangle {
                            visible: modelData.id === root.selectedId
                            width: 3
                            radius: 2
                            height: parent.height - 16
                            anchors.left: parent.left
                            anchors.leftMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            color: lpv.accent
                            antialiasing: true
                        }

                        ColumnLayout {
                            id: row
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 16
                            anchors.rightMargin: 12
                            spacing: 2
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Label {
                                    Layout.fillWidth: true
                                    text: modelData.title || "(untitled)"
                                    color: lpv.text
                                    font.bold: true
                                    font.pixelSize: 14
                                    font.family: lpv.uiFamily
                                    elide: Text.ElideRight
                                }
                                Rectangle {
                                    visible: modelData.totp_secret !== ""
                                    radius: 6
                                    color: lpv.accentSoft
                                    antialiasing: true
                                    implicitWidth: badge.implicitWidth + 10
                                    implicitHeight: 18
                                    Label {
                                        id: badge
                                        anchors.centerIn: parent
                                        text: "2FA"
                                        color: lpv.text
                                        font.bold: true
                                        font.pixelSize: 10
                                        font.family: lpv.uiFamily
                                    }
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                text: modelData.username || "No username"
                                color: lpv.subtext
                                font.pixelSize: 12
                                font.family: lpv.uiFamily
                                elide: Text.ElideRight
                            }
                        }

                        TapHandler {
                            onTapped: root.selectedId = modelData.id
                        }
                        Accessible.name: (modelData.title || "Untitled") + ", " + (modelData.username || "no username")
                        Accessible.role: Accessible.ListItem

                        Behavior on color {
                            enabled: lpv && !lpv.reduceMotion
                            ColorAnimation { duration: 140 }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: lpv.surface
                radius: 12
                border.color: lpv.border
                border.width: 1
                antialiasing: true

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 20
                    contentHeight: detail.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                ColumnLayout {
                    id: detail
                    width: parent.width
                    spacing: 10

                    Label {
                        visible: root.current === null
                        text: list.count === 0
                              ? (root.query.trim() !== "" ? "No matching entries" : "No entries yet")
                              : "Select an entry to view details"
                        color: lpv.subtext
                        font.pixelSize: 14
                        font.family: lpv.uiFamily
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 28
                    }

                    ColumnLayout {
                        visible: root.current !== null
                        Layout.fillWidth: true
                        spacing: 8

                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: root.current ? (root.current.title || "(untitled)") : ""
                            color: lpv.text
                            font.pixelSize: 20
                            font.bold: true
                        }
                        Label {
                            visible: root.current && root.current.decrypt_error
                            text: "Part of this entry could not be decrypted."
                            color: lpv.danger
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        LpvButton {
                            visible: root.current && root.current.urlSafe
                            Layout.fillWidth: true
                            text: root.current ? root.current.url : ""
                            variant: "ghost"
                            alignLeft: true
                            compact: true
                            onClicked: bridge.openUrl(root.current.url)
                        }
                        Label {
                            visible: root.current && root.current.url !== "" && !root.current.urlSafe
                            text: root.current ? root.current.url : ""
                            color: lpv.subtext
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Label { text: "Username"; color: lpv.subtext; font.pixelSize: 12; font.family: lpv.uiFamily }
                        Rectangle {
                            Layout.fillWidth: true
                            radius: 10
                            color: lpv.surface2
                            border.color: lpv.border
                            border.width: 1
                            antialiasing: true
                            implicitHeight: 48
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 6
                                Label {
                                    Layout.fillWidth: true
                                    text: root.current ? root.current.username : ""
                                    color: lpv.text
                                    font.pixelSize: 14
                                    font.family: lpv.uiFamily
                                    elide: Text.ElideRight
                                }
                                LpvButton {
                                    text: userCopied ? "Copied" : "Copy"
                                    variant: "ghost"
                                    compact: true
                                    enabled: root.current && root.current.username !== ""
                                    onClicked: {
                                        if (bridge.copyText(root.current.username)) {
                                            userCopied = true
                                            userTimer.restart()
                                        }
                                    }
                                    property bool userCopied: false
                                    Timer {
                                        id: userTimer
                                        interval: 1200
                                        onTriggered: parent.userCopied = false
                                    }
                                }
                            }
                        }

                        Label { text: "Password"; color: lpv.subtext; font.pixelSize: 12; font.family: lpv.uiFamily }
                        Rectangle {
                            Layout.fillWidth: true
                            radius: 10
                            color: lpv.surface2
                            border.color: lpv.border
                            border.width: 1
                            antialiasing: true
                            implicitHeight: 48
                            RowLayout {
                                id: pwRow
                                property bool pwShown: false
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 6
                                spacing: 8
                                Label {
                                    Layout.fillWidth: true
                                    text: !root.current ? "" : (pwRow.pwShown ? root.current.password : "••••••••")
                                    color: lpv.text
                                    font.family: lpv.monoFamily
                                    font.pixelSize: 14
                                    elide: Text.ElideRight
                                }
                                Label {
                                    visible: root.current && root.current.password !== ""
                                    text: root.current ? root.current.strengthLabel : ""
                                    color: root.current ? root.current.strengthColor : lpv.subtext
                                    font.bold: true
                                    font.pixelSize: 12
                                    font.family: lpv.uiFamily
                                }
                                LpvButton {
                                    visible: root.current && root.current.password !== ""
                                    text: pwRow.pwShown ? "Hide" : "Show"
                                    variant: "ghost"
                                    compact: true
                                    onClicked: pwRow.pwShown = !pwRow.pwShown
                                    Accessible.name: pwRow.pwShown ? "Hide password" : "Show password"
                                }
                                LpvButton {
                                    visible: root.current && !(root.current.decrypt_error && root.current.password === "")
                                    text: pwCopied ? "Copied" : "Copy"
                                    variant: "ghost"
                                    compact: true
                                    onClicked: {
                                        if (bridge.copyText(root.current.password)) {
                                            pwCopied = true
                                            pwTimer.restart()
                                        }
                                    }
                                    property bool pwCopied: false
                                    Timer {
                                        id: pwTimer
                                        interval: 1200
                                        onTriggered: parent.pwCopied = false
                                    }
                                }
                            }
                        }

                        Label {
                            visible: root.current && root.current.notes !== ""
                            text: "Notes"
                            color: lpv.subtext
                            font.pixelSize: 12
                            font.family: lpv.uiFamily
                        }
                        Rectangle {
                            visible: root.current && root.current.notes !== ""
                            Layout.fillWidth: true
                            radius: 10
                            color: lpv.surface2
                            border.color: lpv.border
                            border.width: 1
                            antialiasing: true
                            implicitHeight: notesBody.implicitHeight + 20
                            Label {
                                id: notesBody
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 10
                                wrapMode: Text.WordWrap
                                text: root.current ? root.current.notes : ""
                                color: lpv.text
                                font.pixelSize: 14
                                font.family: lpv.uiFamily
                            }
                        }

                        Label {
                            visible: root.current && root.current.totp_secret !== ""
                            text: "Two-factor code"
                            color: lpv.subtext
                            font.pixelSize: 12
                        }
                        RowLayout {
                            visible: root.current && root.current.totp_secret !== ""
                            spacing: 12
                            Canvas {
                                id: arc
                                width: 54
                                height: 54
                                property int remain: 0
                                property real progress: 0
                                onPaint: {
                                    var ctx = getContext("2d")
                                    ctx.clearRect(0, 0, width, height)
                                    var cx = width / 2
                                    var cy = height / 2
                                    var r = 20
                                    ctx.lineWidth = 4
                                    ctx.strokeStyle = lpv.border
                                    ctx.beginPath()
                                    ctx.arc(cx, cy, r, 0, Math.PI * 2)
                                    ctx.stroke()
                                    var ink = remain > 8 ? lpv.success : lpv.warning
                                    ctx.strokeStyle = ink
                                    ctx.beginPath()
                                    ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress)
                                    ctx.stroke()
                                    ctx.fillStyle = ink
                                    ctx.font = "bold 12px \"" + lpv.uiFamily + "\""
                                    ctx.textAlign = "center"
                                    ctx.textBaseline = "middle"
                                    ctx.fillText(String(remain), cx, cy)
                                }
                            }
                            ColumnLayout {
                                Label {
                                    id: totpCode
                                    text: "------"
                                    color: lpv.accent
                                    font.family: lpv.monoFamily
                                    font.pixelSize: 20
                                    font.bold: true
                                    Accessible.name: "Current authenticator code " + text
                                }
                                LpvButton {
                                    text: codeCopied ? "Copied" : "Copy code"
                                    variant: "ghost"
                                    compact: true
                                    onClicked: {
                                        var info = bridge.totpInfo(root.current ? root.current.totp_secret : "")
                                        if (info.ok && bridge.copyText(info.raw)) {
                                            codeCopied = true
                                            codeTimer.restart()
                                        }
                                    }
                                    property bool codeCopied: false
                                    Timer {
                                        id: codeTimer
                                        interval: 1200
                                        onTriggered: parent.codeCopied = false
                                    }
                                }
                            }
                            Timer {
                                interval: 1000
                                repeat: true
                                running: root.current && root.current.totp_secret !== "" && bridge.page === "Vault" && bridge.screen === "main"
                                triggeredOnStart: true
                                onTriggered: {
                                    if (!root.current)
                                        return
                                    var info = bridge.totpInfo(root.current.totp_secret)
                                    totpCode.text = info.ok ? info.display : "Invalid"
                                    arc.remain = info.remaining
                                    arc.progress = info.progress
                                    arc.requestPaint()
                                }
                            }
                        }

                        Label {
                            visible: root.current !== null
                            color: lpv.subtext
                            font.pixelSize: 12
                            text: root.current ? ("Added " + root.current.createdLabel + "   ·   Updated " + root.current.updatedLabel) : ""
                        }

                        RowLayout {
                            visible: root.current !== null
                            spacing: 8
                            LpvButton {
                                text: "Edit"
                                variant: "ghost"
                                onClicked: bridge.editEntry(root.selectedId)
                            }
                            LpvButton {
                                text: "Delete"
                                variant: "danger"
                                onClicked: bridge.requestDelete(root.selectedId)
                            }
                        }
                    }
                }
                }
            }
        }
    }
}
