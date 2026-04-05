<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Run podman faster with vmnet-run

podman machine uses gvproxy and pasta for container networking. They work, but
in our benchmarks TX tops out at 0.92 Gbits/sec and RX at 2.43 Gbits/sec. The VM
has no public IP, so everything goes through port forwarding — which conflicts
with ports used by the host (e.g. a container registry on port 5000 clashes with
AirDrop).

This guide replaces podman machine with a Fedora VM connected to vmnet with
vmnet-helper and managed by launchd. The VM gets its own IP address on the local
network, and delivers 3.9x to 13.5x faster networking.

## Prerequisites

> [!NOTE]
> This tutorial requires macOS 26 or later. On older versions,
> vmnet-helper must be [installed manually][installing].

```console
brew tap nirs/vmnet-helper
brew install vmnet-helper vfkit cdrtools qemu
```

## Download a Fedora 43 cloud image

Download a Fedora cloud image and convert to raw:

> [!NOTE]
> If you already have `~/.cache/vm-images/fedora-43.img` from the
> [launchd guide], skip this step.

```console
curl --fail --location --output /tmp/fedora-43.qcow2 \
    https://download.fedoraproject.org/pub/fedora/linux/releases/43/Cloud/aarch64/images/Fedora-Cloud-Base-Generic-43-1.6.aarch64.qcow2
mkdir -p ~/.cache/vm-images
qemu-img convert -f qcow2 -O raw /tmp/fedora-43.qcow2 \
    ~/.cache/vm-images/fedora-43.img
```

## Create the podman VM

Paste this entire block in one terminal session. You can change the variables at
the top if needed.

```console
VM_NAME=podman
CPUS=4
MEMORY=4096
DISK_SIZE=100g
MAC_ADDRESS=$(python3 -c "
import os
b = bytearray(os.urandom(6))
b[0] = (b[0] | 2) & 0xFE
print(':'.join(f'{x:02x}' for x in b))
")

mkdir -p ~/vms/$VM_NAME
cp -c ~/.cache/vm-images/fedora-43.img ~/vms/$VM_NAME/disk.img
qemu-img resize -q -f raw ~/vms/$VM_NAME/disk.img $DISK_SIZE

cat > ~/vms/$VM_NAME/user-data << EOF
#cloud-config
password: password
chpasswd:
  expire: false
disable_root: false
ssh_authorized_keys:
  - "$(cat ~/.ssh/id_ed25519.pub)"
users:
  - default
  - name: root
    ssh_authorized_keys:
      - "$(cat ~/.ssh/id_ed25519.pub)"
packages:
  - avahi
  - podman
runcmd:
  - systemctl enable --now avahi-daemon
  - systemctl enable --now podman.socket
EOF

cat > ~/vms/$VM_NAME/meta-data << EOF
instance-id: $(uuidgen)
local-hostname: $VM_NAME
EOF

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

(
    cd ~/vms/$VM_NAME
    mkisofs -output cidata.iso -volid cidata -joliet -rock \
        user-data meta-data network-config
)

cat > ~/Library/LaunchAgents/local.$VM_NAME.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>local.$VM_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <!-- On macOS 15, use /opt/vmnet-helper/bin/vmnet-run -->
        <string>$(brew --prefix vmnet-helper)/libexec/vmnet-run</string>
        <string>--</string>
        <string>$(brew --prefix)/bin/vfkit</string>
        <string>--cpus</string>
        <string>$CPUS</string>
        <string>--memory</string>
        <string>$MEMORY</string>
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

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.$VM_NAME.plist
```

## Start the podman VM

```console
launchctl start local.podman
```

Wait for the VM to boot:

```console
until nc -z podman.local 22; do sleep 1; done
```

> [!NOTE]
> The first boot takes longer while cloud-init installs packages and
> configures podman. After that, boots take about 5 seconds.

Update the VM and restart:

```console
ssh root@podman.local dnf update -y
launchctl stop local.podman
launchctl start local.podman
until nc -z podman.local 22; do sleep 1; done
```

## Add a system connection

Add the connection:

```console
podman system connection add vmnet \
    --identity ~/.ssh/id_ed25519 \
    ssh://root@podman.local/run/podman/podman.sock
```

Verify the connection:

```console
podman -c vmnet version
```

```
Client:        Podman Engine
Version:       5.8.1
API Version:   5.8.1
Go Version:    go1.26.1
Built:         Wed Mar 11 15:31:04 2026
Build Origin:  brew
OS/Arch:       darwin/arm64

Server:       Podman Engine
Version:      5.8.1
API Version:  5.8.1
Go Version:   go1.25.7 X:nodwarf5
Git Commit:   c6077f645788743258a1a749f8005b4fb3cbe533
Built:        Wed Mar 11 02:00:00 2026
OS/Arch:      linux/arm64
```

## Will it blend?

### Baseline: podman machine

If you have podman machine running, measure it:

```console
podman run -d --name iperf3 -p 5201:5201 docker.io/networkstatic/iperf3 -s
iperf3 -c localhost -t 30
iperf3 -c localhost -t 30 -R
podman rm -f iperf3
```

### Our podman VM

```console
podman -c vmnet run -d --name iperf3 -p 5201:5201 docker.io/networkstatic/iperf3 -s
iperf3 -c podman.local -t 30
iperf3 -c podman.local -t 30 -R
podman -c vmnet rm -f iperf3
```

### Using host networking

If your service can bind to any port, host networking bypasses nftables
entirely:

```console
podman -c vmnet run -d --name iperf3 --network host docker.io/networkstatic/iperf3 -s
iperf3 -c podman.local -t 30
iperf3 -c podman.local -t 30 -R
podman -c vmnet rm -f iperf3
```

### Results

**TX** (`iperf3 -c <host> -t 30`)

| Machine        | Container       | TX             | Retransmits | Change |
|----------------|-----------------|---------------:|------------:|-------:|
| podman machine | port forwarding | 0.92 Gbits/sec |           0 |        |
| vmnet          | port forwarding | 11.7 Gbits/sec |           0 | 12.7x  |
| vmnet          | host network    | 12.4 Gbits/sec |           0 | 13.5x  |

**RX** (`iperf3 -c <host> -t 30 -R`)

| Machine        | Container       | RX             | Retransmits | Change |
|----------------|-----------------|---------------:|------------:|-------:|
| podman machine | port forwarding | 2.43 Gbits/sec |         247 |        |
| vmnet          | port forwarding | 9.60 Gbits/sec |       1,232 |  3.9x  |
| vmnet          | host network    | 9.76 Gbits/sec |           0 |  4.0x  |

## Make it your default

```console
podman system connection default vmnet
```

From now on:

```console
podman run ...
```

## Managing the VM

```console
launchctl stop local.podman
launchctl start local.podman
```

## Cleanup

```console
podman system connection remove vmnet
launchctl stop local.podman
launchctl bootout gui/$(id -u)/local.podman
rm ~/Library/LaunchAgents/local.podman.plist
rm -r ~/vms/podman
ssh-keygen -R podman.local
```

[installing]: /README.md#installing
[launchd guide]: /docs/launchd.md
