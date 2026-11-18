#!/bin/bash
# Puts a catalog release together in OUTDIR: this directory, plus the repo's server/ tree and the Debian
# packages it needs, so servers update their own Home Server files from the catalog too (server.sh).
# server-rev is the time of the last commit that changed those files; servers never go back to an older one.
#   catalog/bundle.sh OUTDIR
set -euo pipefail
out=$(realpath -m "${1:?usage: catalog/bundle.sh OUTDIR}")
cd "$(dirname "$0")"
rm -rf "$out"
mkdir -p "$out"
tar -c --exclude=./release.sh --exclude=./bundle.sh --exclude=__pycache__ . | tar -x -C "$out"
cp -a ../server "$out/server"
# Live-system packages the installer removes from installed systems aren't needed on a server.
skip=$(sed -n '/try_remove:/,$s/^ *- //p' ../installer/etc/calamares/modules/packages.conf)
grep -v '^#' ../live/config/package-lists/homeserver.list.chroot | grep . | grep -vxF "$skip" > "$out/server-packages.list"
rev=$(git log -1 --format=%ct -- ../server ../live/config/package-lists 2>/dev/null)
echo "${rev:-0}" > "$out/server-rev"
