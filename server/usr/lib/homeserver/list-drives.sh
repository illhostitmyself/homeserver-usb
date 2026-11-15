#!/bin/bash
# Writes the installer's "Extra drives" checklist: every disk except the USB stick it booted from.
# Entries are named "<model>, <size> (/dev/...)"; the homeserver step reads the path from the
# brackets (see main.py and setup-drives.sh).
set -uo pipefail
out=${HOMESERVER_DRIVES_OUT:-/run/homeserver/netinstall-drives.yaml}
mkdir -p "$(dirname "$out")"
live_disk=$(lsblk -no PKNAME "$(findmnt -no SOURCE /run/live/medium)" 2>/dev/null | head -1)

entries=()
while read -r name type size model; do
  [[ $type == disk && ${name#/dev/} != "$live_disk" ]] || continue
  model=$(printf '%b' "${model:-Drive}" | tr -d '"\\')
  entries+=("      - name: \"$model, $size ($name)\"" "        description: \"Erased, then added to the media storage\"")
done < <(lsblk -dnpr -o NAME,TYPE,SIZE,MODEL -e 7,11)

{
  echo '- name: "Extra drives"'
  if (( ${#entries[@]} > 2 )); then
    echo '  description: "Joined with your main drive as one storage. If one breaks, only its files are lost. Your main drive is skipped if ticked."'
  else
    echo '  description: "No other drives found. Everything goes on the drive you picked."'
  fi
  echo '  selected: false'
  echo '  expanded: true'
  echo '  packages:'
  printf '%s\n' "${entries[@]}"
} > "$out"
