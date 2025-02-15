# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import os
import platform
import subprocess

from . import store

IMAGES = {
    "ubuntu": {
        "arm64": "https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-arm64.img",
        "x86_64": "https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-amd64.img",
    },
    "alpine": {
        "arm64": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/nocloud_alpine-3.21.2-aarch64-uefi-cloudinit-r0.qcow2",
    },
    "fedora": {
        "arm64": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Cloud/aarch64/images/Fedora-Cloud-Base-Generic-41-1.4.aarch64.qcow2",
    },
}


def create_disk(vm_name, distro):
    """
    Create a disk from image using copy-on-write.
    """
    disk = store.vm_path(vm_name, "disk.img")
    if not os.path.isfile(disk):
        image = create_image(distro)
        print(f"Creating disk '{disk}'")
        subprocess.run(["cp", "-c", image, disk], check=True)
    return disk


def create_image(distro):
    image_url = IMAGES[distro][platform.machine()]
    image_hash = hashlib.sha256(image_url.encode()).hexdigest()
    path = store.cache_path("images", image_hash, "disk.img")
    if not os.path.exists(path):
        image_dir = os.path.dirname(path)
        os.makedirs(image_dir, exist_ok=True)
        tmp_path = path + ".tmp"
        try:
            download_image(image_url, tmp_path)
            convert_image(tmp_path, path)
            resize_image(path, "20g")
        except:
            store.silent_remove(path)
            raise
        finally:
            store.silent_remove(tmp_path)
    return path


def download_image(image_url, path):
    print(f"Downloading image '{image_url}'")
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


def convert_image(src, target):
    print(f"Converting image to raw format '{target}'")
    cmd = ["qemu-img", "convert", "-f", "qcow2", "-O", "raw", src, target]
    subprocess.run(cmd, check=True)


def resize_image(path, size):
    print(f"Resizing image to {size}")
    cmd = ["qemu-img", "resize", "-q", "-f", "raw", path, size]
    subprocess.run(cmd, check=True)
