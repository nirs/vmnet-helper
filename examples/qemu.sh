#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Example for using vmnet-client with QEMU.

MAC_ADDRESS="92:c9:52:b7:6c:08"
DISK_IMAGE="disk.img"
CIDATA_ISO="cidata.iso"

if [ ! -f "$DISK_IMAGE" ]; then
    ./download.sh "$DISK_IMAGE"
fi

if [ ! -f "$CIDATA_ISO" ]; then
    ./create-iso.sh "$MAC_ADDRESS" "$CIDATA_ISO"
fi

# Start qemu and vmnet-helper connected via unix datagram sockets.
/opt/vmnet-helper/bin/vmnet-client -- \
    qemu-system-aarch64 \
    -m 1024 \
    -cpu host \
    -machine virt,accel=hvf \
    -smp 1 \
    -drive if=pflash,format=raw,readonly=on,file=/opt/homebrew/share/qemu/edk2-aarch64-code.fd \
    -drive "file=$DISK_IMAGE,if=virtio,format=raw" \
    -netdev dgram,id=net1,local.type=fd,local.str=4 \
    -device "virtio-net-pci,netdev=net1,mac=$MAC_ADDRESS" \
    -drive "file=$CIDATA_ISO,id=cdrom0,if=none,format=raw,readonly=on" \
    -device virtio-scsi-pci,id=scsi0 \
    -device scsi-cd,bus=scsi0.0,drive=cdrom0 \
    -serial stdio \
    -nographic \
    -nodefaults \
