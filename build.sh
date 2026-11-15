#!/usr/bin/env bash
# Builds out/homeserver-usb.iso. Needs Docker and about 20 GB of free disk.
set -euo pipefail
cd "$(dirname "$0")"

images_list=server/usr/share/homeserver/images.list
mkdir -p build/images out

# Every image the compose file uses must be bundled, or offline installs break.
for ref in $(grep -oP '^\s*image:\s*\K\S+' server/usr/lib/homeserver/compose.yaml); do
  grep -q " $ref\$" "$images_list" || { echo "compose image $ref is missing from $images_list" >&2; exit 1; }
done

while read -r name ref; do
  [[ -z $name || $name == \#* ]] && continue
  out=build/images/$name.tar.zst
  [[ -f $out && ${REFRESH_IMAGES:-0} != 1 ]] && continue
  docker pull --platform linux/amd64 "$ref"
  docker save "$ref" | zstd -19 -T0 -q -o "$out.tmp"
  mv "$out.tmp" "$out"
done < "$images_list"

docker build -q -t homeserver-usb-builder builder >/dev/null
docker run --rm --privileged --hostname builder \
  -v "$PWD:/src:ro" -v "$PWD/build:/build" -v "$PWD/out:/out" \
  homeserver-usb-builder /src/builder/build-iso.sh

ls -lh out/homeserver-usb.iso
size=$(stat -c %s out/homeserver-usb.iso)
if (( size >= 2 * 1024 ** 3 )); then
  echo "warning: ISO is over 2 GiB and can't be attached to a GitHub release" >&2
fi
