# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import subprocess

# Avoid importing subprocess in callers.
from subprocess import PIPE

from . import privileges


def run(*args, stdout=None, stderr=None, cwd=None, check=True):
    """
    Runs a command as unprivilegd user, waits for it to complete, then returns a
    CompletedProcess instance.
    """
    uid, gid = privileges.creds()
    return subprocess.run(
        args,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        check=check,
        user=uid,
        group=gid,
    )


def start(*args, stdout=None, stderr=None, pass_fds=()):
    """
    Starts a new process as unprivileged user. Return subprocess.Popen()
    instance for waiting and terminating the new process.
    """
    uid, gid = privileges.creds()
    return subprocess.Popen(
        args,
        stdout=stdout,
        stderr=stderr,
        pass_fds=pass_fds,
        user=uid,
        group=gid,
    )
