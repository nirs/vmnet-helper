<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Performance

We benchmarked vmnet-helper with 3 VMs types (vfkit, krunkit, qemu) in
all operation modes supported by the vmnet framework (shared, bridged,
host), in 3 directions (host to vm, vm to host, vm to vm), on 2 machines
(iMac M3, MacBook Pro M2 Max) running macOS 15.6.1.

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

## Comparing different VMs

Performance depends on VM type and transfer direction.
[vfkit](https://github.com/crc-org/vfkit) performs better in all tests.
[qemu](https://www.qemu.org/) is up to *5 times slower* than vfkit.

![vmnet-helper drivers - shared network](/performance/2025-08/M3/plot/drivers/shared.png)
![vmnet-helper drivers - bridged network](/performance/2025-08/M3/plot/drivers/bridged.png)

## Offloading

With krunkit we can use the vmnet framework offloading options to dramatically
increase performance for vm-to-host and vm-to-vm cases. However using offloading
also dramatically reduces performance in host-to-vm case. If you have a workload
that use mostly vm to vm traffic you may benefit from offloading.

![vmnet-helper offloading - shared network](/performance/2025-08/M3/plot/offloading/shared.png)
![vmnet-helper offloading - bridged network](/performance/2025-08/M3/plot/offloading/bridged.png)
