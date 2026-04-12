<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# FreeBSD VM with vmnet

This guide shows how to run a FreeBSD VM connected to vmnet with
vmnet-helper.

FreeBSD 15.0 cloud images ship with [nuageinit], a lightweight Lua-based
cloud-init implementation. It supports NoCloud cidata ISOs for SSH key
provisioning. The VM obtains its IP address via DHCP from vmnet's
built-in DHCP server.

## Requirements

> [!NOTE]
> - This tutorial requires macOS 26 or later. On older versions,
>   vmnet-helper must be [installed manually][installing].
> - FreeBSD aarch64 does not work with vfkit or krunkit. Use QEMU
>   with HVF acceleration instead.

```console
brew tap nirs/vmnet-helper
brew install vmnet-helper cdrtools qemu
```

## Download a FreeBSD 15.0 cloud image

Download the FreeBSD CLOUDINIT image and decompress:

```console
curl --fail --location --output /tmp/freebsd-15.raw.xz \
    https://download.freebsd.org/releases/VM-IMAGES/15.0-RELEASE/aarch64/Latest/FreeBSD-15.0-RELEASE-arm64-aarch64-BASIC-CLOUDINIT-ufs.raw.xz
mkdir -p ~/.cache/vm-images
xz -dk /tmp/freebsd-15.raw.xz
mv /tmp/freebsd-15.raw ~/.cache/vm-images/freebsd-15.img
```

> [!TIP]
> If the download is slow, try a [regional mirror][mirrors] such as
> `http://ftp2.de.freebsd.org/pub/FreeBSD/releases/VM-IMAGES/15.0-RELEASE/aarch64/Latest/`.

## Create the VM

Paste this entire block in one terminal session. You can change the
variables at the top if needed.

```console
VM_NAME=freebsd
DISK_SIZE=20g

MAC_ADDRESS=$(python3 -c "
import os
b = bytearray(os.urandom(6))
b[0] = (b[0] | 2) & 0xFE
print(':'.join(f'{x:02x}' for x in b))
")

mkdir -p ~/vms/$VM_NAME
cp -c ~/.cache/vm-images/freebsd-15.img ~/vms/$VM_NAME/disk.img
qemu-img resize -q -f raw ~/vms/$VM_NAME/disk.img $DISK_SIZE

cat > ~/vms/$VM_NAME/user-data << EOF
#cloud-config
ssh_authorized_keys:
  - "$(cat ~/.ssh/id_ed25519.pub)"
EOF

cat > ~/vms/$VM_NAME/meta-data << EOF
instance-id: $(uuidgen)
local-hostname: $VM_NAME
EOF

(
    cd ~/vms/$VM_NAME
    mkisofs -output cidata.iso -volid cidata -joliet -rock \
        user-data meta-data
)
```

## Run the VM

The VM obtains its IP address via DHCP from vmnet's built-in DHCP
server:

```console
$(brew --prefix vmnet-helper)/libexec/vmnet-run \
    --start-address 192.168.240.1 \
    --end-address 192.168.240.254 \
    --subnet-mask 255.255.255.0 \
    -- \
    qemu-system-aarch64 \
    -m 2048 \
    -cpu host \
    -machine virt,accel=hvf \
    -smp 2 \
    -drive if=pflash,format=raw,readonly=on,file=/opt/homebrew/share/qemu/edk2-aarch64-code.fd \
    -drive "file=$HOME/vms/$VM_NAME/disk.img,if=virtio,format=raw" \
    -drive "file=$HOME/vms/$VM_NAME/cidata.iso,id=cdrom0,if=none,format=raw,readonly=on" \
    -device virtio-scsi-pci,id=scsi0 \
    -device scsi-cd,bus=scsi0.0,drive=cdrom0 \
    -netdev dgram,id=net1,local.type=fd,local.str=4 \
    -device "virtio-net-pci,netdev=net1,mac=$MAC_ADDRESS" \
    -monitor none \
    -serial file:$HOME/vms/$VM_NAME/serial.log \
    -nographic \
    -nodefaults \
    -device virtio-rng-pci
```

Press *Control+C* to stop the VM.

> [!NOTE]
> The first boot takes longer because the image runs `freebsd-update`
> to check for security patches. Wait for sshd to start before
> connecting — you can watch progress with `tail -f ~/vms/freebsd/serial.log`.

## Connect with SSH

Find the DHCP-assigned IP address in the serial log:

```console
grep 'bound to' ~/vms/freebsd/serial.log
```

Example output:

```
bound to 192.168.240.2 -- renewal in 300 seconds.
```

Then connect in another terminal:

```console
ssh freebsd@192.168.240.2
```

The default user is `freebsd`, authenticated by the SSH key configured
in user-data.

## Setting up mDNS

To access the VM by hostname instead of IP address, install
[mDNSResponder] inside the VM:

```console
su -
pkg install -y mDNSResponder

cat > /usr/local/etc/mdnsresponderposix.conf << EOF
freebsd
_workstation._tcp
9
EOF

sysrc mdnsresponderposix_enable=YES
sysrc mdnsresponderposix_flags="-f /usr/local/etc/mdnsresponderposix.conf"
service mdnsresponderposix start
```

The configuration file lists one service per block: service name,
service type, and port, separated by newlines.

After this you can connect using:

```console
ssh freebsd@freebsd.local
```

## Benchmarking with iperf3

Install iperf3 inside the VM:

```console
su -
pkg install -y iperf3
iperf3 -s
```

Run iperf3 from the host in another terminal:

```console
iperf3 -c freebsd.local --time 30
iperf3 -c freebsd.local --time 30 -R
```

### Results

QEMU with HVF acceleration on MacBook Pro M2 Max:

| Direction      |          Bitrate | Retransmits |
|----------------|-----------------:|------------:|
| TX (host → VM) | 1.57 Gbits/sec   |           0 |
| RX (VM → host) | 3.61 Gbits/sec   |           0 |

> [!NOTE]
> QEMU networking performance is limited by the QEMU dgram
> implementation. For comparison, Linux VMs with QEMU on a MacBook
> Pro M2 Max achieve 2.34 Gbits/sec TX and 4.39 Gbits/sec RX. See
> the [performance guide] for details.

## Cleanup

> [!NOTE]
> Update 192.168.240.2 if you got another IP from the DHCP server.

```console
rm -r ~/vms/freebsd
ssh-keygen -R 192.168.240.2
ssh-keygen -R freebsd.local
```

[mDNSResponder]: https://www.freshports.org/net/mDNSResponder/
[nuageinit]: https://man.freebsd.org/cgi/man.cgi?query=nuageinit&sektion=7
[installing]: /README.md#installing
[mirrors]: https://docs.freebsd.org/en/books/handbook/mirrors/
[performance guide]: /docs/performance.md
