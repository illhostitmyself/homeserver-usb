#!/bin/bash
# Run by installer-scale.sh before the installer. With no wired connection and a Wi-Fi card, shows
# a screen to pick a Wi-Fi network. Calamares' networkcfg step copies the saved connection to the
# installed system.
online() { ip route show default | grep -q .; }

nm-online -s -q -t 30 || true
online && exit 0
nmcli radio wifi on 2>/dev/null
nmcli -t -f TYPE device | grep -qx wifi || exit 0

size=$(awk -v s="${QT_SCALE_FACTOR:-1}" 'BEGIN { print int(14 * s) }')
foot -o font="DejaVu Sans Mono:size=$size" -o pad=40x40 -o colors.background=1e2229 \
  /usr/lib/homeserver/wifi-picker.sh
