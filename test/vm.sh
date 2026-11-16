#!/usr/bin/env bash
# Boots out/homeserver-usb.iso in a VM the way a real install happens: the ISO as a USB stick,
# plus an NVMe and a SATA disk. No window opens; watch it over VNC (127.0.0.1:5907) or use test/qmp.py.
#
#   test/vm.sh            UEFI, with network, boot from the USB stick
#   test/vm.sh --bios     legacy BIOS instead of UEFI
#   test/vm.sh --offline  no network card
#   test/vm.sh --disk     boot the installed system (stick unplugged)
#   test/vm.sh --reset    wipe the VM disks first
#   test/vm.sh --window   show the VM in a window instead of headless
#   test/vm.sh --iso F    boot F instead of out/homeserver-usb.iso (e.g. an older release)
#   test/vm.sh --extra 3  three small (16 GB) SATA disks instead of the 500 GB one, to test pooling.
#                         Pass the same --extra when booting the installed system with --disk.
set -euo pipefail
cd "$(dirname "$0")/.."
state=build/vm
mkdir -p "$state"

firmware=uefi net=1 stick=1 display=none extra=0 iso=out/homeserver-usb.iso
while (( $# )); do
  arg=$1; shift
  case $arg in
    --extra) extra=$1; shift ;;
    --iso) iso=$1; shift ;;
    --bios) firmware=bios ;;
    --offline) net=0 ;;
    --disk) stick=0 ;;
    --window) display=gtk,zoom-to-fit=on ;;
    --reset) rm -f "$state"/*.qcow2 "$state"/OVMF_VARS.fd ;;
    *) echo "unknown option $arg" >&2; exit 1 ;;
  esac
done

# Different sizes so they're easy to tell apart in the installer.
[[ -f $state/nvme.qcow2 ]] || qemu-img create -q -f qcow2 "$state/nvme.qcow2" 64G
if (( extra )); then
  sata=()
  for i in $(seq "$extra"); do
    [[ -f $state/extra$i.qcow2 ]] || qemu-img create -q -f qcow2 "$state/extra$i.qcow2" 16G
    sata+=("$state/extra$i.qcow2")
  done
else
  [[ -f $state/sata.qcow2 ]] || qemu-img create -q -f qcow2 "$state/sata.qcow2" 500G
  sata=("$state/sata.qcow2")
fi

args=(
  -enable-kvm -cpu host -smp 4 -m 4096 -machine q35
  -device VGA,edid=on,xres=1920,yres=1080 -device qemu-xhci -device usb-tablet -device usb-kbd
  -display "$display" -vnc 127.0.0.1:7
  -qmp "unix:$state/qmp.sock,server,nowait"
  -serial "file:$state/serial.log"
  -drive "if=none,id=nvme,file=$state/nvme.qcow2" -device "nvme,drive=nvme,serial=NVME0001,bootindex=1"
  -device ahci,id=ahci
)
for i in "${!sata[@]}"; do
  args+=(-drive "if=none,id=sata$i,file=${sata[$i]}" -device "ide-hd,drive=sata$i,bus=ahci.$i")
done
if [[ $firmware == uefi ]]; then
  [[ -f $state/OVMF_VARS.fd ]] || cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$state/OVMF_VARS.fd"
  args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive "if=pflash,format=raw,file=$state/OVMF_VARS.fd")
fi
if (( stick )); then
  args+=(-drive "if=none,id=stick,format=raw,readonly=on,file=$iso"
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
