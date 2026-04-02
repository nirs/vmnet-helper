<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Integrating with launchd

## Overview

This guide shows how to run persistent virtual machines on macOS
using vmnet-run and launchd.

vmnet-run supervises both vmnet-helper and the VM process as
children, making it a natural fit for launchd — `launchctl stop`
cleanly terminates everything, and `launchctl start` brings it back
up. No PID files or wrapper scripts are needed.

By the end of this guide you will have a Fedora VM managed by
launchd that you can start and stop with `launchctl`.

## Prerequisites

Install using [Homebrew](https://brew.sh/):

```console
brew tap nirs/vmnet-helper
brew install vmnet-helper vfkit cdrtools qemu
```

- **vmnet-helper** v0.11.0+ — provides vmnet-run
- **vfkit** — lightweight macOS virtual machine
- **cdrtools** — provides `mkisofs` for creating cloud-init ISOs
- **qemu** — provides `qemu-img` for image conversion and resizing

## Preparing the image cache

Download a cloud image once and convert it to raw format. The cached
image can be reused for multiple VMs.

```console
curl --fail --location --output fedora-43.qcow2 \
    https://download.fedoraproject.org/pub/fedora/linux/releases/43/Cloud/aarch64/images/Fedora-Cloud-Base-Generic-43-1.6.aarch64.qcow2

mkdir -p ~/.cache/vm-images

qemu-img convert -f qcow2 -O raw fedora-43.qcow2 \
    ~/.cache/vm-images/fedora-43.img
```

## Creating a VM

Choose a VM name that is a valid hostname. The name is used as the
mDNS hostname for SSH access (e.g., `ssh fedora@my-vm.local`).

```console
VM_NAME=my-vm
```

### VM directory

Create the VM directory, copy the cached image using copy-on-write,
and resize it:

```console
mkdir -p ~/vms/$VM_NAME
cp -c ~/.cache/vm-images/fedora-43.img ~/vms/$VM_NAME/disk.img
qemu-img resize -q -f raw ~/vms/$VM_NAME/disk.img 20g
```

### MAC address

Generate a locally administered unicast MAC address. Use the same
address in the cloud-init network-config and the vfkit command to
get a stable DHCP IP across restarts.

```console
MAC_ADDRESS=$(python3 -c "
import os
b = bytearray(os.urandom(6))
b[0] = (b[0] | 2) & 0xFE
print(':'.join(f'{x:02x}' for x in b))
")
echo $MAC_ADDRESS
```

### Cloud-init

Create the cloud-init files in `~/vms/$VM_NAME/`. These examples are
for Fedora; see the [cloud-init documentation][cloud-init] for other
distributions.

`user-data`:

```console
cat > ~/vms/$VM_NAME/user-data << EOF
#cloud-config
password: password
chpasswd:
  expire: false
ssh_authorized_keys:
  - "$(cat ~/.ssh/id_ed25519.pub)"
packages:
  - avahi
runcmd:
  - systemctl enable --now avahi-daemon
EOF
```

`meta-data`:

```console
cat > ~/vms/$VM_NAME/meta-data << EOF
instance-id: $(uuidgen)
local-hostname: $VM_NAME
EOF
```

`network-config`:

```console
cat > ~/vms/$VM_NAME/network-config << EOF
version: 2
ethernets:
  eth0:
    match:
      macaddress: $MAC_ADDRESS
    set-name: eth0
    dhcp4: true
    dhcp-identifier: mac
    dhcp4-overrides:
      use-dns: false
    nameservers:
      addresses:
        - 8.8.8.8
        - 1.1.1.1
EOF
```

> [!NOTE]
> The nameservers override DHCP-provided DNS to avoid DNS issues on
> managed macOS machines. Adjust to your preferred DNS servers.

Create the cloud-init ISO from the files:

```console
(cd ~/vms/$VM_NAME && mkisofs -output cidata.iso -volid cidata -joliet -rock \
    user-data meta-data network-config)
```

### Creating the plist

Generate a UUID for `--interface-id` to get stable MAC/IP assignments
from vmnet across restarts:

```console
INTERFACE_ID=$(uuidgen)
```

> [!NOTE]
> On macOS 15, replace the vmnet-run path in the plist with
> `/opt/vmnet-helper/bin/vmnet-run`.

Create the plist:

```console
cat > ~/Library/LaunchAgents/local.$VM_NAME.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>local.$VM_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(brew --prefix vmnet-helper)/libexec/vmnet-run</string>
        <string>--interface-id</string>
        <string>$INTERFACE_ID</string>
        <string>--</string>
        <string>$(brew --prefix)/bin/vfkit</string>
        <string>--cpus</string>
        <string>2</string>
        <string>--memory</string>
        <string>2048</string>
        <string>--bootloader</string>
        <string>efi,variable-store=$HOME/vms/$VM_NAME/efi-variable-store,create</string>
        <string>--device</string>
        <string>usb-mass-storage,path=$HOME/vms/$VM_NAME/cidata.iso,readonly</string>
        <string>--device</string>
        <string>virtio-blk,path=$HOME/vms/$VM_NAME/disk.img</string>
        <string>--device</string>
        <string>virtio-serial,logFilePath=$HOME/vms/$VM_NAME/serial.log</string>
        <string>--device</string>
        <string>virtio-net,fd=4,mac=$MAC_ADDRESS</string>
        <string>--device</string>
        <string>virtio-rng</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardErrorPath</key>
    <string>$HOME/vms/$VM_NAME/vm.log</string>
</dict>
</plist>
EOF
```

Load the agent:

```console
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.$VM_NAME.plist
```

### Plist options

Add these keys to the plist `<dict>` for additional behavior:

- **KeepAlive**: Set to `<true/>` to automatically restart the VM
  if it crashes.
- **RunAtLoad**: Set to `<true/>` to start the VM automatically
  when the agent is loaded (e.g., on login).

See the [launchd.plist documentation][launchd-plist] for all
available options.

## Managing the VM

Start the VM:

```console
launchctl start local.$VM_NAME
```

Stop the VM (cleanly terminates vmnet-helper and vfkit):

```console
launchctl stop local.$VM_NAME
```

### Checking status

```console
launchctl print gui/$(id -u)/local.$VM_NAME | grep "^\tstate"
```

When the VM is running:

```
	state = running
```

When the VM is stopped:

```
	state = not running
```

## Connecting with SSH

After starting the VM, wait a few seconds for it to boot and then
connect using the mDNS hostname:

```console
ssh fedora@my-vm.local
```

The username is `fedora` for Fedora cloud images. The VM is
accessible via mDNS thanks to the avahi package installed by
cloud-init.

### SSH config

To avoid specifying the username every time, create an SSH config
for the VM:

```console
cat > ~/vms/$VM_NAME/ssh.config << EOF
Host $VM_NAME.local
    User fedora
EOF
```

Then add this to your `~/.ssh/config`:

```
Include ~/vms/*/ssh.config
```

Now you can connect without specifying the username:

```console
ssh my-vm.local
```

## Deleting a VM

> [!WARNING]
> This deletes all VM data including the disk image.

```console
launchctl stop local.$VM_NAME
launchctl bootout gui/$(id -u)/local.$VM_NAME
rm ~/Library/LaunchAgents/local.$VM_NAME.plist
rm -r ~/vms/$VM_NAME
```

[cloud-init]: https://cloudinit.readthedocs.io/
[launchd-plist]: https://developer.apple.com/documentation/servicemanagement/property-list-keys
