# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import os
import socket
import subprocess
import uuid

from . import store

OPERATION_MODES = ["shared", "bridged", "host"]

# Apple recommend receive buffer size to be 4 times the size of the send
# buffer size, but send buffer size is not used to allocate a buffer in
# datagram sockets, it only limits the maximum packet size.
# Must be larger than TSO packets size (65550 bytes).
SEND_BUFSIZE = 65 * 1024

# The receive buffer size determine how many packets can be queued by the
# peer. Using bigger receive buffer size make ENOBUFS error less likey for the
# peer and improves throughput.
RECV_BUFSIZE = 4 * 1024 * 1024


class Helper:

    def __init__(self, args, fd=None, socket=None):
        # Configuration
        self.fd = fd
        self.socket = socket
        self.vm_name = args.vm_name
        self.operation_mode = args.operation_mode
        self.shared_interface = args.shared_interface
        self.enable_isolation = args.enable_isolation
        self.vmnet_offload = args.vmnet_offload
        self.verbose = args.verbose

        # Running state.
        self.proc = None
        self.interface = None

    def start(self):
        """
        Starts vmnet-helper with fd or socket.
        """
        interface_id = interface_id_from(self.vm_name)
        print(
            f"Starting vmnet-helper for '{self.vm_name}' with interface id '{interface_id}'"
        )
        if self.fd is not None:
            cmd = [
                "sudo",
                "--non-interactive",
                f"--close-from={self.fd+1}",
                "/opt/vmnet-helper/bin/vmnet-helper",
                f"--fd={self.fd}",
            ]
            pass_fds = [self.fd]
        elif self.socket is not None:
            cmd = [
                "sudo",
                "--non-interactive",
                "/opt/vmnet-helper/bin/vmnet-helper",
                f"--socket={self.socket}",
            ]
            pass_fds = []
        else:
            raise ValueError("fd or socket required")

        cmd.append(f"--interface-id={interface_id}")
        cmd.append(f"--operation-mode={self.operation_mode}")

        if self.operation_mode == "bridged":
            cmd.append(f"--shared-interface={self.shared_interface}")
        elif self.operation_mode == "host" and self.enable_isolation:
            cmd.append("--enable-isolation")

        if self.verbose:
            cmd.append("--verbose")

        if self.vmnet_offload == "on":
            cmd.extend(["--enable-tso", "--enable-checksum-offload"])

        vm_home = store.vm_path(self.vm_name)
        os.makedirs(vm_home, exist_ok=True)
        logfile = os.path.join(vm_home, "vmnet-helper.log")

        with open(logfile, "w") as log:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=log,
                pass_fds=pass_fds,
            )
        try:
            reply = self.proc.stdout.readline()  # type: ignore[attr-defined]
            if not reply:
                raise RuntimeError("No response from helper")

            self.interface = json.loads(reply)
        except:
            self.stop()
            raise

    def stop(self):
        self.proc.terminate()
        self.proc.wait()


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
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUFSIZE)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUFSIZE)
        os.set_inheritable(sock.fileno(), True)
    return pair


def shared_interfaces():
    cp = subprocess.run(
        ["/opt/vmnet-helper/bin/vmnet-helper", "--list-shared-interfaces"],
        stdout=subprocess.PIPE,
        check=True,
    )
    return cp.stdout.decode().splitlines()
