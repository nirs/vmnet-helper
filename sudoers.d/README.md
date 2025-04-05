<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# vmnet-helper sudoers rule

To install the default vmnet-helper sudoers rule run:

```sh
sudo install -m 0640 /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/vmnet-helper /etc/sudoers.d/
```

## The default rule

```console
$ cat /etc/sudoers.d/vmnet-helper
%staff  ALL = (root) NOPASSWD: /opt/vmnet-helper/bin/vmnet-helper
Defaults:%staff closefrom_override
```

This rule allows users in the `staff` group to run the vmnet helper
with sudo without a password:

```sh
sudo --non-interactive --close-from 8 /opt/vmnet-helper/bin/vmnet-helper --fd 7
```

Note that to allow passing the file descriptor to the vmnet-helper
process via sudo, you must use the `--close-from` option. This requires
allowing the `closefrom_override` option for the user or group running
the command.
