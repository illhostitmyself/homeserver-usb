#!/bin/bash
# Runs on the first start of the installed system, and again on the next boot if it failed.
set -euo pipefail
lib=/usr/lib/homeserver

for f in /var/lib/homeserver/images/*.tar.zst; do
  [[ -e $f ]] || continue
  zstd -dc "$f" | docker load
  rm -f "$f"
done

python3 "$lib/setup.py" prepare
set -a
. /etc/homeserver/homeserver.env
. /etc/homeserver/compose.env
set +a

if [[ " $APPS " == *" files "* ]]; then
  pw=$(cat /etc/homeserver/owner-password 2>/dev/null || cat /etc/homeserver/app-password)
  printf '%s\n%s\n' "$pw" "$pw" | smbpasswd -s -a "$OWNER"
fi

docker compose -f "$lib/compose.yaml" up -d
python3 "$lib/setup.py" connect

rm -f /etc/homeserver/owner-password
touch /var/lib/homeserver/setup-done
