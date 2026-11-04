import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: win
    width: 1200
    height: 860
    minimumWidth: 960
    minimumHeight: 680
    visible: true
    title: "LocalPasswordVault"
    color: lpv.bg
    font.family: lpv.uiFamily
    font.pixelSize: 14

    function typing(item) {
        if (!item)
            return false
        var name = item.toString()
        return name.indexOf("TextField") !== -1 || name.indexOf("TextArea") !== -1 || name.indexOf("TextInput") !== -1
    }

    Shortcut {
        sequences: ["Ctrl+L"]
        context: Qt.ApplicationShortcut
        enabled: bridge.screen === "main"
        onActivated: bridge.lockVault()
    }
    Shortcut {
        sequences: ["Ctrl+F"]
        context: Qt.ApplicationShortcut
        enabled: bridge.screen === "main"
        onActivated: bridge.focusSearch()
    }
    Shortcut {
        sequences: ["Ctrl+N"]
        context: Qt.ApplicationShortcut
        enabled: bridge.screen === "main" && !win.typing(win.activeFocusItem)
        onActivated: bridge.newEntry()
    }

    Loader {
        anchors.fill: parent
        source: bridge.screen === "main" ? "Shell.qml" : "UnlockPage.qml"
    }

    EntryDialog { id: entryDlg }
    TwoFaDialogs { }

    Connections {
        target: bridge
        function onEntryDialogRequested(eid) {
            entryDlg.openFor(eid)
        }
        function onConfirmRequested(id, title, body) {
            confirmDlg.askId = id
            confirmDlg.heading = title
            confirmDlg.bodyText = body
            confirmDlg.open()
        }
        function onAlertRequested(title, body) {
            alertDlg.heading = title
            alertDlg.bodyText = body
            alertDlg.open()
        }
        function onStateChanged() {
            if (bridge.screen !== "main" && entryDlg.opened)
                entryDlg.close()
        }
    }

    Dialog {
        id: confirmDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 440
        padding: 20
        standardButtons: Dialog.NoButton
        closePolicy: Popup.CloseOnEscape
        property string askId: ""
        property string heading: ""
        property string bodyText: ""
        property bool answered: false
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }
        header: Label {
            text: confirmDlg.heading
            color: lpv.text
            font.bold: true
            font.pixelSize: 16
            leftPadding: 20
            topPadding: 16
            wrapMode: Text.WordWrap
            width: confirmDlg.width - 40
        }
        contentItem: Label {
            text: confirmDlg.bodyText
            color: lpv.text
            wrapMode: Text.WordWrap
            font.pixelSize: 14
        }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            LpvButton { text: "No"; variant: "ghost"; onClicked: confirmDlg.reject() }
            LpvButton { text: "Yes"; variant: "primary"; onClicked: confirmDlg.accept() }
        }
        onAboutToShow: answered = false
        onAccepted: {
            if (answered)
                return
            answered = true
            bridge.answerConfirm(askId, true)
        }
        onRejected: {
            if (answered)
                return
            answered = true
            bridge.answerConfirm(askId, false)
        }
    }

    Dialog {
        id: alertDlg
        parent: Overlay.overlay
        modal: true
        anchors.centerIn: parent
        width: 440
        padding: 20
        standardButtons: Dialog.NoButton
        closePolicy: Popup.CloseOnEscape
        property string heading: ""
        property string bodyText: ""
        background: Rectangle { color: lpv.surface; radius: 14; border.color: lpv.border; border.width: 1; antialiasing: true }
        header: Label {
            text: alertDlg.heading
            color: lpv.text
            font.bold: true
            font.pixelSize: 16
            leftPadding: 20
            topPadding: 16
            wrapMode: Text.WordWrap
            width: alertDlg.width - 40
        }
        contentItem: Label {
            text: alertDlg.bodyText
            color: lpv.text
            wrapMode: Text.WordWrap
        }
        footer: RowLayout {
            Item { Layout.fillWidth: true }
            LpvButton { text: "OK"; onClicked: alertDlg.close() }
        }
    }
}
