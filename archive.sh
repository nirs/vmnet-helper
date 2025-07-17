#!/bin/sh

set -eu
set -o pipefail

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Create reproducible archive.
# Derived from https://github.com/lima-vm/socket_vmnet/blob/master/Makefile

build_dir="${1:?Usage: $0 BUILD_DIR}"

# Install to root directory.
rm -rf "$build_dir/root"
DESTDIR=root meson install -C "$build_dir"

machine=$(uname -m)
archive="$PWD/$build_dir/vmnet-helper-$machine.tar"

# Make content reproducible by using commit time instead of build time.
commit_time=$(git log -1 --pretty=%ct)
commit_time_iso8601=$(date -u -Iseconds -r "$commit_time" | sed -e 's/+00:00/Z/')
find "$build_dir/root" -exec touch -d "$commit_time_iso8601" {} \;

# Create reproducible archive by sorting the files and overriding uid/gid.
(cd "$build_dir/root" && find -s .) | \
    tar --create \
        --file $archive \
        --uid 0 \
        --gid 0 \
        --verbose \
        --no-recursion \
        --directory "$build_dir/root" \
        --files-from /dev/stdin

# Create reproducible file by disabling filename and timestamp.
gzip -9 --no-name $archive
