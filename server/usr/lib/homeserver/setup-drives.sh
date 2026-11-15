#!/bin/bash
# Run by the installer with the new system mounted at $1. Erases the extra drives ticked in the
# installer and pools them with the main drive's data folder using mergerfs:
#   /srv/main            data folder on the main drive's /srv partition
#   /mnt/disks/diskN     one ext4 filesystem per extra drive
#   /srv/data            mergerfs pool of all of them, which the apps use
# A dead drive only loses the files that were on it, and each drive can be read on its own.
set -euo pipefail
root=${1%/}
list=$root/etc/homeserver/drives
[[ -s $list ]] || exit 0
. "$root/etc/homeserver/homeserver.env"
uid=$(chroot "$root" id -u "$OWNER")
gid=$(chroot "$root" id -g "$OWNER")
main_disk=/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE "$root/srv")" | head -1)
live_disk=/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /run/live/medium)" 2>/dev/null | head -1)

# Same folder layout on every drive, so new folders spread over all of them (see category.create).
skeleton() {
  for d in torrents/{movies,tv,books,audiobooks} media/{movies,tv,books,audiobooks,podcasts}; do
    mkdir -p "$1/$d"
  done
  chown -R "$uid:$gid" "$1"
}

branches=(/srv/main)
n=0
while read -r dev; do
  [[ -b $dev && $dev != "$main_disk" && $dev != "$live_disk" ]] || { echo "Skipping $dev"; continue; }
  n=$((n + 1))
  echo "Erasing $dev for the storage pool"
  wipefs -a "$dev"
  parted -s "$dev" mklabel gpt mkpart data ext4 1MiB 100%
  udevadm settle
  part=$(lsblk -lnpo NAME,TYPE "$dev" | awk '$2 == "part" {print $1; exit}')
  mkfs.ext4 -q -F -L "data$n" "$part"
  mnt=/mnt/disks/disk$n
  # Immutable while unmounted, so a missing drive can't silently fill the system drive.
  mkdir -p "$root$mnt"
  chattr +i "$root$mnt"
  mount "$part" "$root$mnt"
  skeleton "$root$mnt"
  echo "UUID=$(blkid -s UUID -o value "$part") $mnt ext4 defaults,noatime,nofail 0 2" >> "$root/etc/fstab"
  branches+=("$mnt")
done < "$list"
(( n > 0 )) || exit 0
mkdir -p "$root/srv/main"
skeleton "$root/srv/main"

# epmfs: new files go to the drive with the most free space among those that already have the
# folder, so a folder's contents stay together and hardlinks (TRaSH) mostly stay on one drive.
options=defaults,allow_other,use_ino,cache.files=off,dropcacheonclose=true,category.create=epmfs,moveonenospc=true,minfreespace=20G,fsname=data
echo "$(IFS=:; echo "${branches[*]}") /srv/data fuse.mergerfs $options,nofail 0 0" >> "$root/etc/fstab"
mkdir -p "$root/srv/data" "$root/etc/systemd/system/docker.service.d"
printf '[Unit]\nRequiresMountsFor=/srv/data\n' > "$root/etc/systemd/system/docker.service.d/wait-for-data.conf"

# Mount the pool now too, so the app setup later in the install writes into it.
mergerfs -o "${options//defaults,/}" "$(IFS=:; echo "${branches[*]/#/$root}")" "$root/srv/data"
