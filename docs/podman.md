<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Flying podman high with vmnet and krunkit

<picture><img src="/media/libkrun.png" alt="You're flying! How? libkrun!"></picture><br>
<sub>Based on [xkcd #353][xkcd] by Randall Munroe ([CC BY-NC 2.5][cc-by-nc])</sub>

podman machine supports two providers: applehv ([vfkit]) and libkrun
([krunkit]). Both use gvproxy and pasta for container networking. They work, but
applehv tops out at 0.91 Gbits/sec TX and 2.36 Gbits/sec RX. libkrun shows much
better performance — 1.25 Gbits/sec TX and 18.69 Gbits/sec RX — but the VM still
has no public IP, so everything goes through port forwarding, which conflicts
with ports used by the host (e.g. a container registry on port 5000 clashes with
AirDrop).

This guide replaces podman machine with a Fedora VM connected to vmnet with
vmnet-helper and managed by launchd. The VM gets its own IP address on the local
network. We test with both vfkit and krunkit. vfkit delivers 4.1x to 13.5x
faster networking compared to podman machine (applehv).  krunkit with network
offloading delivers 2.3x to 30.2x faster networking compared to podman machine
(libkrun).

## Requirements

> [!NOTE]
> - This tutorial requires macOS 26 or later. On older versions,
>   vmnet-helper must be [installed manually][installing].
> - If you have krunkit installed from the old `slp/krunkit` brew tap,
>   you need to [remove it first][old-tap].

```console
brew tap nirs/vmnet-helper
brew tap slp/krun
brew install vmnet-helper vfkit krunkit cdrtools qemu
```

## Download a Fedora 43 cloud image

Download a Fedora cloud image and convert to raw:

> [!NOTE]
> If you already have `~/.cache/vm-images/fedora-44.img` from the
> [launchd guide], skip this step.

```console
curl --fail --location --output /tmp/fedora-44.qcow2 \
    https://download.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/aarch64/images/Fedora-Cloud-Base-Generic-44-1.7.aarch64.qcow2
mkdir -p ~/.cache/vm-images
qemu-img convert -f qcow2 -O raw /tmp/fedora-44.qcow2 \
    ~/.cache/vm-images/fedora-44.img
```

## Creating podman VM with vfkit

### Create the podman VM

Paste this entire block in one terminal session. You can change the variables at
the top if needed.

```console
VM_NAME=podman-vfkit
CPUS=4
MEMORY=2048
DISK_SIZE=100g

MAC_ADDRESS=$(python3 -c "
import os
b = bytearray(os.urandom(6))
b[0] = (b[0] | 2) & 0xFE
print(':'.join(f'{x:02x}' for x in b))
")

mkdir -p ~/vms/$VM_NAME
cp -c ~/.cache/vm-images/fedora-44.img ~/vms/$VM_NAME/disk.img
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

### Start the podman VM

```console
launchctl start local.podman-vfkit
```

Wait for the VM to boot:

```console
until nc -z podman-vfkit.local 22; do true; done
```

> [!NOTE]
> The first boot takes longer while cloud-init installs packages and
> configures podman. After that, boots take about 5 seconds.

Update the VM and restart:

```console
ssh root@podman-vfkit.local dnf update -y
launchctl stop local.podman-vfkit
until launchctl print gui/$(id -u)/local.podman-vfkit | grep -q 'state = not running'; do sleep 1; done
launchctl start local.podman-vfkit
until nc -z podman-vfkit.local 22; do true; done
```

### Add a system connection

```console
podman system connection add vmnet-vfkit \
    --identity ~/.ssh/id_ed25519 \
    ssh://root@podman-vfkit.local/run/podman/podman.sock
```

Verify the connection:

```console
podman -c vmnet-vfkit version
```

### Cleanup

To remove the VM after you are done testing:

```console
podman system connection remove vmnet-vfkit
launchctl stop local.podman-vfkit
launchctl bootout gui/$(id -u)/local.podman-vfkit
rm ~/Library/LaunchAgents/local.podman-vfkit.plist
rm -r ~/vms/podman-vfkit
ssh-keygen -R podman-vfkit.local
```

## Creating podman VM with krunkit

> [!NOTE]
> The krunkit VM enables network offloading (`--enable-tso` and
> `--enable-checksum-offload`), which requires macOS 26.2 or later.
> On older versions, offloading dramatically reduces TX performance.
> If you are on macOS < 26.2, use the vfkit VM instead. See the
> [offloading section][offloading] in the performance guide for details.

### Create the podman VM

Paste this entire block in one terminal session. You can change the variables at
the top if needed.

```console
VM_NAME=podman-krunkit
CPUS=4
MEMORY=2048
DISK_SIZE=100g

MAC_ADDRESS=$(python3 -c "
import os
b = bytearray(os.urandom(6))
b[0] = (b[0] | 2) & 0xFE
print(':'.join(f'{x:02x}' for x in b))
")

mkdir -p ~/vms/$VM_NAME
cp -c ~/.cache/vm-images/fedora-44.img ~/vms/$VM_NAME/disk.img
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
        <string>$(brew --prefix vmnet-helper)/libexec/vmnet-run</string>
        <string>--enable-tso</string>
        <string>--enable-checksum-offload</string>
        <string>--</string>
        <string>$(brew --prefix)/bin/krunkit</string>
        <string>--cpus</string>
        <string>$CPUS</string>
        <string>--memory</string>
        <string>$MEMORY</string>
        <string>--bootloader</string>
        <string>efi,variable-store=$HOME/vms/$VM_NAME/efi-variable-store,create</string>
        <string>--device</string>
        <string>virtio-blk,path=$HOME/vms/$VM_NAME/disk.img</string>
        <string>--device</string>
        <string>virtio-blk,path=$HOME/vms/$VM_NAME/cidata.iso</string>
        <string>--device</string>
        <string>virtio-serial,logFilePath=$HOME/vms/$VM_NAME/serial.log</string>
        <string>--device</string>
        <string>virtio-net,type=unixgram,fd=4,mac=$MAC_ADDRESS,offloading=on</string>
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

### Start the podman VM

```console
launchctl start local.podman-krunkit
```

Wait for the VM to boot:

```console
until nc -z podman-krunkit.local 22; do true; done
```

> [!NOTE]
> The first boot takes longer while cloud-init installs packages and
> configures podman. After that, boots take about 5 seconds.

Update the VM and restart:

```console
ssh root@podman-krunkit.local dnf update -y
launchctl stop local.podman-krunkit
until launchctl print gui/$(id -u)/local.podman-krunkit | grep -q 'state = not running'; do sleep 1; done
launchctl start local.podman-krunkit
until nc -z podman-krunkit.local 22; do true; done
```

### Add a system connection

```console
podman system connection add vmnet-krunkit \
    --identity ~/.ssh/id_ed25519 \
    ssh://root@podman-krunkit.local/run/podman/podman.sock
```

Verify the connection:

```console
podman -c vmnet-krunkit version
```

### Cleanup

To remove the VM after you are done testing:

```console
podman system connection remove vmnet-krunkit
launchctl stop local.podman-krunkit
launchctl bootout gui/$(id -u)/local.podman-krunkit
rm ~/Library/LaunchAgents/local.podman-krunkit.plist
rm -r ~/vms/podman-krunkit
ssh-keygen -R podman-krunkit.local
```

## Taking off

Create a directory for the benchmark results:

```console
mkdir -p out
```

### podman machine (applehv, libkrun)

Create a machine for each provider:

```console
for provider in applehv libkrun; do
    CONTAINERS_MACHINE_PROVIDER=$provider podman machine init --rootful podman-$provider
done
```

We test rootful podman with port forwarding. Traffic goes through the
gvproxy userspace network stack.

```console
for provider in applehv libkrun; do
    export CONTAINERS_MACHINE_PROVIDER=$provider
    podman machine start podman-$provider

    podman -c podman-$provider-root run -d --name iperf3 -p 5201:5201 docker.io/networkstatic/iperf3 -s
    iperf3 -c localhost --json --time 30 > out/podman-$provider-tx.json
    iperf3 -c localhost --json --time 30 --reverse > out/podman-$provider-rx.json
    podman -c podman-$provider-root rm -f iperf3

    podman machine stop podman-$provider
done
```

### vmnet — port forwarding

We use rootful podman with port forwarding, implemented by the kernel using
nftables.

```console
for vm in vfkit krunkit; do
    launchctl start local.podman-$vm
    until nc -z podman-$vm.local 22; do true; done

    podman -c vmnet-$vm run -d --name iperf3 -p 5201:5201 docker.io/networkstatic/iperf3 -s
    iperf3 -c podman-$vm.local --json --time 30 > out/vmnet-$vm-port-forwarding-tx.json
    iperf3 -c podman-$vm.local --json --time 30 --reverse > out/vmnet-$vm-port-forwarding-rx.json
    podman -c vmnet-$vm rm -f iperf3

    launchctl stop local.podman-$vm
    until launchctl print gui/$(id -u)/local.podman-$vm | grep -q 'state = not running'; do sleep 1; done
done
```

### vmnet — host network

The container uses the host network directly, avoiding the port forwarding cost.
If your service can bind to any port, this is the fastest option.

```console
for vm in vfkit krunkit; do
    launchctl start local.podman-$vm
    until nc -z podman-$vm.local 22; do true; done

    podman -c vmnet-$vm run -d --name iperf3 --network host docker.io/networkstatic/iperf3 -s
    iperf3 -c podman-$vm.local --json --time 30 > out/vmnet-$vm-host-network-tx.json
    iperf3 -c podman-$vm.local --json --time 30 --reverse > out/vmnet-$vm-host-network-rx.json
    podman -c vmnet-$vm rm -f iperf3

    launchctl stop local.podman-$vm
    until launchctl print gui/$(id -u)/local.podman-$vm | grep -q 'state = not running'; do sleep 1; done
done
```

### Results

<picture><img src="/media/podman-tx.png" alt="TX benchmark results"></picture>

<picture><img src="/media/podman-rx.png" alt="RX benchmark results"></picture>

krunkit with host networking is the clear winner — 37.75 Gbits/sec TX and 43.64
Gbits/sec RX. Port forwarding has a big impact on krunkit TX (12.06 vs 37.75)
but almost none on RX, since nftables only rewrites incoming packets.

## Make it your default

> [!TIP]
> Our VM is not a complete replacement for podman machine. podman machine
> provides additional features like integration with [ramalama] for AI
> workloads. You can keep both — use podman machine for AI workloads and the
> vmnet VM for everyday container use.

```console
podman system connection default vmnet-krunkit
```

## Managing the VM

Start the VM:

```console
launchctl start local.podman-krunkit
```

Stop the VM:

```console
launchctl stop local.podman-krunkit
```

[xkcd]: https://xkcd.com/353/
[cc-by-nc]: https://creativecommons.org/licenses/by-nc/2.5/
[old-tap]: https://github.com/containers/krunkit#removing-the-old-homebrew-tap
[vfkit]: https://github.com/crc-org/vfkit
[krunkit]: https://github.com/containers/krunkit
[libkrun]: https://github.com/containers/libkrun
[ramalama]: https://github.com/containers/ramalama
[offloading]: /docs/performance.md#offloading
[installing]: /README.md#installing
[launchd guide]: /docs/launchd.md
