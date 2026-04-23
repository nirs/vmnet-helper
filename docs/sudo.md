<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Running vmnet-helper with sudo

On **macOS 26** and later, vmnet-helper runs as a regular user — do
not use `sudo`.

On **macOS 15** and earlier, vmnet-helper requires root privileges.
See [sudoers.d](/sudoers.d/) for details on configuring sudoers for
vmnet-helper.

When running interactively, `sudo` will prompt for a password if
needed:

```console
sudo /opt/vmnet-helper/bin/vmnet-helper --socket /tmp/vmnet-helper.sock ...
```

For automation, use `--non-interactive` to avoid hanging indefinitely
waiting for a password. With `--non-interactive`, `sudo` fails
immediately so you can handle the error:

```console
sudo --non-interactive \
    /opt/vmnet-helper/bin/vmnet-helper --socket /tmp/vmnet-helper.sock ...
```

## Passing file descriptor with sudo

When using `--fd`, you must use `--close-from` to prevent `sudo`
from closing the file descriptor before the helper starts. By
default, `sudo` closes all file descriptors above stderr (fd 2).
`--close-from=4` keeps fd 3 open for the helper.

```console
sudo --close-from=4 /opt/vmnet-helper/bin/vmnet-helper --fd 3 ...
```

This requires the `closefrom_override` option in the sudoers
configuration (enabled by the install script). See
[sudoers.d](/sudoers.d/) for details.

> [!WARNING]
> On managed Macs where the sudoers configuration cannot be modified,
> `--close-from` is not available and `--fd` cannot be used with
> `sudo`. Use `--socket` instead. This is why [minikube always uses
> `--socket`][minikube-vmnet].

## Using passwordless sudo

For smooth integration, the user should configure passwordless sudo
during installation. However, passwordless sudo may not be available:

- The user skipped the sudoers configuration during install
- The machine policy prevents modifying sudoers (e.g. managed
  corporate Macs)

The `--non-interactive` option tells `sudo` to fail instead of
prompting for a password. Use it to detect whether passwordless
sudo is available, and fall back to a password prompt if not:

1. Try `sudo --non-interactive vmnet-helper --version`
2. If it succeeds, passwordless sudo is available — use
   `sudo` to start the helper
3. If it fails and interaction is possible, run `sudo --validate`
   to prompt for a password and cache the credentials
4. Start the helper with `sudo`, which now succeeds using the
   cached credentials (valid for ~5 minutes)

## Reference implementations

- [run.c](/run.c) — vmnet-run's sudo handling, including
  `--non-interactive`, `--close-from`, and `closefrom_override`
- [minikube's vmnet integration][minikube-vmnet] — uses `--socket`
  to avoid `closefrom_override`, and falls back to interactive
  `sudo --validate` when passwordless sudo is not available

[minikube-vmnet]: https://github.com/kubernetes/minikube/blob/799c248d9faccedf7fc6af377bb4464dbebf431f/pkg/drivers/common/vmnet/vmnet.go
