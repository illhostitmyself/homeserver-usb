#!/bin/bash
# Run by the installer with the new system mounted at $1. Starts a temporary Docker daemon that
# stores everything on the new disk, then downloads and sets up the apps.
# If setup fails the install still finishes, and homeserver-firstboot.service retries it.
set -euo pipefail
root=${1%/}
. "$root/etc/homeserver/homeserver.env"

systemctl stop docker.socket docker.service 2>/dev/null || true
systemd-run --quiet --unit=homeserver-install-docker --collect \
  dockerd --data-root "$root/var/lib/docker" --exec-root /run/homeserver-docker --pidfile /run/homeserver-docker.pid
trap 'systemctl stop homeserver-install-docker' EXIT
for _ in $(seq 60); do docker info >/dev/null 2>&1 && break; sleep 1; done
docker info >/dev/null || { echo "Docker didn't start" >&2; exit 1; }

# The catalog's Home Server files, if they're newer than this USB stick's.
"$root/var/lib/homeserver/catalog/server.sh" "$root" || echo "Couldn't install the app catalog's Home Server files" >&2
if "$root/var/lib/homeserver/catalog/configure-apps.sh" "$root"; then
  echo "Apps are set up"
else
  echo "App setup failed; it will be retried when the server first starts" >&2
fi
docker compose -p homeserver down || true
