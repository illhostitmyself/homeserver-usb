#!/bin/bash
# Adds and removes apps on an installed server. Run as root through `catalog.sh apps`, with two lines
# on stdin: the owner's password, then the apps wanted (ids from catalog.json, space-separated).
# What those apps need is added and the always-installed apps stay. A removed app's settings stay in
# /srv/appdata, so adding it back picks up where it left off. Downloads and media are never touched.
set -euo pipefail
cat=$(dirname "$(readlink -f "$0")")
etc=/etc/homeserver
IFS= read -r password || true
read -r wanted || true
. "$etc/homeserver.env"
new=$(python3 "$cat/apps.py" resolve $wanted)
diff_apps() { comm "$1" <(tr ' ' '\n' <<<"$APPS" | grep . | sort) <(tr ' ' '\n' <<<"$new" | grep . | sort) | xargs; }
removed=$(diff_apps -23) added=$(diff_apps -13)
if [[ -z $removed && -z $added ]]; then
  echo "Nothing to change"
  exit 0
fi
[[ -n $added ]] && echo "Adding $(python3 "$cat/apps.py" names $added)"
[[ -n $removed ]] && echo "Removing $(python3 "$cat/apps.py" names $removed)"

# The apps get the owner's name and password, as in the installer. configure-apps.sh deletes the file.
if [[ ! -f $etc/password-generated ]]; then
  [[ -n $password ]] || { echo "No password given" >&2; exit 1; }
  trap 'rm -f "$etc/password"' EXIT
  install -m 600 /dev/null "$etc/password"
  printf '%s' "$password" > "$etc/password"
fi

set -a
. "$etc/compose.env"
. "$etc/secrets.env"
SRV=/srv
set +a
compose() { docker compose -f "$cat/compose.yaml" "$@"; }
for app in $removed; do
  if [[ $app == files ]]; then
    systemctl disable --now smbd.service nmbd.service wsdd2.service 2>/dev/null || true
    smbpasswd -x "$OWNER" >/dev/null 2>&1 || true
    awk '/^\[/ { skip = ($0 == "[Media]") } !skip' /etc/samba/smb.conf > /etc/samba/smb.conf.new
    mv /etc/samba/smb.conf.new /etc/samba/smb.conf
  else
    images=$(COMPOSE_PROFILES=$app compose config --images "$app")
    COMPOSE_PROFILES=$app compose rm --stop --force "$app"
    docker image rm $images >/dev/null 2>&1 || true
  fi
done

profiles=$(tr ' ' '\n' <<<"$new" | grep -vx files | paste -sd, -)
printf 'OWNER="%s"\nAPPS="%s"\nCOMPOSE_PROFILES="%s"\n' "$OWNER" "$new" "$profiles" > "$etc/homeserver.env"
# Bazarr's config follows which of Sonarr and Radarr are installed; it's only read when Bazarr starts.
[[ " $new " == *" bazarr "* ]] && COMPOSE_PROFILES=bazarr compose stop bazarr >/dev/null 2>&1
"$cat/configure-apps.sh" /
echo "Done"
