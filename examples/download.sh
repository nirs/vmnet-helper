#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Download disk image for the examples.

DISK_IMAGE="${1:?Usage: disk.sh FILENAME}"
TMP_IMAGE="$DISK_IMAGE.tmp"
MACHINE=$(uname -m)

case "$MACHINE" in
x86_64)
    IMAGE_ARCH="amd64"
    ;;
arm64)
    IMAGE_ARCH="arm64"
    ;;
*)
    echo "Unsupported machine: $MACHINE"
    exit 1
esac

trap 'rm -f "$DISK_IMAGE.tmp"' EXIT

# Download qcow2 cloud image.
curl \
    --fail \
    --location \
    --output "$TMP_IMAGE" \
    "https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-$IMAGE_ARCH.img"

# Resize to make room for updates.
qemu-img resize -f qcow2 "$TMP_IMAGE" 6g

# Convert to raw so we can use this image for vfkit.
qemu-img convert -f qcow2 -O raw "$TMP_IMAGE" "$DISK_IMAGE"
