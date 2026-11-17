#!/usr/bin/env bash
# Builds out/homeserver-usb.iso. Needs Docker and about 15 GB of free disk.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p build out

docker build -q -t homeserver-usb-builder builder >/dev/null
# The catalog the ISO falls back to without internet: only what every server always gets.
rm -rf build/catalog-minimal
mkdir -p build/catalog-minimal
cp -a catalog/. build/catalog-minimal/
rm -f build/catalog-minimal/release.sh
python3 - build/catalog-minimal/catalog.json <<'PY'
import json, sys
path = sys.argv[1]
cat = json.load(open(path))
groups = [g for g in cat["groups"] if g.get("always")]
keep = {a for g in groups for a in g["apps"]}
cat.update(version=0, groups=groups, apps={k: v for k, v in cat["apps"].items() if k in keep})
json.dump(cat, open(path, "w"), indent=2)
PY

version=$(git describe --tags --always --dirty 2>/dev/null || echo unknown)
docker run --rm --privileged --hostname builder -e VERSION="$version" \
  -v "$PWD:/src:ro" -v "$PWD/build:/build" -v "$PWD/out:/out" \
  homeserver-usb-builder /src/builder/build-iso.sh

ls -lh out/homeserver-usb.iso
size=$(stat -c %s out/homeserver-usb.iso)
if (( size >= 2 * 1024 ** 3 )); then
  echo "warning: ISO is over 2 GiB and can't be attached to a GitHub release" >&2
fi
