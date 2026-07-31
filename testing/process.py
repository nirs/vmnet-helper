# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import subprocess

# Avoid importing subprocess in callers.
from subprocess import PIPE


def run(*args, stdout=None, stderr=None, cwd=None, check=True):
    """
    Runs a command as unprivilegd user, waits for it to complete, then returns a
    CompletedProcess instance.
    """
    return subprocess.run(
        args,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        check=check,
    )


def start(*args, stdout=None, stderr=None, pass_fds=()):
    """
    Starts a new process as unprivileged user. Return subprocess.Popen()
    instance for waiting and terminating the new process.
    """
    return subprocess.Popen(
        args,
        stdout=stdout,
        stderr=stderr,
        pass_fds=pass_fds,
    )
