#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Example for using vmnet-client with QEMU.

MAC_ADDRESS="92:c9:52:b7:6c:08"
DISK_IMAGE="disk.img"
CIDATA_ISO="cidata.iso"
SERIAL_CONSOLE="ttyAMA0"

if [ ! -f "$DISK_IMAGE" ]; then
    ./download.sh "$DISK_IMAGE"
fi

# We create new iso for every run to enforce users scripts to run during
# startup and report the IP address. This is used by the integration tests.
./create-iso.sh "$MAC_ADDRESS" "$CIDATA_ISO" "$SERIAL_CONSOLE"

# Delete data from previous run.
rm -f serial.log ip-address

# Start qemu and vmnet-helper connected via unix datagram sockets.
/opt/vmnet-helper/bin/vmnet-client \
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
    -serial file:serial.log \
    -nographic \
    -nodefaults &

if ! timeout 3m bash -c "until grep -q 'example address: ' serial.log >/dev/null; do sleep 3; done"; then
  echo >&2 "Timeout waiting for vm IP address"
  exit 1
fi

# Write IP address to file for the tests.
grep 'example address: ' serial.log | cut -w -f 3 | tr -d '\r\n' > ip-address

# Interrupt to terminate vfkit and vmnet-helper.
wait
