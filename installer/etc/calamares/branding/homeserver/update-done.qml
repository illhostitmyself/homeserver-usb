// Last page of "Update this server" (the finishedq module). Done closes Calamares and the stick restarts.
import io.calamares.core 1.0
import io.calamares.ui 1.0
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.3

Page {
    background: Rectangle { color: "#FFFFFF" }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 30
        spacing: 18

        Text { text: "Your server is up to date"; font.pixelSize: 30; font.bold: true; color: "#253457" }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 18; color: "#253457"
            text: "Your apps, their settings, your name and password, and your files are all as they were. " +
                  "The first time the server starts, it moves your apps to the versions in the app catalog, " +
                  "so the dashboard can take a few minutes to come up."
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 22; font.bold: true; color: "#FB4D13"
            text: "Take out the USB stick, then click Done. The computer restarts into your server."
        }
        Item { Layout.fillHeight: true }
    }
}
