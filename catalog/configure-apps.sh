#!/bin/bash
# Downloads and configures the apps in /etc/homeserver/homeserver.env, when installing and when apps are
# added later (apps.sh). $1 is the system's root: the
# new disk during install, / on a first-start retry. Safe to run again; every step skips what's done.
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

for try in 1 2 3; do
  compose pull --quiet && break
  (( try == 3 )) && { echo "Couldn't download the apps (no internet?)" >&2; exit 1; }
  sleep $((try * 15))
done

if has files; then
  smb=$root/etc/samba/smb.conf
  grep -qx '\[Media\]' "$smb" ||
    printf '\n[Media]\n   path = /srv/data/media\n   valid users = %s\n   read only = no\n' "$OWNER" >> "$smb"
  printf '%s\n%s\n' "$password" "$password" | chroot "${root:-/}" smbpasswd -s -a "$OWNER" >/dev/null
  if [[ -z $root ]]; then
    systemctl --quiet enable --now smbd.service nmbd.service wsdd2.service
  else
    chroot "$root" systemctl --quiet enable smbd.service nmbd.service wsdd2.service
  fi
fi

if has filebrowser && [[ ! -f $SRV/appdata/filebrowser/database/filebrowser.db ]]; then
  compose run --rm --no-deps filebrowser config init --minimumPasswordLength=1 >/dev/null
  if ! compose run --rm --no-deps filebrowser users add "$OWNER" "$password" --perm.admin >/dev/null; then
    # File Browser refuses passwords on its common-password list.
    files_password=$(head -c 12 /dev/urandom | base64 | tr -d '/+=')
    compose run --rm --no-deps filebrowser users add "$OWNER" "$files_password" --perm.admin >/dev/null
    printf '%s' "$files_password" > "$etc/files-password"
    chmod 600 "$etc/files-password"
  fi
fi

compose up -d
setup connect

if has recyclarr; then
  compose run --rm --no-deps recyclarr sync ||
    echo "Recyclarr couldn't sync the TRaSH Guides (no internet?). It retries every day." >&2
fi
setup link
setup dashboard

[[ -f $etc/password-generated ]] || rm -f "$etc/password"
mkdir -p "$root/var/lib/homeserver"
touch "$root/var/lib/homeserver/setup-done"
