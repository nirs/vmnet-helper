#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Example for using vmnet-client with vfkit.

MAC_ADDRESS="92:c9:52:b7:6c:08"
DISK_IMAGE="disk.img"
CIDATA_ISO="cidata.iso"
SERIAL_CONSOLE="hvc0"

if [ ! -f "$DISK_IMAGE" ]; then
    ./download.sh "$DISK_IMAGE"
fi

# We create new iso for every run to enforce users scripts to run during
# startup and report the IP address. This is used by the integration tests.
./create-iso.sh "$MAC_ADDRESS" "$CIDATA_ISO" "$SERIAL_CONSOLE"

# Delete data from previous run.
rm -f serial.log ip-address

# Start vfkit and vmnet-helper connected via unix datagram sockets.
/opt/vmnet-helper/bin/vmnet-client \
    vfkit \
    --memory=1024 \
    --cpus=1 \
    --bootloader=efi,variable-store=efi-variable-store,create \
    "--device=usb-mass-storage,path=$CIDATA_ISO,readonly" \
    "--device=virtio-blk,path=$DISK_IMAGE" \
    "--device=virtio-net,fd=4,mac=$MAC_ADDRESS" \
    --device=virtio-serial,logFilePath=serial.log &

if ! timeout 3m bash -c "until grep -q 'example address: ' serial.log >/dev/null; do sleep 3; done"; then
  echo >&2 "Timeout waiting for vm IP address"
  exit 1
fi

# Write IP address to file for the tests.
grep 'example address: ' serial.log | cut -w -f 3 | tr -d '\r\n' > ip-address

# Interrupt to terminate vfkit and vmnet-helper.
wait
