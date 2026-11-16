#!/bin/bash
# Run by installer-scale.sh before the installer. If a disk already has Home Server on it, runs the
# "Update this server" flow (Calamares with /etc/calamares-update). Next updates it in place
# (/run/homeserver/updated is left behind); Cancel goes on to the normal installer.
probe=/run/homeserver/probe
mkdir -p "$probe"
for dev in $(lsblk -lnpo NAME,FSTYPE | awk '$2 == "ext4" { print $1 }'); do
  mount -o ro "$dev" "$probe" 2>/dev/null || continue
  if [[ -f $probe/etc/homeserver/homeserver.env ]]; then
    export HS_DEV=$dev
    disk=/dev/$(lsblk -no PKNAME "$dev")
    hs_disk="$(lsblk -dno MODEL "$disk" | xargs), $(lsblk -dno SIZE "$disk" | xargs) ($disk)"
    hs_date=$(date -d "@$(stat -c %Y "$probe/etc/homeserver/homeserver.env")" '+%-d %B %Y')
    hs_version=$(cat "$probe/usr/share/homeserver/version" 2>/dev/null || echo "v0.2.0 or older")
    hs_apps=$(. "$probe/etc/homeserver/homeserver.env"; echo "$APPS")
  fi
  umount "$probe"
  [[ -n ${HS_DEV:-} ]] && break
done
[[ -n ${HS_DEV:-} ]] || exit 0

declare -A names=([audiobookshelf]=Audiobookshelf [bazarr]=Bazarr [chaptarr]=Chaptarr [filebrowser]="File Browser"
  [files]="Shared folder" [homepage]=Homepage [jellyfin]=Jellyfin [prowlarr]=Prowlarr [qbittorrent]=qBittorrent
  [radarr]=Radarr [recyclarr]=Recyclarr [sabnzbd]=SABnzbd [seerr]=Seerr [sonarr]=Sonarr)
apps=$(for a in $hs_apps; do printf '%s, ' "${names[$a]:-$a}"; done | sed 's/, $//')
new=$(cat /usr/share/homeserver/version 2>/dev/null)
q() { sed 's/[\\"]/\\&/g' <<< "$1"; }

cat > /etc/calamares/branding/homeserver/update-server.qml <<EOF
// Written by update-setup.sh: first page of "Update this server" (notesqml@server).
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

        Text { text: "Home Server is already on this computer"; font.pixelSize: 30; font.bold: true; color: "#253457" }
        GridLayout {
            columns: 2; columnSpacing: 24; rowSpacing: 8
            Text { text: "Disk"; font.pixelSize: 18; font.bold: true; color: "#253457" }
            Text { text: "$(q "$hs_disk")"; font.pixelSize: 18; color: "#253457" }
            Text { text: "Installed"; font.pixelSize: 18; font.bold: true; color: "#253457" }
            Text { text: "$(q "$hs_date")"; font.pixelSize: 18; color: "#253457" }
            Text { text: "Version"; font.pixelSize: 18; font.bold: true; color: "#253457" }
            Text { text: "$(q "$hs_version")"; font.pixelSize: 18; color: "#253457" }
            Text { text: "Apps"; font.pixelSize: 18; font.bold: true; color: "#253457"; Layout.alignment: Qt.AlignTop }
            Text { text: "$(q "$apps")"; font.pixelSize: 18; color: "#253457"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 22; font.bold: true; color: "#253457"
            text: "Click Next to update it to $(q "$new")."
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 18; color: "#253457"
            text: "Nothing is erased: your apps, their settings, your name and password, and your files stay as " +
                  "they are. It takes a few minutes and needs the internet for the new system packages."
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 18; color: "#FB4D13"
            text: "To erase the disk and install from scratch instead, click Cancel."
        }
        Item { Layout.fillHeight: true }
    }
}
EOF

XDG_CONFIG_DIRS=/etc/calamares-update /usr/bin/calamares -X
