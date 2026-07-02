<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Integration

## Install location

On **macOS 26** and later, vmnet-helper is installed via Homebrew.
Use `brew --prefix vmnet-helper` to get the install prefix:

```console
$(brew --prefix vmnet-helper)/libexec/vmnet-helper
$(brew --prefix vmnet-helper)/libexec/vmnet-run
```

On **macOS 15** and earlier, vmnet-helper is installed at a fixed
location by the install script:

```
/opt/vmnet-helper/bin/vmnet-helper
/opt/vmnet-helper/bin/vmnet-run
```

> [!NOTE]
> The examples in this guide use macOS 26 with Homebrew paths.

## Running with sudo

On **macOS 26** and later, vmnet-helper runs as a regular user — do
not use `sudo`.

On **macOS 15** and earlier, vmnet-helper requires root privileges.
See the [sudo guide](/docs/sudo.md) for details on using `sudo` with
vmnet-helper.

> [!NOTE]
> The examples in this guide do not use `sudo`. Add `sudo` when
> running on macOS 15 and earlier.

## Starting the helper with a file descriptor

> [!NOTE]
> This is the most secure way, connecting the vmnet helper and the
> virtual machine process using a socketpair.

The program running vmnet-helper and the virtual machine process (vfkit,
qemu) creates a datagram socketpair. One file descriptor must be passed
to vmnet-helper child process using the `--fd` option, and the other to
the virtual machine child process.

After creating the network interface, the helper writes a single line
JSON message describing the interface to stdout. The program running the
helper can parse the JSON message and extract the mac address for the
virtual machine.

Example run using jq to pretty print the response:

```console
% $(brew --prefix vmnet-helper)/libexec/vmnet-helper \
    --fd 3 \
    --interface-id 2835E074-9892-4A79-AFFB-7E41D2605678 \
    2>/dev/null | jq
{
  "vmnet_write_max_packets": 256,
  "vmnet_read_max_packets": 256,
  "vmnet_subnet_mask": "255.255.255.0",
  "vmnet_mtu": 1500,
  "vmnet_end_address": "192.168.105.254",
  "vmnet_start_address": "192.168.105.1",
  "vmnet_interface_id": "2835E074-9892-4A79-AFFB-7E41D2605678",
  "vmnet_max_packet_size": 1514,
  "vmnet_nat66_prefix": "fd2d:1b24:620:47::",
  "vmnet_mac_address": "0a:d6:36:c1:ea:f3"
}
```

The `--interface-id` option is optional but recommended to ensure that
vmnet allocates the same MAC address for the VM on every run.

> [!TIP]
> vmnet documentation instructs to configure the virtual interface with
> the mac address specified by "vmnet_mac_address". Testing shows that
> this is not required and any mac address works.

## Starting the helper with a unix socket

To start the helper from a shell, or if the virtual machine driver does not
support passing a file descriptor, you can use a bound unix socket.

Example run with a unix socket, redirecting the helper stdout to file:

```console
% $(brew --prefix vmnet-helper)/libexec/vmnet-helper \
    --socket /tmp/vmnet-helper.sock \
    --interface-id 2835E074-9892-4A79-AFFB-7E41D2605678 \
    >/tmp/vmnet-helper.json
INFO  [main] running /opt/homebrew/opt/vmnet-helper/libexec/vmnet-helper v0.11.0 on macOS 26.4.0
INFO  [main] running as uid: 501 gid: 20
INFO  [main] enabling bulk forwarding
INFO  [main] started vmnet interface
INFO  [main] waiting for client on "/tmp/vmnet-helper.sock"
```

The helper created a unix datagram socket and waits until a client
connects and sends the first packet.

You can get the mac address for the vm from the JSON file:

```console
% jq -r .vmnet_mac_address </tmp/vmnet-helper.json
0a:d6:36:c1:ea:f3
```

### Connecting to the helper unix socket

To connect to the helper from a client, you need to:

1. Create a unix datagram socket
1. Bind the socket to allow the helper to send packets to your socket
1. Connect the socket to the helper socket

