<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Similar tools

## socket_vmnet

[socket_vmnet](https://github.com/lima-vm/socket_vmnet) has the same
purpose and features, providing access to vmnet capabilities without the
special `com.apple.vm.networking` entitlement.

The main difference between vmnet-helper and socket_vmnet is using a
helper process and vmnet interface per vm, instead of single daemon
process and vmnet interface for vms using the same networking mode
(host, bridged). Using a separate process is simpler to manage, more
reliable, and more secure.

The second difference is using a unix datagram socket instead of a unix
stream socket and qemu length prefixed packets format. This is simpler
and performs better, avoiding copying and converting packets from qemu
format to raw format.

Detailed list of differences:

- Much better performance when using Apple Virtualization framework (see
  [performance](/docs/performance.md) section).
- Eliminating the scaling issues caused by flooding packets to vms by
  using one vmnet interface per VM, and delegating to vmnet for forwarding
  packets to the right mac address. For more info see
  https://github.com/lima-vm/socket_vmnet/issues/58.
- Eliminating copying packets from length prefixed qemu packets on unix
  stream socket to vz datagram socket by copying directly from vmnet to
  vz file handle unix datagram socket.
- Using sendmsg_x() and recvmsg_x() for reading and writing multiple
  packets per one syscall doubles throughput in vm to vm use case and
  lower cpu usage.
- More reliable: crash in one helper process affects only one virtual
  machine.
- More secure: dropping privileges after starting the vmnet interface
  and running as the real user and group id.
- Eliminating the need to manage daemons and sockets files shared by
  multiple virtual machines.
- Works with [vfkit](https://github.com/crc-org/vfkit) using
  `--device=virtio-net,fd=` device.
- Works with [qemu](https://www.qemu.org/) using `-netdev dgram` device
  instead of `-netdev unix` device.
- Not integrated yet with [lima](https://github.com/lima-vm/lima) or
  [minikube](https://minikube.sigs.k8s.io/).

## softnet

[softnet](https://github.com/cirruslabs/softnet) seems to provide the
same vmnet network features, using the same process model - one helper
process and vmnet interface per virtual machine.

softnet supports network isolation and tweaking DHCP server lease
timeout, which are not in scope for vmnet-helper.

softnet is released under AGPL license which may be harder to adopt in
your organization.
