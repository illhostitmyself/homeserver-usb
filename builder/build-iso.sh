#!/usr/bin/env bash
# Runs inside the builder container: /src is the repo, /build is the work dir.
set -euo pipefail
mkdir -p /build/lb && cd /build/lb

lb clean
rm -rf auto config
cp -a /src/live/. .
lb config

overlay=config/includes.chroot_after_packages
mkdir -p "$overlay" config/includes.binary/homeserver/images
cp -a /src/installer/. /src/server/. "$overlay/"
chown -R root:root "$overlay"
cp -l /build/images/*.tar.zst config/includes.binary/homeserver/images/

lb build
mv -f ./*.hybrid.iso /out/homeserver-usb.iso
