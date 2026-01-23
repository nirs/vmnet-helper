# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import platform
import selectors
import signal
import subprocess
import time

from . import cidata
from . import disks
from . import ssh
from . import store

DRIVERS = ["vfkit", "krunkit", "qemu"]

QEMU_CONFIG = {
    "arm64": {
        "arch": "aarch64",
        "machine": "virt",
    },
    "x86_64": {
        "arch": "x86_64",
        "machine": "q35",
    },
}


class VM:
    def __init__(self, args, mac_address, fd=None, socket=None, client=None):
        # Configuration
        self.args = args
        self.mac_address = mac_address
        self.fd = fd
        self.socket = socket
        self.client = client
        self.vm_name = args.vm_name
        self.verbose = args.verbose
        self.driver = args.driver
        self.driver_command = args.driver_command
        self.cpus = args.cpus
        self.memory = args.memory
        self.distro = args.distro
        self.serial = store.vm_path(self.vm_name, "serial.log")
        self.enable_offloading = args.enable_offloading

        # Running info
        self.disk = None
        self.cidata = None
        self.proc = None
        self.ip_address = None

    def start(self):
        """
        Starts a VM driver with fd or socket.
        """
        vm_home = store.vm_path(self.vm_name)
        os.makedirs(vm_home, exist_ok=True)

        self.disk = disks.create_disk(self)
        self.cidata = cidata.create_iso(self)
        if self.driver == "vfkit":
            cmd = self.vfkit_command()
        elif self.driver == "krunkit":
            cmd = self.krunkit_command()
        elif self.driver == "qemu":
            cmd = self.qemu_command()
        else:
            raise ValueError(f"Invalid driver '{self.driver}'")
        logging.info(
            "Starting '%s' virtual machine '%s' with mac address '%s'",
            self.driver,
            self.vm_name,
            self.mac_address,
        )
        store.silent_remove(self.serial)
        self._start_process(cmd)

    def _start_process(self, cmd):
        pass_fds = []
        stdout = None
        logfile = store.vm_path(self.vm_name, f"{self.driver}.log")
        with open(logfile, "w") as log:
            if self.client:
                cmd = self.client_command(cmd)
                stdout = log
            elif self.fd is not None:
                pass_fds = [self.fd]
            self.write_command(cmd)
            self.proc = subprocess.Popen(
                cmd,
                stdout=stdout,
                stderr=log,
                pass_fds=pass_fds,
            )

    def stop(self):
        self.delete_ip_address()
        ssh.delete_config(self)
        self.proc.terminate()
        self.proc.wait()

    def write_command(self, cmd):
        """
        Write command to file to make it easy to debug and report bugs.
        """
        path = store.vm_path(self.vm_name, f"{self.driver}.command")
        data = " \\\n    ".join(cmd) + "\n"
        with open(path, "w") as f:
            f.write(data)

    def wait_for_ip_address(self, timeout=60):
        """
        Lookup the vm ip address in the serial log and write to
        vm_home/ip-address.
        """
        prefix = f"{self.vm_name} address: "
        for line in tail(self.serial, timeout):
            self.check_running()
            if line.startswith(prefix):
                self.ip_address = line[len(prefix) :]
                logging.info("Virtual machine IP address: %s", self.ip_address)
                self.write_ip_address()
                ssh.create_config(self)
                return
        self.check_running()
        logging.warning("Timeout looking up ip address")

    def check_running(self):
        if self.proc.poll() is not None:
            raise RuntimeError(
                f"Virtual machine terminated (exitcode {self.proc.returncode})"
            )

    def write_ip_address(self):
        path = store.vm_path(self.vm_name, "ip-address")
        with open(path, "w") as f:
            f.write(self.ip_address)

    def delete_ip_address(self):
        path = store.vm_path(self.vm_name, "ip-address")
        store.silent_remove(path)

    def vfkit_command(self):
        efi_store = store.vm_path(self.vm_name, "efi-variable-store")
        cmd = [
            self.driver_command or "vfkit",
            f"--memory={self.memory}",
            f"--cpus={self.cpus}",
            f"--bootloader=efi,variable-store={efi_store},create",
            f"--device=usb-mass-storage,path={self.cidata},readonly",
            f"--device=virtio-blk,path={self.disk['image']}",
            f"--device=virtio-serial,logFilePath={self.serial}",
            "--log-level=debug",
            "--device=virtio-rng",
        ]
        if self.fd is not None:
            cmd.append(f"--device=virtio-net,fd={self.fd},mac={self.mac_address}")
        elif self.socket is not None:
            cmd.append(
                f"--device=virtio-net,unixSocketPath={self.socket},mac={self.mac_address}"
            )
        else:
            raise ValueError("fd or socket required")
        return cmd

    def krunkit_command(self):
        cmd = [
            self.driver_command or "krunkit",
            f"--memory={self.memory}",
            f"--cpus={self.cpus}",
            f"--restful-uri=none://",
            f"--device=virtio-blk,path={self.disk['image']}",
            f"--device=virtio-blk,path={self.cidata}",
            f"--device=virtio-serial,logFilePath={self.serial}",
            "--krun-log-level=3",
            "--device=virtio-rng",
        ]

        offloading = "on" if self.enable_offloading else "off"
        if self.fd is not None:
            cmd.append(
                f"--device=virtio-net,type=unixgram,fd={self.fd},mac={self.mac_address},offloading={offloading}",
            )
        elif self.socket is not None:
            cmd.append(
                f"--device=virtio-net,type=unixgram,path={self.socket},mac={self.mac_address},offloading={offloading}",
            )
        else:
            raise ValueError("fd or socket required")

        return cmd

    def qemu_command(self):
        if self.fd is not None:
            netdev = f"dgram,id=net1,local.type=fd,local.str={self.fd}"
        elif self.socket is not None:
            # qemu support unix datagram socket, but it requires local and remote sockets:
            #   -netdev dgram,id=str,local.type=unix,local.path=path[,remote.type=unix,remote.path=path]
            # The remote parameters look optional but they are required.  Trying to
            # use the helper socket with local.path and remote.path does not work.
            # Maybe it tries to connect to the helper socket twice, and the helper
            # ignores the second client.
            raise ValueError("socket connection not supported for qemu driver")
        else:
            raise ValueError("fd or socket required")
        qemu = QEMU_CONFIG[platform.machine()]
        firmware = qemu_firmware(qemu["arch"])
        cmd = [
            self.driver_command or f"qemu-system-{qemu['arch']}",
            "-name",
            self.vm_name,
            "-m",
            f"{self.memory}",
            "-cpu",
            "host",
            "-machine",
            f"{qemu['machine']},accel=hvf",
            "-smp",
            f"{self.cpus},sockets=1,cores={self.cpus},threads=1",
            "-drive",
            f"if=pflash,format=raw,readonly=on,file={firmware}",
            "-drive",
            f"file={self.disk['image']},if=virtio,format=raw,discard=on",
            "-drive",
            f"file={self.cidata},id=cdrom0,if=none,format=raw,readonly=on",
            "-device",
            "virtio-scsi-pci,id=scsi0",
            "-device",
            "scsi-cd,bus=scsi0.0,drive=cdrom0",
            "-netdev",
            netdev,
            "-device",
            f"virtio-net-pci,netdev=net1,mac={self.mac_address}",
            "-monitor",
            "none",
            "-serial",
            f"file:{self.serial}",
            "-nographic",
            "-nodefaults",
            "-device",
            "virtio-rng-pci",
        ]

        # Optional arguments

        if "kernel" in self.disk:
            cmd.extend(["-kernel", self.disk["kernel"]])
        if "kernel_parameters" in self.disk:
            # https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html
            kernel_cmdline = " ".join(self.disk["kernel_parameters"])
            cmd.extend(["-append", kernel_cmdline])
        if "initrd" in self.disk:
            cmd.extend(["-initrd", self.disk["initrd"]])

        return cmd

    def client_command(self, vm_command):
        cmd = [self.client]
        if self.args.network_name:
            cmd.append(f"--network={self.args.network_name}")
        elif self.args.operation_mode:
            cmd.append(f"--operation-mode={self.args.operation_mode}")
            if self.args.operation_mode == "bridged":
                cmd.append(f"--shared-interface={self.args.shared_interface}")
            elif self.args.operation_mode == "host" and self.args.enable_isolation:
                cmd.append("--enable-isolation")
        if self.args.verbose:
            cmd.append("--verbose")
        if not self.args.privileged:
            cmd.append("--unprivileged")
        cmd.append("--")
        cmd.extend(vm_command)
        return cmd


def qemu_firmware(arch):
    """
    Based on https://github.com/lima-vm/lima/blob/master/pkg/qemu/qemu.go.
    """
    filename = f"edk2-{arch}-code.fd"
    candidates = [
        f"/opt/homebrew/share/qemu/{filename}",  # Apple silicon
        f"/usr/local/share/qemu/{filename}",  # intel (github runner)
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise RuntimeError(f"Unable to find firmware: {candidates}")


def tail(path, timeout):
    tail = subprocess.Popen(
        ["tail", "-F", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        partial = bytearray()
        for data in stream(tail.stdout, timeout):
            for line in data.splitlines(keepends=True):
                if not line.endswith(b"\n"):
                    partial += line
                    break
                if partial:
                    line = bytes(partial) + line
                    del partial[:]
                yield line.rstrip().decode()
        if partial:
            yield partial.decode()
    finally:
        tail.kill()
        tail.wait()


def stream(file, timeout):
    deadline = time.monotonic() + timeout
    with selectors.PollSelector() as sel:
        sel.register(file, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining < 0:
                break
            for key, _ in sel.select(remaining):
                data = os.read(key.fd, 1024)
                if not data:
                    break
                yield data
