#!/bin/bash
# Configures the apps in /etc/homeserver/homeserver.env. $1 is the system's root: the new disk during
# install, / on a first-start retry. Safe to run again; every step skips what's already done.
set -euo pipefail
root=${1:-/}
root=${root%/}
lib=$(dirname "$(readlink -f "$0")")
etc=$root/etc/homeserver
setup() { python3 "$lib/setup.py" --root "${root:-/}" "$@"; }
has() { [[ " $APPS " == *" $1 "* ]]; }

setup prepare
set -a
. "$etc/homeserver.env"
. "$etc/compose.env"
. "$etc/secrets.env"
SRV=$root/srv
set +a
compose() { docker compose -f "$lib/compose.yaml" "$@"; }
password=$(cat "$etc/password")

if has files; then
  printf '%s\n%s\n' "$password" "$password" | chroot "${root:-/}" smbpasswd -s -a "$OWNER"
  chroot "${root:-/}" systemctl enable smbd.service nmbd.service wsdd2.service
fi

if [[ ! -f $SRV/appdata/filebrowser/database/filebrowser.db ]]; then
  compose run --rm --no-deps filebrowser config init --minimumPasswordLength=1 >/dev/null
  if ! compose run --rm --no-deps filebrowser users add "$OWNER" "$password" --perm.admin >/dev/null; then
    # Filebrowser refuses passwords on its common-password list.
    files_password=$(head -c 12 /dev/urandom | base64 | tr -d '/+=')
    compose run --rm --no-deps filebrowser users add "$OWNER" "$files_password" --perm.admin >/dev/null
    printf '%s' "$files_password" > "$etc/files-password"
    chmod 600 "$etc/files-password"
  fi
fi

compose up -d --quiet-pull
setup connect

if has downloads; then
  compose run --rm --no-deps recyclarr sync ||
    echo "Recyclarr couldn't sync the TRaSH Guides (no internet?). It retries every day." >&2
fi
if has requests; then
  setup seerr
fi
setup dashboard

[[ -f $etc/password-generated ]] || rm -f "$etc/password"
mkdir -p "$root/var/lib/homeserver"
touch "$root/var/lib/homeserver/setup-done"
