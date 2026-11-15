#!/usr/bin/env bash
# Boots out/homeserver-usb.iso in a VM the way a real install happens: the ISO as a USB stick,
# plus an NVMe and a SATA disk. No window opens; watch it over VNC (127.0.0.1:5907) or use test/qmp.py.
#
#   test/vm.sh            UEFI, with network, boot from the USB stick
#   test/vm.sh --bios     legacy BIOS instead of UEFI
#   test/vm.sh --offline  no network card
#   test/vm.sh --disk     boot the installed system (stick unplugged)
#   test/vm.sh --reset    wipe the VM disks first
set -euo pipefail
cd "$(dirname "$0")/.."
state=build/vm
mkdir -p "$state"

firmware=uefi net=1 stick=1
for arg in "$@"; do
  case $arg in
    --bios) firmware=bios ;;
    --offline) net=0 ;;
    --disk) stick=0 ;;
    --reset) rm -f "$state"/*.qcow2 "$state"/OVMF_VARS.fd ;;
    *) echo "unknown option $arg" >&2; exit 1 ;;
  esac
done

for d in nvme sata; do
  [[ -f $state/$d.qcow2 ]] || qemu-img create -q -f qcow2 "$state/$d.qcow2" 64G
done

args=(
  -enable-kvm -cpu host -smp 4 -m 4096 -machine q35
  -device virtio-vga -device qemu-xhci -device usb-tablet -device usb-kbd
  -display none -vnc 127.0.0.1:7
  -qmp "unix:$state/qmp.sock,server,nowait"
  -serial "file:$state/serial.log"
  -drive "if=none,id=nvme,file=$state/nvme.qcow2" -device "nvme,drive=nvme,serial=NVME0001,bootindex=1"
  -drive "if=none,id=sata,file=$state/sata.qcow2" -device ahci,id=ahci -device "ide-hd,drive=sata,bus=ahci.0,bootindex=2"
)
if [[ $firmware == uefi ]]; then
  [[ -f $state/OVMF_VARS.fd ]] || cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$state/OVMF_VARS.fd"
  args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive "if=pflash,format=raw,file=$state/OVMF_VARS.fd")
fi
if (( stick )); then
  args+=(-drive "if=none,id=stick,format=raw,readonly=on,file=out/homeserver-usb.iso"
         -device "usb-storage,drive=stick,bootindex=0")
fi
if (( net )); then
  fwd=""
  for pair in 18022:22 18080:80 19090:9090 18096:8096 15055:5055 18989:8989 17878:7878 19696:9696 18081:8080; do
    fwd+=",hostfwd=tcp:127.0.0.1:${pair%%:*}-:${pair##*:}"
  done
  args+=(-nic "user,model=virtio-net-pci$fwd")
else
  args+=(-nic none)
fi

exec qemu-system-x86_64 "${args[@]}"
