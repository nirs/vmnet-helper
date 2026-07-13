# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import glob
import logging
import os
import subprocess
import uuid
import tempfile

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
    "debian": {
        "packages": ["avahi-daemon"],
    },
    "alpine": {
        "packages": ["avahi"],
        "runcmd": [
            # Fix dhcpcd to use MAC client identifier instead of
            # DUID+IAID, and restart to release the bad first boot
            # lease. https://github.com/nirs/vmnet-helper/issues/54
            "sed -i 's/^duid/clientid/' /etc/dhcpcd.conf",
            "dhcpcd --release eth0",
            "rc-service dhcpcd restart",
            # Enable and start avahi-daemon. dbus must be added
            # explicitly — avahi depends on it but `apk add avahi`
            # does not enable it. Start dbus before avahi because
            # OpenRC dependency resolution does not work during
            # cloud-init runcmd.
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

    user_data = create_user_data(vm)
    network_config = create_network_config(vm)

    if os.path.exists(cidata):
        user_data_matches = file_matches(user_data, cidata, "user-data")
        network_config_matches = file_matches(network_config, cidata, "network-config")
        if user_data_matches and network_config_matches:
            logging.debug("Reusing cloud-init iso '%s'", cidata)
            return cidata

    logging.info("Creating cloud-init iso '%s'", cidata)

    with tempfile.TemporaryDirectory() as tmp:
        meta_data_path = os.path.join(tmp, "meta-data")
        user_data_path = os.path.join(tmp, "user-data")
        network_config_path = os.path.join(tmp, "network-config")

        with open(meta_data_path, "w") as f:
            yaml.dump(create_meta_data(vm), f, sort_keys=False)

        with open(user_data_path, "w") as f:
            f.write("#cloud-config\n")
            yaml.dump(user_data, f, sort_keys=False)

        with open(network_config_path, "w") as f:
            yaml.dump(network_config, f, sort_keys=False)

        cmd = [
            "mkisofs",
            "-output",
            cidata,
            "-volid",
            "cidata",
            "-joliet",
            "-rock",
            "user-data",
            "meta-data",
            "network-config",
        ]
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmp,
        )

    return cidata


def create_user_data(vm):
    """
    Create cloud-init user-data dict.
    """
    data = {
        "password": "password",
        "chpasswd": {
            "expire": False,
        },
        "ssh_authorized_keys": public_keys(),
    }
    data.update(DISTROS[vm.distro])
    return data


def create_meta_data(vm):
    """
    Create cloud-init meta-data dict.
    """
    return {
        "instance-id": str(uuid.uuid4()),
        "local-hostname": vm.hostname(),
    }


def create_network_config(vm):
    """
    Create cloud-init network-config dict.
    """
    return {
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


def file_matches(data, iso_path, file_path):
    """
    Parses the YAML file at 'file_path' in the ISO 'iso_path', and compares it to 'data'.

    Returns True if they match, False otherwise.
    """
    extract = subprocess.run(
        ["bsdtar", "-xf", iso_path, "--to-stdout", file_path],
        check=True,
        stdout=subprocess.PIPE,
    )
    file_data = yaml.safe_load(extract.stdout)
    return data == file_data


def public_keys():
    """
    Read public keys under ~/.ssh/
    """
    keys = []
    for key in glob.glob(os.path.expanduser("~/.ssh/id_*.pub")):
        with open(key) as f:
            keys.append(f.readline().strip())
    return keys
