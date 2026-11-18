#!/bin/bash
# Installs the Home Server files this catalog carries (server/: scripts, services, the Cockpit page, the
# sudo rule) and the Debian packages they need, so they update with the catalog instead of needing a new
# USB stick. ROOT is the system: / from update.sh, or the new disk from the installer (files only).
# Skipped if the system has newer files (from a newer USB stick). With the same server-rev, files that
# differ are put back (an older stick's update copied its own).
set -euo pipefail
cat=$(dirname "$(readlink -f "$0")")
root=${1:-/}
root=${root%/}
share=$root/usr/share/homeserver
[[ -d $cat/server && -f $cat/server-rev ]] || exit 0
new=$(<"$cat/server-rev") have=$(cat "$share/server-rev" 2>/dev/null || echo 0)
if (( new < have )); then
  echo "Home Server files: this server already has newer ones"
  exit 0
fi

if [[ -z $root ]]; then
  mapfile -t pkgs < "$cat/server-packages.list"
  mapfile -t missing < <(dpkg-query -W -f '${Package} ${db:Status-Status}\n' "${pkgs[@]}" 2>/dev/null |
    awk '$2 == "installed" { print $1 }' | grep -vxF -f - <(printf '%s\n' "${pkgs[@]}") || true)
  if (( ${#missing[@]} )); then
    echo "Installing system packages: ${missing[*]}"
    { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends "${missing[@]}"; } \
      >/dev/null || { echo "Couldn't install ${missing[*]}" >&2; exit 1; }
  fi
fi

# A broken sudo rule would lock the owner out of administration; check before installing it.
for f in "$cat"/server/etc/sudoers.d/*; do
  visudo -cqf "$f" || { echo "The sudo rule $f is broken; not installing the Home Server files" >&2; exit 1; }
done
changed=0 grub=0
while read -r f; do
  cmp -s "$cat/server/$f" "$root/$f" && continue
  install -D -m "$(stat -c %a "$cat/server/$f")" "$cat/server/$f" "$root/$f"
  changed=$((changed + 1))
  [[ $f == etc/default/grub.d/* ]] && grub=1
done < <(cd "$cat/server" && find . -type f -printf '%P\n' | sort)
chmod 0440 "$root"/etc/sudoers.d/homeserver-*
mkdir -p "$share"
(cd "$cat/server" && find . -type f -printf '%P\n' | sort) > "$share/server-files"
cp "$cat/server-packages.list" "$share/packages.list"
echo "$new" > "$share/server-rev"
units=(homeserver-kiosk.service homeserver-firstboot.service homeserver.service homeserver-refresh.service)
if [[ -z $root ]]; then
  systemctl daemon-reload
  systemctl --quiet enable "${units[@]}"
else
  chroot "$root" systemctl --quiet enable "${units[@]}"
fi
if (( grub )); then
  if [[ -z $root ]]; then update-grub; else chroot "$root" update-grub; fi >/dev/null 2>&1 ||
    echo "Couldn't update the boot menu; the new start-up settings apply after the next update" >&2
fi
echo "Home Server files: $changed updated"
