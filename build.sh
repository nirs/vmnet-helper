#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

set -eu

build_dir="${1:?Usage: $0 BUILD_DIR}"

for arch in arm64 x86_64; do
    meson setup "$build_dir/$arch" --cross-file "$arch.ini"
    meson compile -C "$build_dir/$arch"
done

for prog in vmnet-helper vmnet-client; do
    lipo -create "$build_dir/x86_64/$prog" "$build_dir/arm64/$prog" -output "$build_dir/$prog"
done

# Ad-hoc signing to allow creation of vmnet interfaces without root.
codesign --force --verbose --entitlements entitlements.plist --sign - "$build_dir/vmnet-helper"
codesign --display --entitlements - "$build_dir/vmnet-helper"

root_dir="$build_dir/root"
prefix="/opt/vmnet-helper"

rm -rf "$root_dir"

bin_dir="$root_dir$prefix/bin"

install -v -d -m 0755 "$bin_dir"
for prog in vmnet-helper vmnet-client; do
    install -v -m 0755 $build_dir/$prog $bin_dir
done

sudoers_dir="$root_dir$prefix/share/doc/vmnet-helper/sudoers.d"

install -v -d -m 0755 "$sudoers_dir"
install -v -m 0644 sudoers.d/README.md "$sudoers_dir"
install -v -m 0644 sudoers.d/vmnet-helper "$sudoers_dir"

archive="$PWD/$build_dir/vmnet-helper.tar"

# Make content reproducible by using commit time instead of build time.
commit_time=$(git log -1 --pretty=%ct)
commit_time_iso8601=$(date -u -Iseconds -r "$commit_time" | sed -e 's/+00:00/Z/')
find "$root_dir" -exec touch -d "$commit_time_iso8601" {} \;

rm -f "$archive"

# Create reproducible archive by sorting the files and overriding uid/gid.
(cd "$root_dir" && find -s .) | \
    tar --create \
        --file $archive \
        --uid 0 \
        --gid 0 \
        --verbose \
        --no-recursion \
        --directory "$root_dir" \
        --files-from /dev/stdin

# Create reproducible file by disabling filename and timestamp.
rm -f "$archive.gz"
gzip -9 --no-name $archive
