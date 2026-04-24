#!/bin/sh
# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Format all source code.

set -e

python3 -m black testing/ run bench building/gen-version
