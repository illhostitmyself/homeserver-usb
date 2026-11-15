// "Review" page (notesqml@review): what the install will do, from the choices on the earlier pages.
import io.calamares.core 1.0
import io.calamares.ui 1.0
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.3

Page {
    id: page
    background: Rectangle { color: "#FFFFFF" }

    // Checklist name -> [download MB, disk MB, memory MB when idle], measured with every app running.
    readonly property var cost: ({
        "Homepage": [80, 263, 233], "File Browser": [16, 39, 25], "Shared folder": [0, 0, 30],
        "Jellyfin": [326, 894, 206], "Seerr": [140, 503, 228], "Audiobookshelf": [125, 360, 119],
        "Sonarr": [83, 205, 120], "Radarr": [86, 213, 101], "Chaptarr": [368, 1030, 132],
        "Prowlarr": [77, 187, 114], "Bazarr": [149, 442, 181], "Recyclarr": [45, 130, 12],
        "qBittorrent": [97, 231, 35], "SABnzbd": [66, 185, 67]
    })
    property var drives: []
    property var apps: []
    property var totals: [0, 0, 0]

    function refresh() {
        var d = [], a = [], t = [0, 0, 0];
        var ops = Global.value("packageOperations") || [];
        for (var i = 0; i < ops.length; i++) {
            for (var key in ops[i]) {
                var entries = ops[i][key];
                if (!Array.isArray(entries)) continue;
                for (var j = 0; j < entries.length; j++) {
                    var e = entries[j];
                    var name = typeof e === "string" ? e : (e.package || e.name || "");
                    if (/\(\/dev\/[^)]+\)$/.test(name)) d.push(name);
                    else if (cost[name] !== undefined) {
                        a.push(name);
                        for (var k = 0; k < 3; k++) t[k] += cost[name][k];
                    }
                }
            }
        }
        drives = d; apps = a; totals = t;
    }
    function gb(mb) { return (Math.max(mb, 100) / 1024).toFixed(1) + " GB"; }

    onVisibleChanged: if (visible) refresh()
    Component.onCompleted: refresh()

    ScrollView {
        anchors.fill: parent
        anchors.margins: 30
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: 18

            Text { text: "Check this before installing"; font.pixelSize: 30; font.bold: true; color: "#253457" }

            Text { text: "These drives will be ERASED"; font.pixelSize: 22; font.bold: true; color: "#FB4D13" }
            Text {
                Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 18; color: "#253457"
                text: "• The drive you picked on the Partitions page (shown again on the next page)" +
                      (drives.length ? "\n• " + drives.join("\n• ") +
                       "\n  (if one of these is the drive above, it's skipped)" : "\n• No extra drives")
            }

            Text { text: "Apps (" + apps.length + ")"; font.pixelSize: 22; font.bold: true; color: "#253457" }
            Text {
                Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 18; color: "#253457"
                text: (apps.length ? apps.join(", ") : "None") +
                      "\nApps that a picked app needs are added automatically."
            }

            Text { text: "What it needs"; font.pixelSize: 22; font.bold: true; color: "#253457" }
            Text {
                Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 18; color: "#253457"
                text: "• Internet: about " + gb(totals[0]) + " to download during the install. Without " +
                      "internet the system still installs, and the apps download on the first start.\n" +
                      "• Disk: about 3 GB for the system and " + gb(totals[1]) + " for the apps, on the " +
                      "system partition. The rest is free for your files and media.\n" +
                      "• Memory: the apps use about " + gb(totals[2] + 1000) + " together with the system " +
                      "and screen. 4 GB of RAM works; 8 GB is more comfortable for streaming to several TVs."
            }
        }
    }
}
