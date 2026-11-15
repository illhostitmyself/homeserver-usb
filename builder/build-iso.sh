#!/usr/bin/env bash
# Runs inside the builder container: /src is the repo, /build is the work dir.
set -euo pipefail
mkdir -p /build/lb && cd /build/lb

lb clean
rm -rf auto config
cp -a /src/live/. .
lb config

# Boot the menu's first entry on its own after 5 seconds (the stock menus wait for a key press).
mkdir -p config/bootloaders
cp -a /usr/share/live/build/bootloaders/grub-pc /usr/share/live/build/bootloaders/isolinux config/bootloaders/
sed -i 's/^set default=0$/set default=0\nset timeout=5/' config/bootloaders/grub-pc/config.cfg
sed -i 's/^timeout 0$/timeout 50/' config/bootloaders/isolinux/isolinux.cfg

overlay=config/includes.chroot_after_packages
mkdir -p "$overlay"
cp -a /src/installer/. /src/server/. "$overlay/"
chown -R root:root "$overlay"

lb build
mv -f ./*.hybrid.iso /out/homeserver-usb.iso
