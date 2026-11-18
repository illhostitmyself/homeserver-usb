#!/bin/bash
# Run on an installed server right after this catalog release replaced the previous one
# (/var/lib/homeserver/catalog): by catalog.sh update (the Cockpit page) or homeserver-refresh.service
# (after an update from the USB stick). Installs the Home Server files this release carries, moves the
# apps to the versions pinned here, and applies the app settings again. With the owner's password in
# /etc/homeserver/password (the Cockpit page passes it) that's all of setup.py; without it, what the
# apps' API keys allow: download clients, libraries, Prowlarr, Recyclarr, Bazarr and the dashboard.
# Anything else a release needs goes here too, written so it's safe to run more than once.
set -euo pipefail
cat=$(dirname "$(readlink -f "$0")")
"$cat/server.sh" /

set -a
. /etc/homeserver/homeserver.env
. /etc/homeserver/compose.env
. /etc/homeserver/secrets.env
SRV=/srv
set +a
compose() { docker compose -f "$cat/compose.yaml" "$@"; }
setup() { python3 "$cat/setup.py" --root / "$@"; }

# Registries sometimes refuse for a moment (rate limits, timeouts); keep trying for a few minutes.
for try in 1 2 3 4 5; do
  compose pull --quiet && break
  (( try == 5 )) && { echo "Couldn't download the apps" >&2; exit 1; }
  echo "Download failed; trying again in $((try * 30)) seconds" >&2
  sleep $((try * 30))
done

# The apps run whatever happens to their settings; a setting that can't be applied isn't worth a rollback.
setup prepare || echo "Couldn't refresh the apps' settings files" >&2
compose up -d --remove-orphans
setup connect || echo "Some app settings couldn't be applied again; the apps still work" >&2
setup link || echo "Seerr's settings couldn't be applied again; it still works" >&2
setup dashboard
# Keys created by the setup steps above go on the dashboard widgets.
set -a
. /etc/homeserver/secrets.env
set +a
compose up -d
