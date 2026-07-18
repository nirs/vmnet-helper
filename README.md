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

## Compatible VM drivers

vmnet-helper is integrated and tested with the following VM drivers.

| Driver    |       ★ | Description |
|-----------|--------:|-------------|
| [QEMU]    |  12,972 | Open-source machine emulator and virtualizer |
| [vfkit]   |     350 | macOS VM manager wrapping Apple's Virtualization.framework |
| [krunkit] |     266 | macOS wrapper for [libkrun] |

## Projects using vmnet-helper

The following projects use vmnet-helper to connect VMs to the vmnet network.

| Project          |       ★ | Description |
|------------------|--------:|-------------|
| [minikube]       |  31,668 | Local Kubernetes for development and CI |
| [renode]         |   2,383 | Embedded systems simulator |
| [anylinuxfs]     |   1,153 | Mounts Linux-supported filesystems on macOS via a microVM |
| [vibe]           |     848 | Linux VM sandbox for LLM agents on macOS |
| [nerdbox]        |     103 | containerd sandbox runtime for libkrun VMs on macOS |
| [ec1]            |       5 | Go-based VM orchestration |

## Compatible projects

The following projects use libkrun's unixgram API and can work with vmnet-helper.

| Project       |      ★ | Description |
|---------------|-------:|-------------|
| [microvm.nix] |  2,457 | NixOS MicroVMs |
| [libkrun]     |  1,793 | Library for running workloads in isolated VMs |
| [boxlite]     |  1,730 | Embeddable sandboxes for AI agents using libkrun |
| [libkrun-go]  |     47 | Go bindings for libkrun |
| [Box]         |     36 | MicroVM runtime using libkrun |
| [bux]         |      3 | Embedded micro-VM sandbox for AI agents using libkrun |
| [krun-api]    |      0 | Go wrapper for libkrun |

## Tutorials

- [Integrating with launchd](docs/launchd.md)
- [Flying podman high with vmnet and krunkit](docs/podman.md)
- [Freeing the whale with vmnet and krunkit](docs/docker.md)
- [FreeBSD VM with vmnet](docs/freebsd.md)

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

[Box]: https://github.com/A3S-Lab/Box
[QEMU]: https://gitlab.com/qemu-project/qemu
[anylinuxfs]: https://github.com/nohajc/anylinuxfs
[boxlite]: https://github.com/boxlite-ai/boxlite
[bux]: https://github.com/qntx/bux
[ec1]: https://github.com/walteh/ec1
[krun-api]: https://github.com/CGA1123/krun-api
[krunkit]: https://github.com/containers/krunkit
[libkrun-go]: https://github.com/mishushakov/libkrun-go
[libkrun]: https://github.com/containers/libkrun
[microvm.nix]: https://github.com/microvm-nix/microvm.nix
[minikube]: https://github.com/kubernetes/minikube
[native-perf]: docs/performance.md#native-vmnet-via-vmnet-broker
[native-vmnet]: docs/architecture.md#native-vmnet-on-macos-26
[nerdbox]: https://github.com/containerd/nerdbox
[renode]: https://github.com/renode/renode
[vfkit]: https://github.com/crc-org/vfkit
[vibe]: https://github.com/lynaghk/vibe
[vmnet-broker]: https://github.com/nirs/vmnet-broker
