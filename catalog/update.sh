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

compose pull --quiet
compose up -d --remove-orphans
python3 "$cat/setup.py" --root / dashboard
