<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Integration

## Starting the interface by passing a file descriptor

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
% sudo --non-interactive \
       --close-from 4 \
       /opt/vmnet-helper/bin/vmnet-helper \
       --fd 3 \
       --interface-id 2835E074-9892-4A79-AFFB-7E41D2605678 \
       2>/dev/null | jq
{
  "vmnet_subnet_mask": "255.255.255.0",
  "vmnet_mtu": 1500,
  "vmnet_end_address": "192.168.105.254",
  "vmnet_start_address": "192.168.105.1",
  "vmnet_interface_id": "2835E074-9892-4A79-AFFB-7E41D2605678",
  "vmnet_max_packet_size": 1514,
  "vmnet_nat66_prefix": "fd9b:5a14:ba57:e3d3::",
  "vmnet_mac_address": "0a:d6:36:c1:ea:f3"
}
```

> [!TIP]
> vmnet documentation instructs to configure the virtual interface with
> the mac address specified by "vmnet_mac_address". Testing shows that
> this is not required and any mac address works.

The `--interface-id` option is optional. It ensures that you get the same
MAC address on every run.

## Starting the helper with a unix socket

To start the helper from a shell, or if the virtual machine driver does not
support passing a file descriptor, you can use a bound unix socket.

Example run with a unix socket, redirecting the helper stdout to file:

```console
% sudo --non-interactive \
       /opt/vmnet-helper/bin/vmnet-helper \
       --socket /tmp/example/vm/vmnet.sock \
       --interface-id 2835E074-9892-4A79-AFFB-7E41D2605678 \
       >/tmp/example/vm/vmnet.json
INFO  [main] running /opt/vmnet-helper/bin/vmnet-helper v0.2.0-4-ga1b610b on macOS 15.2.0
INFO  [main] enabling bulk forwarding
INFO  [main] started vmnet interface
INFO  [main] running as uid: 501 gid: 20
INFO  [main] waiting for client on "/tmp/example/vm/vmnet.sock"
```

The helper created a unix datagram socket and waits until a client
connects and sends the first packet.

You can get the mac address for the vm from the vmnet.json:

```console
jq -r .vmnet_mac_address </tmp/example/vm/vmnet.json
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
INFO  [main] serving client "/tmp/example/vm/vfkit-1262-6e38.sock"
INFO  [main] host forwarding started
INFO  [main] vm forwarding started
INFO  [main] waiting for termination
```

> [!NOTE]
> Once connected, the helper will ignore packets sent by a new client.
> If you want to recover from failures, restart the helper to create a
> new unix socket and reconnect.

### Using vmnet-client

To use the helper from a shell script without using a bound unix socket, you
can use *vmnet-client*. The client creates a socketpair, and starts the helper
with one socket, and the command provided by the user with the other socket.

Example run with *vfkit*:

```console
/opt/vmnet-helper/bin/vmnet-client -- \
    vfkit \
    --bootloader=efi,variable-store=efi-variable-store,create \
    "--device=virtio-blk,path=disk.img" \
    "--device=virtio-net,fd=4,mac=92:c9:52:b7:6c:08" \
```

> [!IMPORTANT]
> The command run by *vmnet-client* must use file descriptor 4.

See the [examples](/examples/) for more examples of using *vmnet-client*.

> [!TIP]
> On macOS 26 and later, use the `--unprivileged` option to run the
> helper without sudo.

## Operation modes

The vmnet helper supports all the operation modes provided by the vmnet
framework, using the **--operation-mode** option.

### --operation-mode=host

Allows the vmnet interface to communicate with other vmnet interfaces
that are in host mode and also with the native host.

Options:

- **--enable-isolation**: Enable isolation for this interface. Interface
  isolation ensures that network communication between multiple vmnet
  interface instances is not possible.

### --operation-mode=shared

Allows traffic originating from the vmnet interface to reach the
Internet through a network address translator (NAT). The vmnet interface
can also communicate with the native host. By default, the vmnet
interface is able to communicate with other shared mode interfaces.

Options:

- **--start-address**: The starting IPv4 address to use for the interface.
  This address is used as the gateway address. The subsequent address up
  to and including **--end-address** are placed in the DHCP pool.
  All other addresses are available for static assignment.  The address
  must be in the private IP range (RFC 1918).  Must be specified along
  with **--end-address** and **--subnet-mask** (default "192.168.105.1").

- **--end-address**: The DHCP IPv4 range end address (string) to use for
  the interface.  The address must be in the private IP range (RFC
  1918).  Must be specified with **--start-address** and
  **--subnet-mask** (default "192.168.105.254").

- **--subnet-mask**: The IPv4 subnet mask to use on the interface.  Must
  also specify **--start-address** and **--end-address** (default
  "255.255.255.0").

### --operation-mode=bridged

Bridges the vmnet interface with a physical network interface. When
using this mode you must specify the interface name using
**--shared-interface**.

Required options:
- **--shared-interface**: The name of the interface to use.

You can find the physical interfaces that can be used in bridged mode
using the **--list-shared-interfaces** option.

```console
% /opt/vmnet-helper/bin/vmnet-helper --list-shared-interfaces
en10
en0
```

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

## Stopping the interface

Terminate the vmnet-helper process gracefully. Send a SIGTERM or SIGINT
signal and wait until child process terminates.

## Logging

The vmnet helper logs to stderr. You can read the logs and integrate
them in your application logs or redirect them to a file.
