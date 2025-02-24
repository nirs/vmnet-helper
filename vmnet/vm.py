# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import os
import platform
import selectors
import subprocess
import time

from . import cidata
from . import disks
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
    def __init__(self, args, mac_address, fd=None, socket=None):
        # Configuration
        self.mac_address = mac_address
        self.fd = fd
        self.socket = socket
        self.vm_name = args.vm_name
        self.verbose = args.verbose
        self.driver = args.driver
        self.driver_command = args.driver_command
        self.krunkit_port = args.krunkit_port
        self.cpus = args.cpus
        self.memory = args.memory
        self.distro = args.distro
        self.serial = store.vm_path(self.vm_name, "serial.log")

        # Running info
        self.disk = None
        self.cidata = None
        self.proc = None

    def start(self):
        """
        Starts a VM driver with fd or socket.
        """
        self.disk = disks.create_disk(self.vm_name, self.distro)
        self.cidata = cidata.create_iso(self)
        if self.driver == "vfkit":
            cmd = self.vfkit_command()
        elif self.driver == "krunkit":
            cmd = self.krunkit_command()
        elif self.driver == "qemu":
            cmd = self.qemu_command()
        else:
            raise ValueError(f"Invalid driver '{self.driver}'")
        print(
            f"Starting '{self.driver}' virtual machine '{self.vm_name}' with mac address '{self.mac_address}'"
        )
        self.write_command(cmd)
        store.silent_remove(self.serial)
        with open(store.vm_path(self.vm_name, f"{self.driver}.log"), "w") as log:
            pass_fds = [self.fd] if self.fd is not None else []
            self.proc = subprocess.Popen(cmd, stderr=log, pass_fds=pass_fds)

    def stop(self):
        self.delete_ip_address()
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

    def wait_for_ip_address(self, timeout=300):
        """
        Lookup the vm ip address in the serial log and write to
        vm_home/ip-address.
        """
        prefix = f"{self.vm_name} address: "
        for line in tail(self.serial, timeout):
            self.check_running()
            if line.startswith(prefix):
                ip_address = line[len(prefix) :]
                print(f"Virtual machine IP address: {ip_address}")
                self.write_ip_address(ip_address)
                return
        self.check_running()
        print("Timeout looking up ip address")

    def check_running(self):
        if self.proc.poll() is not None:
            raise RuntimeError(
                f"Virtual machine terminated (exitcode {self.proc.returncode})"
            )

    def write_ip_address(self, ip_address):
        path = store.vm_path(self.vm_name, "ip-address")
        with open(path, "w") as f:
            f.write(ip_address)

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
        if self.fd is not None:
            raise ValueError("fd connection not supported for krunkit driver")
        if self.socket is None:
            raise ValueError("socket connection required")
        return [
            self.driver_command or "krunkit",
            f"--memory={self.memory}",
            f"--cpus={self.cpus}",
            f"--restful-uri=tcp://localhost:{self.krunkit_port}",
            f"--device=virtio-blk,path={self.disk['image']}",
            f"--device=virtio-blk,path={self.cidata}",
            f"--device=virtio-net,unixSocketPath={self.socket},mac={self.mac_address}",
            f"--device=virtio-serial,logFilePath={self.serial}",
            "--krun-log-level=3",
        ]

    def qemu_command(self):
        if self.fd is not None:
            netdev = f"dgram,id=net1,local.type=fd,local.str={self.fd}"
        elif self.socket is not None:
            # qemu support unix datagram socket, but it rquires local and remote sockets:
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
        ]

        # Optinal arguments

        if "kernel" in self.disk:
            cmd.extend(["-kernel", self.disk["kernel"]])
        if "kernel_parameters" in self.disk:
            # https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html
            kernel_cmdline = " ".join(self.disk["kernel_parameters"])
            cmd.extend(["-append", kernel_cmdline])
        if "initrd" in self.disk:
            cmd.extend(["-initrd", self.disk["initrd"]])

        return cmd

def qemu_firmware(arch):
    """
    Based on https://github.com/lima-vm/lima/blob/master/pkg/qemu/qemu.go.
    """
    filename = f"edk2-{arch}-code.fd"
    candidates = [
        f"/opt/homebrew/share/qemu/{filename}",  # Apple silicon
        f"/usr/local/share/qemu/{filename}",  # macos-13 github runner
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
