#!/bin/bash
# Writes the installer's "Extra drives" checklist: every disk except the USB stick it booted from.
# Each entry is a device path that the homeserver step picks up (see main.py and setup-drives.sh).
set -uo pipefail
out=${HOMESERVER_DRIVES_OUT:-/run/homeserver/netinstall-drives.yaml}
mkdir -p "$(dirname "$out")"
live_disk=$(lsblk -no PKNAME "$(findmnt -no SOURCE /run/live/medium)" 2>/dev/null | head -1)

entries=()
while read -r name type size model; do
  [[ $type == disk && ${name#/dev/} != "$live_disk" ]] || continue
  model=$(printf '%b' "${model:-Drive}" | tr -d '"\\')
  entries+=("      - name: \"$name\"" "        description: \"$model, $size\"")
done < <(lsblk -dnpr -o NAME,TYPE,SIZE,MODEL -e 7,11)

{
  echo '- name: "Extra drives"'
  if (( ${#entries[@]} > 2 )); then
    echo '  description: "Ticked drives are ERASED and added to the storage for your movies, shows and books"'
  else
    echo '  description: "No other drives found. Everything goes on the drive you picked."'
  fi
  echo '  selected: false'
  echo '  expanded: true'
  echo '  packages:'
  printf '%s\n' "${entries[@]}"
} > "$out"
