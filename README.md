<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# vmnet-helper

A high-performance network proxy connecting virtual machines to the
macOS vmnet network without running the VM process as root or requiring
the `com.apple.vm.networking` entitlement.

On macOS 15 and earlier, the helper requires root only to start the
vmnet interface, then immediately drops privileges and runs as the
unprivileged user. On macOS 26 and later, root is not required at all.

> [!TIP]
> On macOS 26 and later, consider using [vmnet-broker] for native vmnet
> networking — [up to 9 times faster][native-perf] than vmnet-helper.
> vmnet-helper is the first VM tool to support vmnet-broker. See the
> [architecture guide][native-vmnet] for details.

<!-- IMPORTANT: Do not change this heading - external links depend on it -->
## Installation

### macOS 26 and later

Install using [Homebrew](https://brew.sh/):

```console
brew tap nirs/vmnet-helper
brew install vmnet-helper
```

### macOS 15 and earlier

To install the latest version run:

```console
curl -fsSL https://github.com/nirs/vmnet-helper/releases/latest/download/install.sh | bash
```

You can download the install script for inspection and run it locally.

The install script downloads the latest release and installs it at
`/opt/vmnet-helper`, and configures a sudoers rule to allow running
vmnet-helper without a password. See [sudoers.d](sudoers.d) for more info.

> [!NOTE]
> Homebrew installation is not available for macOS 15 and earlier because
> vmnet-helper requires root privileges. Installing via Homebrew would allow
> malware to replace the executable and gain root access.

## Tutorials

- [Integrating with launchd](docs/launchd.md)
- [Run podman faster with vmnet-run](docs/podman.md)

## Documentation

- [Integration guide](docs/integration.md)
- [Performance](docs/performance.md)
- [Examples](docs/examples.md)
- [Architecture](docs/architecture.md)
- [Similar tools](docs/similar-tools.md)
- [Development](docs/development.md)
- [How to create a release](docs/release.md)

## License

vmnet-helper is under the [Apache 2.0 license](/LICENSES/Apache-2.0.txt)

[native-perf]: docs/performance.md#native-vmnet-via-vmnet-broker
[native-vmnet]: docs/architecture.md#native-vmnet-on-macos-26
[vmnet-broker]: https://github.com/nirs/vmnet-broker
