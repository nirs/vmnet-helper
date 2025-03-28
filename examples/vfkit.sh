#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Example for using vmnet-client with vfkit.

MAC_ADDRESS="92:c9:52:b7:6c:08"
DISK_IMAGE="disk.img"
CIDATA_ISO="cidata.iso"

if [ ! -f "$DISK_IMAGE" ]; then
    ./download.sh "$DISK_IMAGE"
fi

if [ ! -f "$CIDATA_ISO" ]; then
    ./create-iso.sh "$MAC_ADDRESS" "$CIDATA_ISO"
fi

# Start vfkit and vmnet-helper connected via unix datagram sockets.
/opt/vmnet-helper/bin/vmnet-client \
    vfkit \
    --memory=1024 \
    --cpus=1 \
    --bootloader=efi,variable-store=efi-variable-store,create \
    "--device=usb-mass-storage,path=$CIDATA_ISO,readonly" \
    "--device=virtio-blk,path=$DISK_IMAGE" \
    "--device=virtio-net,fd=4,mac=$MAC_ADDRESS" \
    --device virtio-serial,stdio \
