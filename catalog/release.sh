#!/bin/bash
# Publishes this directory, with the repo's server/ files (bundle.sh), as the newest app catalog.
# Raise "version" in catalog.json and commit first: the release is built from what's committed.
#   catalog/release.sh KEYFILE
# KEYFILE is the private half of server/usr/share/homeserver/catalog-signers. It never goes in the
# repo, in CI, or on a server. The release goes to two GitHub releases: catalog-vN (kept, for
# history) and catalog (always the newest; what servers and the installer download).
set -euo pipefail
cd "$(dirname "$0")"
key=${1:?usage: catalog/release.sh KEYFILE}
signers=../server/usr/share/homeserver/catalog-signers
version=$(python3 -c 'import json; print(json.load(open("catalog.json"))["version"])')
git diff --quiet HEAD -- . ../server ../live/config/package-lists ../installer/etc/calamares/modules/packages.conf ||
  { echo "Commit your changes first: the release is built from what's committed" >&2; exit 1; }

current=$(mktemp -d)
trap 'rm -rf "$current"' EXIT
if HOMESERVER_CATALOG_SIGNERS=$signers ../server/usr/lib/homeserver/catalog.sh fetch "$current/c" 2>/dev/null; then
  published=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$current/c/catalog.json")
  (( version > published )) || { echo "catalog.json version $version isn't newer than the published $published" >&2; exit 1; }
fi

out=$(mktemp -d)
./bundle.sh "$out/c"
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime=@0 -C "$out/c" -czf "$out/catalog.tar.gz" .
ssh-keygen -Y sign -f "$key" -n homeserver-catalog "$out/catalog.tar.gz"
ssh-keygen -q -Y verify -f "$signers" -I homeserver-catalog -n homeserver-catalog \
  -s "$out/catalog.tar.gz.sig" < "$out/catalog.tar.gz" >/dev/null ||
  { echo "That key isn't the one in $signers" >&2; exit 1; }

# Both files in one asset too: GitHub caches downloads of the "catalog" release for a few minutes, and
# two separate files can come from different releases in that time. catalog.sh tries this one first.
tar -C "$out" -cf "$out/catalog.bundle.tar" catalog.tar.gz catalog.tar.gz.sig

notes="App catalog version $version: the app configs and setup that Home Server installs and updates from."
gh release create "catalog-v$version" --latest=false --title "App catalog v$version" --notes "$notes" \
  "$out/catalog.tar.gz" "$out/catalog.tar.gz.sig" "$out/catalog.bundle.tar"
gh release view catalog >/dev/null 2>&1 ||
  gh release create catalog --latest=false --title "App catalog (newest)" \
    --notes "Always the newest app catalog. Servers and the installer download it from here."
gh release upload catalog --clobber "$out/catalog.tar.gz" "$out/catalog.tar.gz.sig" "$out/catalog.bundle.tar"
rm -rf "$out"
echo "Published app catalog v$version"
