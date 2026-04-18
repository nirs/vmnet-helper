# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import glob
import logging
import os
import subprocess
import uuid

import yaml

from . import store

# Distro-specific cloud-init user-data configuration. Keys match
# cloud-init module names so the dict can be merged directly into the
# user-data.
DISTROS = {
    # Ubuntu auto-enables and starts daemons on package install.
    "ubuntu": {
        "packages": ["avahi-daemon"],
    },
    "fedora": {
        "packages": ["avahi"],
        "runcmd": ["systemctl enable --now avahi-daemon"],
    },
    "alpine": {
        "packages": ["avahi"],
        # Alpine needs dbus in the default runlevel — avahi depends on it
        # but `apk add avahi` does not enable it. Add both to the default
        # runlevel for subsequent boots. Start dbus explicitly before avahi
        # because OpenRC dependency resolution does not work during
        # cloud-init runcmd.
        "runcmd": [
            "rc-update add dbus",
            "rc-update add avahi-daemon",
            "rc-service dbus start",
            "rc-service avahi-daemon start",
        ],
    },
}


def create_iso(vm):
    """
    Create cloud-init iso image.

    The iso is created on first run and reused on subsequent runs so
    cloud-init skips re-provisioning. Delete the iso to force recreation.
    """
    vm_home = store.vm_path(vm.vm_name)
    cidata = os.path.join(vm_home, "cidata.iso")

    if os.path.exists(cidata):
        logging.debug("Reusing cloud-init iso '%s'", cidata)
        return cidata

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
    data = {
        "password": "password",
        "chpasswd": {
            "expire": False,
        },
        "ssh_authorized_keys": public_keys(),
    }
    data.update(DISTROS[vm.distro])

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
            "eth0": {
                "match": {
                    "macaddress": vm.mac_address,
                },
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
