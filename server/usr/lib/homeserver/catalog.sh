#!/bin/bash
# The app catalog: the apps' configs and setup, published as signed releases in the repo.
#   catalog.sh fetch DIR    download the newest release, check its signature, unpack it into DIR
#   catalog.sh status       JSON for the Cockpit page: {"installed": N, "latest": N or null}
#   catalog.sh update       install the newest release on this server (run as root)
#   catalog.sh apps         add and remove apps (run as root; stdin: password, then the apps wanted)
# The release is catalog.tar.gz + catalog.tar.gz.sig on the repo's "catalog" release, signed with a
# key that never leaves the maintainer's machine. /etc/homeserver/catalog-url (or homeserver.catalog=
# on the kernel command line) points somewhere else, for testing.
set -uo pipefail
signers=${HOMESERVER_CATALOG_SIGNERS:-/usr/share/homeserver/catalog-signers}
installed=/var/lib/homeserver/catalog
url=https://github.com/illhostitmyself/homeserver-usb/releases/download/catalog
[[ -f /etc/homeserver/catalog-url ]] && url=$(< /etc/homeserver/catalog-url)
for arg in $(< /proc/cmdline); do [[ $arg == homeserver.catalog=* ]] && url=${arg#*=}; done

version() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$1/catalog.json" 2>/dev/null; }

fetch() {
  local dir=$1 tmp
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN
  curl -fsSL --retry 2 --max-time 120 -o "$tmp/catalog.tar.gz" "$url/catalog.tar.gz" &&
    curl -fsSL --retry 2 --max-time 30 -o "$tmp/catalog.tar.gz.sig" "$url/catalog.tar.gz.sig" ||
    { echo "Couldn't download the app catalog" >&2; return 1; }
  ssh-keygen -q -Y verify -f "$signers" -I homeserver-catalog -n homeserver-catalog \
    -s "$tmp/catalog.tar.gz.sig" < "$tmp/catalog.tar.gz" >/dev/null ||
    { echo "The app catalog's signature doesn't match; not using it" >&2; return 1; }
  rm -rf "$dir" && mkdir -p "$dir" && tar -xzf "$tmp/catalog.tar.gz" -C "$dir" ||
    { echo "Couldn't unpack the app catalog" >&2; return 1; }
  [[ -n $(version "$dir") ]] || { echo "The app catalog has no version" >&2; return 1; }
}

# One app change at a time: an update and adding apps both restart them.
lock() {
  exec 9>/run/homeserver-catalog.lock
  flock -n 9 || { echo "The apps are already being changed. Try again when that's done." >&2; exit 1; }
}

case ${1:-} in
  fetch)
    [[ -n ${2:-} ]] || { echo "usage: catalog.sh fetch DIR" >&2; exit 2; }
    fetch "$2"
    ;;
  status)
    tmp=$(mktemp -d)
    latest=null
    fetch "$tmp/c" 2>/dev/null && latest=$(version "$tmp/c")
    rm -rf "$tmp"
    printf '{"installed": %s, "latest": %s}\n' "$(version "$installed" || echo null)" "$latest"
    ;;
  update)
    lock
    new=$installed.new old=$installed.old
    fetch "$new" || exit 1
    have=$(version "$installed") got=$(version "$new")
    if [[ -n $have ]] && (( got <= have )); then
      echo "Already up to date (catalog $have)"
      rm -rf "$new"
      exit 0
    fi
    echo "Updating the apps from catalog ${have:-none} to $got..."
    rm -rf "$old"
    [[ -d $installed ]] && mv "$installed" "$old"
    mv "$new" "$installed"
    if "$installed/update.sh"; then
      rm -rf "$old"
      echo "Done: catalog $got"
    else
      echo "The update failed; going back to catalog $have" >&2
      rm -rf "$installed"
      [[ -d $old ]] && mv "$old" "$installed" && "$installed/update.sh"
      exit 1
    fi
    ;;
  apps)
    lock
    [[ -x $installed/apps.sh ]] ||
      { echo "This app catalog can't add or remove apps. Update the apps first." >&2; exit 1; }
    "$installed/apps.sh"
    ;;
  *)
    sed -n '2,9p' "$0" >&2
    exit 2
    ;;
esac
