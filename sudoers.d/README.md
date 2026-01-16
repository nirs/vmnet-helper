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

## Per-user rule

If you want to allow a user not in the staff group to use vmnet-helper,
create a rule for the specific user. This example allows user `alice` to
use vmnet-helper without a password:

```
$ cat /etc/sudoers.d/vmnet-helper
alice  ALL = (root) NOPASSWD: /opt/vmnet-helper/bin/vmnet-helper
Defaults:alice closefrom_override
```

## Adding new group for vmnet-helper

You can create a new "vmnet" group and add users to the group to allow
them to use vmnet-helper without a password. This example creates the
group "vmnet" and add a sudoers rule for the group:

Find an available group GroupID number:

```console
dscl . list /Groups PrimaryGroupID | awk '{print $2}' | sort -n | tail -1
701
```

We can use gid 702 for the new group.

Create the new group:

```console
sudo dscl . create /Groups/vmnet
sudo dscl . create /Groups/vmnet RealName "vmnet helper"
sudo dscl . create /Groups/vmnet gid 702
```

Add the user "alice" to the group:

```console
sudo dscl . create /Groups/vmnet GroupMembership alice
```

Add a vmnet-helper sudoers rule for the group:

```console
$ cat /etc/sudoers.d/vmnet-helper
%vmnet  ALL = (root) NOPASSWD: /opt/vmnet-helper/bin/vmnet-helper
Defaults:%vmnet closefrom_override
```
