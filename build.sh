#!/usr/bin/env bash
# Builds out/homeserver-usb.iso. Needs Docker and about 15 GB of free disk.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p build out

docker build -q -t homeserver-usb-builder builder >/dev/null
docker run --rm --privileged --hostname builder \
  -v "$PWD:/src:ro" -v "$PWD/build:/build" -v "$PWD/out:/out" \
  homeserver-usb-builder /src/builder/build-iso.sh

ls -lh out/homeserver-usb.iso
size=$(stat -c %s out/homeserver-usb.iso)
if (( size >= 2 * 1024 ** 3 )); then
  echo "warning: ISO is over 2 GiB and can't be attached to a GitHub release" >&2
fi
