#!/bin/sh
# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Create a source tarball for testing builds from release archives.

set -e

mkdir -p build/archive
git archive --format=tar.gz --prefix=vmnet-helper/ HEAD -o build/archive/vmnet-helper.tar.gz
