#!/bin/bash
# Brings an installed Home Server up to this USB stick's version. $1 is its root partition.
# Never formats, and never touches users, passwords, app settings (/srv/appdata) or media (/srv/data).
#   - installs the Debian packages this version adds (needs internet; skipped without it)
#   - replaces the Home Server scripts and services with this version's
#   - installs the newest app catalog, and moves the apps to its versions the next time the server starts
set -uo pipefail
dev=$1
T=/mnt/homeserver
share=/usr/share/homeserver
step() { printf '\n  %s\n' "$*"; }
fail() { printf '\n  Update failed: %s\n  Nothing was erased. Your server still starts as before.\n' "$*"; exit 1; }

cleanup() {
  rm -f "$T/usr/sbin/policy-rc.d"
  umount -R "$T" 2>/dev/null
}
trap cleanup EXIT

step "Opening your server's disk..."
mkdir -p "$T"
mount "$dev" "$T" || fail "couldn't open $dev"
[[ -f $T/etc/homeserver/homeserver.env ]] || fail "no Home Server found on $dev"
for d in dev proc sys run; do mount --rbind "/$d" "$T/$d" && mount --make-rslave "$T/$d"; done
[[ -L $T/etc/resolv.conf ]] || mount --bind /etc/resolv.conf "$T/etc/resolv.conf"
# /boot, /home, /srv and the EFI partition, as the server mounts them. Extra-drive pools (mergerfs) aren't needed.
while read -r mp; do
  chroot "$T" mount "$mp" || fail "couldn't open the server's $mp partition"
done < <(chroot "$T" findmnt --fstab -rno TARGET -t ext4,vfat | grep -vx / | sort)
log=$T/var/log/homeserver-update.log
exec > >(tee -a "$log") 2>&1
echo "== $(date -u '+%F %T') update to $(cat $share/version 2>/dev/null)"

step "Adding new system packages..."
# Everything on the stick's list except what the installer removes from installed systems.
skip=$(sed -n '/try_remove:/,$s/^ *- //p' /etc/calamares/modules/packages.conf)
mapfile -t pkgs < <(grep -v '^#' $share/packages.list | grep . | grep -vxF "$skip")
printf '#!/bin/sh\nexit 101\n' > "$T/usr/sbin/policy-rc.d"
chmod +x "$T/usr/sbin/policy-rc.d"
mapfile -t missing < <(chroot "$T" dpkg-query -W -f '${Package} ${db:Status-Status}\n' "${pkgs[@]}" 2>/dev/null |
  awk '$2 == "installed" { print $1 }' | grep -vxF -f - <(printf '%s\n' "${pkgs[@]}"))
if (( ${#missing[@]} == 0 )); then
  echo "  Nothing new."
elif chroot "$T" apt-get update -qq >>"$log" 2>&1; then
  echo "  ${missing[*]}"
  # apt's own output only goes to the log.
  DEBIAN_FRONTEND=noninteractive chroot "$T" apt-get install -y -q --no-install-recommends "${missing[@]}" \
    >>"$log" 2>&1 || fail "couldn't install ${missing[*]} (details in /var/log/homeserver-update.log)"
else
  echo "  No internet, skipped: ${missing[*]}"
fi
rm -f "$T/usr/sbin/policy-rc.d"

step "Updating Home Server..."
# Unless the server already has newer Home Server files, from an app catalog update (server-rev is the
# time of their last change in the repo).
have_rev=$(cat "$T$share/server-rev" 2>/dev/null || echo 0)
if (( $(cat $share/server-rev 2>/dev/null || echo 0) >= have_rev )); then
  grub=0
  while read -r f; do
    cmp -s "/$f" "$T/$f" && continue
    install -D -m "$(stat -c %a "/$f")" "/$f" "$T/$f" || fail "couldn't copy /$f"
    [[ $f == etc/default/grub.d/* ]] && grub=1
  done < $share/server-files
  (( grub )) && { chroot "$T" update-grub >>"$log" 2>&1 || echo "  Couldn't update the boot menu (details in the log)."; }
  for f in packages.list server-files server-rev; do install -D -m 644 "$share/$f" "$T$share/$f"; done
  chmod 0440 "$T"/etc/sudoers.d/homeserver-*
else
  echo "  The server already has newer Home Server files from the app catalog."
fi
install -D -m 644 "$share/version" "$T$share/version"
chroot "$T" systemctl enable homeserver-kiosk.service homeserver-firstboot.service homeserver.service \
  homeserver-refresh.service >/dev/null 2>&1 || fail "couldn't switch on the Home Server services"

# The app catalog the installer fetched (or the minimal one on the stick), unless the server already
# has a newer one. Before 0.4.0 its files lived in /usr/lib/homeserver.
version() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$1/catalog.json" 2>/dev/null; }
have=$(version "$T/var/lib/homeserver/catalog") got=$(version /run/homeserver/catalog)
if [[ -z $have ]] || (( ${got:-0} > have )); then
  mkdir -p "$T/var/lib/homeserver"
  rm -rf "$T/var/lib/homeserver/catalog.new"
  cp -a /run/homeserver/catalog "$T/var/lib/homeserver/catalog.new" || fail "couldn't copy the app catalog"
  rm -rf "$T/var/lib/homeserver/catalog"
  mv "$T/var/lib/homeserver/catalog.new" "$T/var/lib/homeserver/catalog"
  echo "  App catalog ${have:-none} -> $got"
fi
rm -f "$T/usr/lib/homeserver/compose.yaml" "$T/usr/lib/homeserver/setup.py" "$T/usr/lib/homeserver/configure-apps.sh"

step "Your apps move to the versions in the app catalog the next time the server starts."
mkdir -p "$T/var/lib/homeserver"
touch "$T/var/lib/homeserver/refresh-images"
echo "== done"
