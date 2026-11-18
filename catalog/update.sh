#!/bin/bash
# Run on an installed server right after this catalog release replaced the previous one
# (/var/lib/homeserver/catalog). Moves the apps to the versions pinned here and rewrites the
# dashboard. Anything a release needs beyond that (a moved setting, a renamed folder) goes here too,
# written so it's safe to run more than once.
set -euo pipefail
cat=$(dirname "$(readlink -f "$0")")
set -a
. /etc/homeserver/homeserver.env
. /etc/homeserver/compose.env
. /etc/homeserver/secrets.env
SRV=/srv
set +a
compose() { docker compose -f "$cat/compose.yaml" "$@"; }

# Registries sometimes refuse for a moment (rate limits, timeouts); keep trying for a few minutes.
for try in 1 2 3 4 5; do
  compose pull --quiet && break
  (( try == 5 )) && { echo "Couldn't download the apps" >&2; exit 1; }
  echo "Download failed; trying again in $((try * 30)) seconds" >&2
  sleep $((try * 30))
done
compose up -d --remove-orphans
python3 "$cat/setup.py" --root / dashboard
