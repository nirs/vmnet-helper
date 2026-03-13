<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Performance

We benchmarked vmnet-helper with 3 VMs types (vfkit, krunkit, qemu) in
all operation modes supported by the vmnet framework (shared, bridged,
host), in 3 directions (host to vm, vm to host, vm to vm), on 2 machines
(iMac M3, MacBook Pro M2 Max).

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

![vmnet-helper vs socket_vmnet - shared network](/performance/2025-08/M3/plot/vmnet-helper-vs-socket_vmnet/shared.png)
![vmnet-helper vs socket_vmnet - bridged network](/performance/2025-08/M3/plot/vmnet-helper-vs-socket_vmnet/bridged.png)

Tested on iMac M3 and macOS 15.6.1.

## Comparing different VMs

Performance depends on VM type and transfer direction.
[vfkit](https://github.com/crc-org/vfkit) performs better in all tests.
[qemu](https://www.qemu.org/) is up to *5 times slower* than vfkit.

![vmnet-helper drivers - shared network](/performance/2026-02/M3/plot/drivers/shared.png)
![vmnet-helper drivers - bridged network](/performance/2026-02/M3/plot/drivers/bridged.png)

Tested on iMac M3 and macOS 26.3.0.

## Offloading

On macOS 26.2 and later, krunkit provides close to native performance
when using offloading. On earlier macOS versions we see dramatically reduced
performance in host-to-vm use case.

Tested on iMac M3.

### macOS 26.3

![vmnet-helper offloading - shared network](/performance/2026-02/M3/plot/offloading/shared.png)
![vmnet-helper offloading - bridged network](/performance/2026-02/M3/plot/offloading/bridged.png)

### macOS 15.6

![vmnet-helper offloading - shared network](/performance/2025-08/M3/plot/offloading/shared.png)
![vmnet-helper offloading - bridged network](/performance/2025-08/M3/plot/offloading/bridged.png)
