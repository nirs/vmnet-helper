# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import os


def creds():
    """
    Return (user, group) for dropping privileges when running as root.

    When the test runs as root (e.g. via sudo for mDNS access in CI),
    the VM command must run as the unprivileged user so its files and
    sockets are accessible by vmnet-helper after it drops privileges.

    Uses SUDO_UID/SUDO_GID like vmnet-helper does. Returns (None, None)
    when not running as root.
    """
    if os.geteuid() != 0:
        return None, None

    sudo_uid = os.environ.get("SUDO_UID")
    uid = int(sudo_uid) if sudo_uid else os.getuid()

    # Running as root directly (not via sudo) — no unprivileged user to drop to.
    if uid == 0:
        return None, None

    sudo_gid = os.environ.get("SUDO_GID")
    gid = int(sudo_gid) if sudo_gid else os.getgid()

    return uid, gid
