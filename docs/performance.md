<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Performance

We benchmarked vmnet-helper with 3 VM types (vfkit, krunkit, qemu) in
all operation modes supported by the vmnet framework (shared, bridged,
host), in 3 directions (host to vm, vm to host, vm to vm), on 3 machines
(iMac M3, MacBook Pro M2 Max, MacBook Pro M5).

See the [performance](/performance) directory for full test results and
the [development guide](/docs/development.md#benchmarking) for running
your own benchmarks.

## Comparing to socket_vmnet

Comparing to [socket_vmnet](https://github.com/lima-vm/socket_vmnet)
with [lima](https://github.com/lima-vm/lima) using VZ and qemu vm types,
vmnet-helper with [vfkit](https://github.com/crc-org/vfkit) is up to *10
times faster*, and vmnet-helper with [qemu](https://www.qemu.org/) is up
to *3 times faster*. See [similar tools](/docs/similar-tools.md) for a
detailed comparison.

![vmnet-helper vs socket_vmnet - shared network](/performance/results/2025-08/M3/plot/vmnet-helper-vs-socket_vmnet/shared.png)
![vmnet-helper vs socket_vmnet - bridged network](/performance/results/2025-08/M3/plot/vmnet-helper-vs-socket_vmnet/bridged.png)

Tested on iMac M3 and macOS 15.6.1.

## Comparing different VMs

Performance depends on VM type and transfer direction.
[vfkit](https://github.com/crc-org/vfkit) performs better in all tests.
[qemu](https://www.qemu.org/) is up to *5 times slower* than vfkit.

![vmnet-helper drivers - shared network](/performance/results/2026-08/M5/plot/drivers/shared.png)
![vmnet-helper drivers - bridged network](/performance/results/2026-08/M5/plot/drivers/bridged.png)

Tested on MacBook Pro M5 and macOS 26.5.2.

## Offloading

With offloading enabled, krunkit provides close to native performance.

Tested on MacBook Pro M5 and macOS 26.5.2.

![vmnet-helper offloading - shared network](/performance/results/2026-08/M5/plot/offloading/shared.png)
![vmnet-helper offloading - bridged network](/performance/results/2026-08/M5/plot/offloading/bridged.png)

> [!IMPORTANT]
> For best performance do not mix VMs using offloading and VMs not using
> offloading on the same bridge. This disables TSO on the bridge, which
> degrades TX performance to 1.5 Gbits/sec.

## Native vmnet via vmnet-broker

On macOS 26 and later, VMs using the Virtualization framework can use
vmnet natively via [vmnet-broker], without vmnet-helper in the data path.
Native vmnet is up to *2 times faster* compared to krunkit with
offloading, and up to *9 times faster* compared to krunkit without
offloading. Only shared network is supported in native vmnet mode.

![vmnet-helper vs vmnet-broker - shared network](/performance/results/2026-02/M3/plot/vmnet-helper%20vs%20vmnet-broker/shared.png)

Tested on iMac M3 and macOS 26.3.0.

[vmnet-broker]: https://github.com/nirs/vmnet-broker
