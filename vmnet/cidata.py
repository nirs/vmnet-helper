# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import glob
import logging
import os
import subprocess
import uuid

import yaml

from . import store

# Distro-specific package names and optional enable commands.
PACKAGES = {
    "avahi": {
        # Ubuntu auto-enables and starts daemons on package install.
        "ubuntu": {"name": "avahi-daemon"},
        "fedora": {
            "name": "avahi",
            "runcmd": ["systemctl enable --now avahi-daemon"],
        },
        # Alpine needs dbus in the default runlevel — avahi depends on it
        # but `apk add avahi` does not enable it. Add both to the default
        # runlevel for subsequent boots. Start dbus explicitly before avahi
        # because OpenRC dependency resolution does not work during
        # cloud-init runcmd.
        "alpine": {
            "name": "avahi",
            "runcmd": [
                "rc-update add dbus",
                "rc-update add avahi-daemon",
                "rc-service dbus start",
                "rc-service avahi-daemon start",
            ],
        },
    },
}


def create_iso(vm):
    """
    Create cloud-init iso image.

    We create a new cidata.iso with new instance id for every run to update the
    vm network configuration and install avahi for mDNS discovery.
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
    logging.info("Creating cloud-init iso '%s'", cidata)
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
    avahi_pkg = PACKAGES["avahi"][vm.distro]
    data = {
        "password": "password",
        "chpasswd": {
            "expire": False,
        },
        "ssh_authorized_keys": public_keys(),
        "packages": [avahi_pkg["name"]],
    }
    if "runcmd" in avahi_pkg:
        data["runcmd"] = avahi_pkg["runcmd"]

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
        "local-hostname": vm.hostname(),
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
                "dhcp4-overrides": {
                    "use-dns": False,
                },
                "nameservers": {
                    "addresses": vm.dns_servers,
                },
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
