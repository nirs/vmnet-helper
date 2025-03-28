#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Download disk image for the examples.

DISK_IMAGE="${1:?Usage: disk.sh FILENAME}"
IMAGE_ARCH="arm64"
TMP_IMAGE="$DISK_IMAGE.tmp"

trap 'rm -f "$DISK_IMAGE.tmp"' EXIT

# Download qcow2 cloud image.
curl \
    --fail \
    --location \
    --output "$TMP_IMAGE" \
    "https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-$IMAGE_ARCH.img"

# Convert to raw so we can use this image for vfkit.
qemu-img convert -f qcow2 -O raw "$TMP_IMAGE" "$DISK_IMAGE"
