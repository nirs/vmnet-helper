# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os

from . import store


def config_path(vm):
    return store.vm_path(vm.vm_name, "ssh.config")


def create_config(vm):
    path = config_path(vm)
    if os.path.exists(path):
        logging.debug("Reusing ssh config '%s'", path)
        return

    data = f"""
Host {vm.vm_name}
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
  User {vm.distro}
  Hostname {vm.fqdn()}
"""
    logging.info("Creating ssh config '%s'", path)
    with open(path, "w") as f:
        f.write(data)
