# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import glob
import os
import platform
import subprocess
import uuid

import yaml

from . import store

# The serial console device in the guest, used to communicate the guest ip
# address.
# TODO: find a way to detect this programmatically instead of hard coding.
SERIAL_CONSOLE = {
    "vfkit": {"arm64": "hvc0", "x86_64": "hvc0"},
    "krunkit": {"arm64": "hvc0", "x86_64": "hvc0"},
    "qemu": {"arm64": "ttyAMA0", "x86_64": "ttyS0"},
}


def create_iso(vm):
    """
    Create cloud-init iso image.

    We create a new cidata.iso with new instance id for every run to update the
    vm network configuration and report the vm ip address.
    """
    vm_home = store.vm_path(vm.vm_name)
    cidata = os.path.join(vm_home, "cidata.iso")
    create_user_data(vm)
    create_meta_data(vm)
    create_network_config(vm)
    cmd = [
        "mkisofs",
        "-output",
        "cidata.iso",
        "-volid",
        "cidata",
        "-joliet",
        "-rock",
        "user-data",
        "meta-data",
        "network-config",
    ]
    print(f"Creating cloud-init iso '{cidata}'")
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=vm_home,
    )
    return cidata


def create_user_data(vm):
    """
    Create cloud-init user-data file.
    """
    serial_console = f"/dev/{SERIAL_CONSOLE[vm.driver][platform.machine()]}"
    data = {
        "password": "password",
        "chpasswd": {
            "expire": False,
        },
        "ssh_authorized_keys": public_keys(),
        "runcmd": [
            "ip_address=$(ip -4 -j addr show dev vmnet0 | jq -r '.[0].addr_info[0].local')",
            f'printf "\n{vm.vm_name} address: %s\n" "$ip_address" > "{serial_console}"',
        ],
    }

    # Skip jq install if posisble to minimize startup time in the CI.
    if vm.distro != "ubuntu":
        data["packages"] = ["jq"]
        data["package_update"] = False
        data["package_upgrade"] = False

    path = store.vm_path(vm.vm_name, "user-data")
    with open(path, "w") as f:
        f.write("#cloud-config\n")
        yaml.dump(data, f, sort_keys=False)


def create_meta_data(vm):
    """
    Create cloud-init meta-data file.
    """
    data = {
        "instance-id": str(uuid.uuid4()),
        "local-hostname": vm.vm_name,
    }
    path = store.vm_path(vm.vm_name, "meta-data")
    with open(path, "w") as f:
        yaml.dump(data, f, sort_keys=False)


def create_network_config(vm):
    """
    Create cloud-init network-config file.
    """
    data = {
        "version": 2,
        "ethernets": {
            "vmnet0": {
                "match": {
                    "macaddress": vm.mac_address,
                },
                "set-name": "vmnet0",
                "dhcp4": True,
                "dhcp-identifier": "mac",
            },
        },
    }
    path = store.vm_path(vm.vm_name, "network-config")
    with open(path, "w") as f:
        yaml.dump(data, f, sort_keys=False)


def public_keys():
    """
    Read public keys under ~/.ssh/
    """
    keys = []
    for key in glob.glob(os.path.expanduser("~/.ssh/id_*.pub")):
        with open(key) as f:
            keys.append(f.readline().strip())
    return keys
