<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Freeing the whale with vmnet and krunkit

<picture><img src="/media/docker.png" alt="Docker whale with vmnet"></picture><br>

Docker Desktop for Mac runs containers inside a Linux VM. The VM has no IP
address on the local network — all networking is proxied through the
`com.docker.backend` process, and published container ports are forwarded on
localhost. This means port conflicts with host services (e.g. a container
registry on port 5000 clashes with AirDrop).

This guide creates an Ubuntu VM with Docker CE, powered by [krunkit] with network
offloading and connected to vmnet via vmnet-helper. The VM is managed by launchd
and gets its own IP address on the local network. The Docker CLI connects to the
VM via SSH. You only need the Docker CLI on the host — Docker Desktop is not
required.

## Requirements

> [!NOTE]
> This tutorial requires macOS 26 or later. On older versions,
> vmnet-helper must be [installed manually][installing].

Install the Docker CLI and VM tools:

```console
brew tap nirs/vmnet-helper
brew tap libkrun/krun
brew trust nirs/vmnet-helper
brew trust libkrun/krun
brew install docker vmnet-helper krunkit cdrtools qemu
```

> [!TIP]
> `brew install docker` installs the Docker CLI only. It works alongside
> Docker Desktop — you can keep both and switch between them using
> `docker context use`.

## Download an Ubuntu 26.04 cloud image

Download an Ubuntu cloud image and convert to raw:

```console
curl --fail --location --output /tmp/ubuntu-26.04.qcow2 \
    https://cloud-images.ubuntu.com/releases/26.04/release/ubuntu-26.04-server-cloudimg-arm64.img
mkdir -p ~/.cache/vm-images
qemu-img convert -f qcow2 -O raw /tmp/ubuntu-26.04.qcow2 \
    ~/.cache/vm-images/ubuntu-26.04.img
```

## Create the Docker VM

Paste this entire block in one terminal session. You can change the variables at
the top if needed.

```console
VM_NAME=docker
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
cp -c ~/.cache/vm-images/ubuntu-26.04.img ~/vms/$VM_NAME/disk.img
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
  - avahi-daemon
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

## Start the Docker VM

```console
launchctl start local.docker
```

Wait for the VM to boot:

```console
until nc -z docker.local 22; do true; done
```

## Install Docker

Update the VM and install Docker CE:

```console
ssh root@docker.local << 'EOF'
apt-get update
apt-get upgrade -y
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io
EOF
```

Restart the VM:

```console
launchctl stop local.docker
until launchctl print gui/$(id -u)/local.docker | grep -q 'state = not running'; do sleep 1; done
launchctl start local.docker
until nc -z docker.local 22; do true; done
```

## Add a Docker context

```console
docker context create vmnet \
    --docker "host=ssh://root@docker.local"
```

Verify the connection:

```console
docker --context vmnet version
```

## Make it your default

```console
docker context use vmnet
```

> [!TIP]
> If you also have Docker Desktop installed, you can switch back to it
> with `docker context use desktop-linux`.

## Playing with Docker

Build a container image:

```console
docker build -t hello - << 'EOF'
FROM alpine
CMD ["echo", "Hello from vmnet!"]
EOF
```

Run it:

```console
docker run --rm hello
```

```
Hello from vmnet!
```

Run an interactive app — it is reachable from your Mac browser at the VM's
hostname, with no localhost port forwarding:

```console
docker run -d --name speedtest -p 80:3000 openspeedtest/latest
open http://docker.local
```

Click **Start** to run a network speed test from your browser to the container.

<picture><img src="/media/speedtest.png" alt="OpenSpeedTest results at docker.local" width="933"></picture>

When you're done, remove the container:

```console
docker rm -f speedtest
```

## Managing the VM

Start the VM:

```console
launchctl start local.docker
until nc -z docker.local 22; do true; done
```

Stop the VM:

```console
launchctl stop local.docker
```

## Cleanup

To remove the VM:

```console
docker context rm vmnet
launchctl stop local.docker
launchctl bootout gui/$(id -u)/local.docker
rm ~/Library/LaunchAgents/local.docker.plist
rm -r ~/vms/docker
ssh-keygen -R docker.local
```


[krunkit]: https://github.com/containers/krunkit
[installing]: README.md#installing
