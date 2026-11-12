# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import ipaddress
import glob
import logging
import os
import uuid
import tempfile

import yaml

from . import privileges
from . import process
from . import store

# Enable busy polling for network sockets to reduce softirq overhead.
# Without this, ksoftirqd saturates a single CPU core during high
# throughput benchmarks, limiting performance to ~30 Gbps. With busy
# polling, packet processing shifts to the application threads,
# reaching ~37 Gbps. Requires CONFIG_NET_RX_BUSY_POLL=y in the guest
# kernel (enabled by default in Ubuntu, Fedora, Debian, and Alpine).
# This increases CPU usage when the VM is idle, so it is only
# appropriate for benchmark VMs, not general purpose workloads.
# Applied via bootcmd so it runs on every boot and is absent when
# --busy-poll is not used.
_BUSY_POLL_CMDS = [
    "sysctl -w net.core.busy_poll=50",
    "sysctl -w net.core.busy_read=50",
]

# Distro-specific cloud-init user-data configuration. Keys match
# cloud-init module names so the dict can be merged directly into the
# user-data.
DISTROS = {
    # Ubuntu auto-enables and starts daemons on package install.
    "ubuntu": {
        "packages": ["avahi-daemon"],
        # systemd-networkd-wait-online may block boot for 2 minutes waiting
        # for all interfaces to be fully configured. We only need eth0
        # (DHCP from vmnet) and don't care about the online target.
        "bootcmd": [
            "systemctl mask systemd-networkd-wait-online.service",
        ],
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

        uid, gid = privileges.creds()
        if uid and gid:
            for path in tmp, meta_data_path, user_data_path, network_config_path:
                os.chown(path, uid, gid)

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
        process.run(
            *cmd,
            stdout=process.PIPE,
            stderr=process.PIPE,
            cwd=tmp,
            check=True,
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
    if vm.busy_poll:
        data.setdefault("bootcmd", []).extend(_BUSY_POLL_CMDS)
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
    data = {
        "version": 2,
        "ethernets": {
            "eth0": {
                "match": {
                    "macaddress": vm.mac_address,
                },
                "dhcp4": vm.args.ip_address is None,
                "nameservers": {
                    "addresses": vm.dns_servers,
                },
            },
        },
    }
    if vm.args.ip_address:
        mask = vm.args.subnet_mask or vm.args.host_subnet_mask or "255.255.255.0"
        route = vm.args.start_address or vm.args.host_ip_address
        data["ethernets"]["eth0"]["addresses"] = [
            ipaddress.IPv4Interface((vm.args.ip_address, mask)).with_prefixlen
        ]
        data["ethernets"]["eth0"]["routes"] = [
            {
                "to": "default",
                "via": str(route),
            }
        ]
    else:
        data["ethernets"]["eth0"]["dhcp-identifier"] = "mac"
        data["ethernets"]["eth0"]["dhcp4-overrides"] = {"use-dns": False}
    return data


def file_matches(data, iso_path, file_path):
    """
    Parses the YAML file at 'file_path' in the ISO 'iso_path', and compares it to 'data'.

    Returns True if they match, False otherwise.
    """
    extract = process.run(
        "bsdtar",
        "-xf",
        iso_path,
        "--to-stdout",
        file_path,
        stdout=process.PIPE,
        check=True,
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
