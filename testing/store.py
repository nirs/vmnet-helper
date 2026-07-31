# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import os

from . import privileges

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, ".vmnet-helper")


def vm_path(*parts):
    """
    Build path for vm files.
    """
    return os.path.join(BASE, "vms", *parts)


def cache_path(*parts):
    """
    Build path for cached files.
    """
    return os.path.join(BASE, "cache", *parts)


def ensure_vm_dir(*parts):
    """
    Ensure that vm directory exists.
    """
    return _ensure_directory(BASE, "vms", *parts)


def ensure_cache_dir(*parts):
    """
    Ensure that cache directory exists.
    """
    return _ensure_directory(BASE, "cache", *parts)


def _ensure_directory(*parts):
    """
    Ensures directory and all intermediate directories from HOME exist with
    specified mode and owned by unprivileged user and group. Returns the
    directory path.

    When running in CI as root, we want to create directories owned by SUDO_USER
    and SUDO_GROUP so we can run the vm and helper as unprivileged user.  We
    cannot use os.makedirs() since it does not change ownership.
    """
    mode = 0o700
    uid, gid = privileges.creds()
    path = HOME  # HOME exists and have right owner.
    for part in parts:
        path = os.path.join(path, part)
        try:
            os.mkdir(path, mode=mode)
        except FileExistsError:
            pass  # Should have right owner.
        else:
            if uid and gid:
                os.chown(path, uid, gid)
    return path


def silent_remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
