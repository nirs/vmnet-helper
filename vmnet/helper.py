# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import logging
import os
import platform
import socket
import subprocess
import uuid

from . import store

PREFIX = "/opt/vmnet-helper"
HELPER = os.path.join(PREFIX, "bin/vmnet-helper")
CLIENT = os.path.join(PREFIX, "bin/vmnet-client")
OPERATION_MODES = ["shared", "bridged", "host"]

# Apple recommends sizing the receive buffer at 4 times the size of the send
# buffer, and other projects typically use a 1 MiB send buffer and a 4 MiB
# receive buffer. However the send buffer size is not used to allocate a buffer
# in datagram sockets, it only limits the maximum packet size. We use 65 KiB
# buffer to allow the largest possible packet size (65550 bytes) when using the
# vmnet_enable_tso option.
SEND_BUFFER_SIZE = 65 * 1024

# The receive buffer size determines how many packets can be queued by the peer.
# Testing shows good performance with a 2 MiB receive buffer. We use a 4 MiB
# buffer to make ENOBUFS errors less likely for the peer and allowing to queue
# more packets when using the vmnet_enable_tso option.
RECV_BUFFER_SIZE = 4 * 1024 * 1024

# Vmnet interface info keys
# https://developer.apple.com/documentation/vmnet/interface_param_xpc_dictionary_keys?language=objc
VMNET_START_ADDRESS = "vmnet_start_address"
VMNET_END_ADDRESS = "vmnet_end_address"
VMNET_MAC_ADDRESS = "vmnet_mac_address"
VMNET_SUBNET_MASK = "vmnet_subnet_mask"
VMNET_MAX_PACKET_SIZE = "vmnet_max_packet_size"

# Network info keys (--network mode only)
NET_IPV4_SUBNET = "net_ipv4_subnet"
NET_IPV4_MASK = "net_ipv4_mask"
NET_IPV6_PREFIX = "net_ipv6_prefix"
NET_IPV6_PREFIX_LEN = "net_ipv6_prefix_len"


class Helper:
    def __init__(self, args, fd=None, socket=None):
        # Configuration
        self.fd = fd
        self.socket = socket
        self.vm_name = args.vm_name
        self.operation_mode = args.operation_mode
        self.start_address = args.start_address
        self.end_address = args.end_address
        self.subnet_mask = args.subnet_mask
        self.shared_interface = args.shared_interface
        self.network_name = args.network_name
        self.enable_isolation = args.enable_isolation
        self.enable_offloading = args.enable_offloading
        self.verbose = args.verbose
        self.privileged = args.privileged

        # Running state.
        self.proc = None
        self.interface = None

    def start(self):
        """
        Starts vmnet-helper with fd or socket.
        """
        interface_id = interface_id_from(self.vm_name)
        logging.info(
            "Starting vmnet-helper for '%s' with interface id '%s'",
            self.vm_name,
            interface_id,
        )
        cmd = self._build_command(interface_id)

        vm_home = store.vm_path(self.vm_name)
        os.makedirs(vm_home, exist_ok=True)
        logfile = os.path.join(vm_home, "vmnet-helper.log")

        with open(logfile, "w") as log:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=log,
                pass_fds=[self.fd] if self.fd is not None else [],
            )
        try:
            reply = self.proc.stdout.readline()  # type: ignore[attr-defined]
            if not reply:
                raise RuntimeError("No response from helper")

            self.interface = json.loads(reply)
        except:
            self.stop()
            raise

    def _build_command(self, interface_id):
        if self.privileged:
            cmd = ["sudo", "--non-interactive"]
            if self.fd is not None:
                cmd.append(f"--close-from={self.fd + 1}")
        else:
            cmd = []

        cmd.append(HELPER)

        if self.fd is not None:
            cmd.append(f"--fd={self.fd}")
        elif self.socket is not None:
            cmd.append(f"--socket={self.socket}")
        else:
            raise ValueError("fd or socket required")

        cmd.append(f"--interface-id={interface_id}")

        if self.network_name:
            cmd.append(f"--network={self.network_name}")
        elif self.operation_mode:
            cmd.append(f"--operation-mode={self.operation_mode}")

            if self.operation_mode == "shared":
                if self.start_address:
                    cmd.append(f"--start-address={self.start_address}")
                if self.end_address:
                    cmd.append(f"--end-address={self.end_address}")
                if self.subnet_mask:
                    cmd.append(f"--subnet-mask={self.subnet_mask}")
            elif self.operation_mode == "bridged":
                cmd.append(f"--shared-interface={self.shared_interface}")
            elif self.operation_mode == "host":
                if self.enable_isolation:
                    cmd.append("--enable-isolation")
            else:
                raise RuntimeError(f"invalid operation mode: {self.operation_mode}")

        if self.enable_offloading:
            cmd.extend(["--enable-tso", "--enable-checksum-offload"])

        if self.verbose:
            cmd.append("--verbose")

        return cmd

    def stop(self):
        self.proc.terminate()
        self.proc.wait()


def requires_root():
    """
    Returns True if the helper requires root.
    """
    release = platform.mac_ver()[0]
    major = release.split(".")[0]
    return int(major) < 26


def interface_id_from(name):
    """
    Return unique UUID using the VM name. This UUID ensures that we get the
    same MAC address when running the same VM again.
    """
    full_name = f"vmnet-helper-example-{name}"
    md = hashlib.sha256(full_name.encode()).digest()
    return str(uuid.UUID(bytes=md[:16], version=4))


def socketpair():
    pair = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM, 0)
    for sock in pair:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUFFER_SIZE)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUFFER_SIZE)
        os.set_inheritable(sock.fileno(), True)
    return pair


def shared_interfaces():
    cp = subprocess.run(
        ["/opt/vmnet-helper/bin/vmnet-helper", "--list-shared-interfaces"],
        stdout=subprocess.PIPE,
        check=True,
    )
    return cp.stdout.decode().splitlines()
