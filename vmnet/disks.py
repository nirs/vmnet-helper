# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import logging
import os
import platform
import subprocess

from . import store

UBUNTU_RELEASE = "25.04"

IMAGES = {
    "ubuntu": {
        "arm64": {
            "image": f"https://cloud-images.ubuntu.com/releases/{UBUNTU_RELEASE}/release/ubuntu-{UBUNTU_RELEASE}-server-cloudimg-arm64.img",
        },
        "x86_64": {
            "image": f"https://cloud-images.ubuntu.com/releases/{UBUNTU_RELEASE}/release/ubuntu-{UBUNTU_RELEASE}-server-cloudimg-amd64.img",
            "kernel": f"https://cloud-images.ubuntu.com/releases/{UBUNTU_RELEASE}/release/unpacked/ubuntu-{UBUNTU_RELEASE}-server-cloudimg-amd64-vmlinuz-generic",
            # Based on the default kernel cmdline when not using kernel and initrd:
            # BOOT_IMAGE=/vmlinuz-6.11.0-14-generic root=LABEL=cloudimg-rootfs ro console=tty1 console=ttyS0
            "kernel_parameters": [
                "root=LABEL=cloudimg-rootfs",
                "ro",
                "console=tty1",
                "console=ttyS0",
                # https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html
                "apic=debug",
                # Based on socket_vmnet fix:
                # https://github.com/lima-vm/socket_vmnet/pull/56
                "no_timer_check",
            ],
            "initrd": f"https://cloud-images.ubuntu.com/releases/{UBUNTU_RELEASE}/release/unpacked/ubuntu-{UBUNTU_RELEASE}-server-cloudimg-amd64-initrd-generic",
        },
    },
    "alpine": {
        "arm64": {
            "image": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/nocloud_alpine-3.21.2-aarch64-uefi-cloudinit-r0.qcow2",
        },
    },
    "fedora": {
        "arm64": {
            "image": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Cloud/aarch64/images/Fedora-Cloud-Base-Generic-41-1.4.aarch64.qcow2",
        },
    },
}


def create_disk(vm):
    """
    Create a disk from image using copy-on-write.
    """
    image_info = IMAGES[vm.distro][platform.machine()]
    disk = {"image": store.vm_path(vm.vm_name, "disk.img")}
    if not os.path.isfile(disk["image"]):
        image = create_image(image_info["image"], format="raw", size="20g")
        logging.info("Creating image '%s'", disk["image"])
        clone(image, disk["image"])
    if "kernel" in image_info:
        disk["kernel"] = store.vm_path(vm.vm_name, "kernel")
        if not os.path.isfile(disk["kernel"]):
            kernel = create_image(image_info["kernel"])
            logging.info("Creating kernel '%s'", disk["kernel"])
            clone(kernel, disk["kernel"])
    if "initrd" in image_info:
        disk["initrd"] = store.vm_path(vm.vm_name, "initrd")
        if not os.path.isfile(disk["initrd"]):
            initrd = create_image(image_info["initrd"])
            logging.info("Creating initrd '%s'", disk["initrd"])
            clone(initrd, disk["initrd"])
    if "kernel_parameters" in image_info:
        disk["kernel_parameters"] = image_info["kernel_parameters"]
    return disk


def create_image(url, format=None, size=None):
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    path = store.cache_path("images", url_hash, "data")
    if not os.path.exists(path):
        image_dir = os.path.dirname(path)
        os.makedirs(image_dir, exist_ok=True)
        tmp_path = path + ".tmp"
        try:
            download_image(url, tmp_path)
            if format:
                convert_image(tmp_path, path, format)
            else:
                os.rename(tmp_path, path)
            if size:
                resize_image(path, size)
        except:
            store.silent_remove(path)
            raise
        finally:
            store.silent_remove(tmp_path)
    return path


def download_image(image_url, path):
    logging.info("Downloading image '%s'", image_url)
    cmd = [
        "curl",
        "--fail",
        "--no-progress-meter",
        "--location",
        "--output",
        path,
        image_url,
    ]
    subprocess.run(cmd, check=True)


def convert_image(src, target, format):
    logging.info("Converting image to '%s' format '%s'", format, target)
    cmd = ["qemu-img", "convert", "-f", "qcow2", "-O", format, src, target]
    subprocess.run(cmd, check=True)


def resize_image(path, size):
    logging.info("Resizing image to %s", size)
    cmd = ["qemu-img", "resize", "-q", "-f", "raw", path, size]
    subprocess.run(cmd, check=True)


def clone(src, dst):
    subprocess.run(["cp", "-c", src, dst], check=True)
