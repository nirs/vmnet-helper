# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import os
import platform
import subprocess

from . import store

IMAGES = {
    "ubuntu": {
        "arm64": {
            "image": "https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-arm64.img",
        },
        "x86_64": {
            "image": "https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-amd64.img",
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


def create_disk(vm_name, distro):
    """
    Create a disk from image using copy-on-write.
    """
    image_info = IMAGES[distro][platform.machine()]
    disk = {"image": store.vm_path(vm_name, "disk.img")}
    if not os.path.isfile(disk["image"]):
        image = create_image(image_info["image"], format="raw", size="20g")
        print(f"Creating image '{disk['image']}'")
        clone(image, disk['image'])
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


def convert_image(src, target, format):
    print(f"Converting image to '{format}' format '{target}'")
    cmd = ["qemu-img", "convert", "-f", "qcow2", "-O", format, src, target]
    subprocess.run(cmd, check=True)


def resize_image(path, size):
    print(f"Resizing image to {size}")
    cmd = ["qemu-img", "resize", "-q", "-f", "raw", path, size]
    subprocess.run(cmd, check=True)


def clone(src, dst):
    subprocess.run(["cp", "-c", src, dst], check=True)
