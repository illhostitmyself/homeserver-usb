#!/bin/bash
# Starts the installer scaled to the screen: 1x at 768 lines, 1.5x at 1080, 2x at 1440 and up.
# Bigger text is easier to read, and Calamares' built-in map is a fixed small image otherwise.
height=$(head -qn1 /sys/class/drm/card*-*/modes 2>/dev/null | cut -dx -f2 | sort -n | tail -1)
scale=$(awk -v h="${height:-768}" 'BEGIN { s = int(h / 720 * 4) / 4; if (s < 1) s = 1; if (s > 2) s = 2; print s }')
export QT_SCALE_FACTOR=$scale
/usr/lib/homeserver/wifi-setup.sh
# The apps come from the newest catalog in the repo; without internet, from the minimal one on the stick.
/usr/lib/homeserver/catalog.sh fetch /run/homeserver/catalog ||
  { rm -rf /run/homeserver/catalog; cp -a /usr/share/homeserver/catalog-minimal /run/homeserver/catalog; }
python3 /run/homeserver/catalog/apps.py installer /run/homeserver
cp /run/homeserver/catalog.js /etc/calamares/branding/homeserver/catalog.js
/usr/lib/homeserver/update-setup.sh
[[ -e /run/homeserver/updated ]] && exec systemctl reboot
/usr/bin/calamares "$@"
if [[ -e /run/homeserver/installed ]]; then
  systemctl poweroff
fi
