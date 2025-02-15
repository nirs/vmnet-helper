# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import os

HOME = os.path.expanduser("~/.vmnet-helper")


def vm_path(*parts):
    """
    Build path for vm files.
    """
    return os.path.join(HOME, "vms", *parts)


def cache_path(*parts):
    """
    Build path for cached files.
    """
    return os.path.join(HOME, "cache", *parts)


def silent_remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