> [!TIP]
> In Go the last 2 steps can be done using:
> `net.DialUnix("unixgram", clientAddress, serverAddress)`

When your client sends the first packet, the helper will start serving:

```console
INFO  [main] serving client "/tmp/vfkit-1262-6e38.sock"
INFO  [main] host forwarding started
INFO  [main] vm forwarding started
INFO  [main] waiting for termination
```

> [!NOTE]
> Once connected, the helper will ignore packets sent by a new client.
> If you want to recover from failures, restart the helper to create a
> new unix socket and reconnect.

## Starting the helper with vmnet-run

> [!NOTE]
> *vmnet-run* was called *vmnet-client* in versions before v0.11.0.

To use the helper from a shell script without using a bound unix socket, you
can use *vmnet-run*. It creates a socketpair, and starts the helper
with one socket, and the command provided by the user with the other socket.

Example run with *vfkit*:

```console
$(brew --prefix vmnet-helper)/libexec/vmnet-run -- \
    vfkit \
    --bootloader=efi,variable-store=efi-variable-store,create \
    "--device=virtio-blk,path=disk.img" \
    "--device=virtio-net,fd=4,mac=92:c9:52:b7:6c:08" \
```

> [!IMPORTANT]
> The command run by *vmnet-run* must use file descriptor 4.

> [!NOTE]
> The `--interface-id` option is not needed with vmnet-run. The command
> passed to vmnet-run specifies its own MAC address (e.g.
> `--device virtio-net,fd=4,mac=...`), so the MAC address allocated by
> vmnet is not used.

See the [examples](/examples/) for more examples of using *vmnet-run*.

## Operation modes

The vmnet helper supports all the operation modes provided by the vmnet
framework, using the **--operation-mode** option.

### --operation-mode=host

Allows the vmnet interface to communicate with other vmnet interfaces
that are in host mode and also with the native host.

