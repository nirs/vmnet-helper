// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#ifndef OS_H
#define OS_H

struct os_version {
    int major;
    int minor;
    int point;
};

// Parse macOS product version (e.g. "15.4.1") into struct os_version.
// Returns 0 on success, -1 on error.
int os_product_version(struct os_version *v);

#endif // OS_H
