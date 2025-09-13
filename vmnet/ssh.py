# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

from . import store


def config_path(vm):
    return store.vm_path(vm.vm_name, "ssh.config")


def create_config(vm):
    data = f"""
Host {vm.vm_name}
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
  User {vm.distro}
  Hostname {vm.ip_address}
"""
    path = config_path(vm)
    with open(path, "w") as f:
        f.write(data)


def delete_config(vm):
    path = config_path(vm)
    store.silent_remove(path)