The network can be configured using the
[network address options](#network-address-options) or the
[host only options](#host-only-options).

### --operation-mode=shared

Allows traffic originating from the vmnet interface to reach the
Internet through a network address translator (NAT). The vmnet interface
can also communicate with the native host. By default, the vmnet
interface is able to communicate with other shared mode interfaces.

The network can be configured using the
[network address options](#network-address-options).

### --operation-mode=bridged

Bridges the vmnet interface with a physical network interface. When
using this mode you must specify the interface name using
**--shared-interface**.

Required options:
- **--shared-interface**: The name of the interface to use.

You can find the physical interfaces that can be used in bridged mode
using the **--list-shared-interfaces** option.

```console
% $(brew --prefix vmnet-helper)/libexec/vmnet-helper --list-shared-interfaces
en10
en0
```

## Interface isolation

The **--enable-isolation** option ensures that network communication
between multiple vmnet interface instances is not possible. This option
is available for shared and host modes.

## Network address options

The IPv4 subnet can be specified using the address options, or omitted to
let vmnet select the next available network automatically. These options
apply to shared and host modes.

> [!IMPORTANT]
> All three options must be given together, or all three omitted.

- **--start-address**: The starting IPv4 address to use for the interface.
  This address is used as the gateway address. The subsequent addresses up
  to and including **--end-address** are placed in the DHCP pool.
  All other addresses are available for static assignment. The address
  must be in the private IP range (RFC 1918).

- **--end-address**: The DHCP IPv4 range end address to use for the
  interface. The address must be in the private IP range (RFC 1918).

- **--subnet-mask**: The IPv4 subnet mask to use on the interface.

### Automatic network selection

When all three address options are omitted, vmnet selects the next available
network; the defaults are 192.168.64.0/24 for shared mode, and 192.168.128.0/24
for host mode. If another program has already reserved the default network,
vmnet allocates the next network (e.g. 192.168.65.0/24). This is similar to
[vmnet-broker] shared and host networks when no explicit network is configured.

This is the most reliable way to start vmnet-helper since it avoids conflicts
with other vmnet users. However, the network address is not known until
vmnet-helper starts, so hard-coded addresses cannot be used in the VM
configuration.

> [!NOTE]
> Before v0.12.0, shared mode used 192.168.105.0/24 when address options
> were omitted. If you depend on a specific network, specify all three
> address options explicitly.

### Network conflicts

The same IPv4 subnet cannot be used for both a shared-mode vmnet network and a
host-mode vmnet network: whichever process creates the network first owns that
range. If another program using vmnet has already created the same network
in a different mode, vmnet-helper will fail.

For example, if socket_vmnet runs as a launchd daemon and creates the network
192.168.105.0/24 at boot, running vmnet-helper with explicit options for that
same subnet conflicts with it. Omitting the address options lets vmnet select
the next network (typically 192.168.65.0/24).

## Network mode (macOS 26)

On macOS 26 and later, vmnet-helper can join a network managed by [vmnet-broker]
instead of creating its own. This lets VMs using vmnet-helper share the same
network as VMs using native vmnet via the Virtualization framework. See the
[architecture guide][native-vmnet] for details.

- **--network NAME**: Join the named network managed by vmnet-broker
  (e.g. "shared"). The broker creates the network on first use and
  shares it with all requesting processes.

The `--network` option is mutually exclusive with `--operation-mode`,
`--shared-interface`, `--start-address`, `--end-address`, and
`--subnet-mask` — the network configuration is owned by the broker.
The `--interface-id` option is ignored in this mode.

Example using vmnet-helper directly:

```console
% $(brew --prefix vmnet-helper)/libexec/vmnet-helper \
    --fd 3 \
    --network shared
```

Example using vmnet-run:

```console
$(brew --prefix vmnet-helper)/libexec/vmnet-run --network shared -- \
    vfkit \
    --bootloader=efi,variable-store=efi-variable-store,create \
    "--device=virtio-blk,path=disk.img" \
    "--device=virtio-net,fd=4,mac=92:c9:52:b7:6c:08"
```

> [!NOTE]
> [vmnet-broker] must be installed and running before using `--network`.

## Offloading options

These options can be used with krunkit to get much better performance in some
cases and much worse performance in other cases. See the
[Offloading](/docs/performance.md#offloading) section for performance results.

- **--enable-tso**: Enable TCP segmentation offload. Note, when this is enabled,
  the interface may generate large (64K) TCP frames. It must also be prepared to
  accept large TCP frames as well.

- **--enable-checksum-offload**: Enable checksum offload for this interface. The
  checksums that are offloaded are: IPv4 header checksum, UDP checksum (IPv4 and
  IPv6), and TCP checksum (IPv4 and IPv6).

  In order to perform the offload function, all packets flowing in and out of
  the vmnet_interface instance are verified to pass basic IPv4, IPv6, UDP, and
  TCP sanity checks. A packet that fails any of these checks is simply dropped.

  On output, checksums are automatically computed as necessary on each packet
  sent using vmnet_write().

  On input, checksums are verified as necessary. If any checksum verification
  fails, the packet is dropped and not delivered to vmnet_read().

  Note that the checksum offload function for UDP and TCP checksums is unable to
  deal with fragmented IPv4/IPv6 packets. The VM client networking stack must
  handle UDP and TCP checksums on fragmented packets itself.

> [!IMPORTANT]
> You must use both **--enable-tso** and **--enable-checksum-offload** when
> using krunkit **offloading=on** virtio-net option.

## Host only options

- **--network-id**: Takes a UUID to identify the network. The guest can only
  communicate with other host-mode interfaces with the same network ID. No DHCP
  service is provided.

> [!WARNING]
> On macOS < 26, an address is not automatically assigned to the host when
> `--network-id` is set.

## Stopping the interface

Terminate the vmnet-helper process gracefully. Send a SIGTERM or SIGINT
signal and wait until child process terminates.

## Logging

The vmnet helper logs to stderr. You can read the logs and integrate
them in your application logs or redirect them to a file.

[native-vmnet]: /docs/architecture.md#native-vmnet-on-macos-26
[socket_vmnet]: https://github.com/lima-vm/socket_vmnet
[vmnet-broker]: https://github.com/nirs/vmnet-broker
