// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#ifndef COMMON_H
#define COMMON_H

// Apple recommends sizing the receive buffer at 4 times the size of the send
// buffer, and other projects typically use a 1 MiB send buffer and a 4 MiB
// receive buffer. However the send buffer size is not used to allocate a buffer
// in datagram sockets, it only limits the maximum packet size. We use 65 KiB
// buffer to allow the largest possible packet size (65550 bytes) when using the
// vmnet_enable_tso option.
#define SEND_BUFFER_SIZE (65 * 1024)

// The receive buffer size determines how many packets can be queued by the
// peer. Testing shows good performance with a 2 MiB receive buffer. We use a 4
// MiB buffer to make ENOBUFS errors less likely for the peer.
#define RECV_BUFFER_SIZE (4 * 1024 * 1024)

// Scale buffer for higher offloading throughput (~2.5x). A larger factor would
// reduce ENOBUFS but adds latency from bufferbloat. With 8 MiB the buffer
// fills in ~2 ms, similar to ~2.6 ms without offloading.
#define RECV_BUFFER_SIZE_OFFLOAD (8 * 1024 * 1024)

#endif // COMMON_H
