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
> - If you have krunkit installed from the old `slp/krunkit` or `slp/krun`
>   brew tap, you need to [remove it first][old-tap].

```console
brew tap nirs/vmnet-helper
brew trust nirs/vmnet-helper
brew tap libkrun/krun
brew trust libkrun/krun
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
write_files:
  - path: /etc/systemd/system/qemu-guest-agent.service
    content: |
      [Unit]
      Description=QEMU Guest Agent
      [Service]
      ExecStart=/usr/bin/qemu-ga --method=vsock-listen --path=3:1234
      Restart=always
      RestartSec=0
      [Install]
      WantedBy=multi-user.target
  - path: /root/qemu-ga-vsock.cil
    content: |
      (allow virt_qemu_ga_t self (vsock_socket (bind create getattr listen accept read write)))
runcmd:
  - semodule -i /root/qemu-ga-vsock.cil
  - systemctl daemon-reload
  - systemctl disable qemu-guest-agent
  - systemctl enable --now qemu-guest-agent
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
    <string>$VM_NAME.local</string>
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
        <string>--timesync</string>
        <string>vsockPort=1234</string>
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
launchctl start podman-vfkit.local
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
launchctl stop podman-vfkit.local
until launchctl print gui/$(id -u)/podman-vfkit.local | grep -q 'state = not running'; do sleep 1; done
launchctl start podman-vfkit.local
until nc -z podman-vfkit.local 22; do true; done
```

### Add a system connection

```console
podman system connection add podman-vfkit.local \
    --identity ~/.ssh/id_ed25519 \
    ssh://root@podman-vfkit.local/run/podman/podman.sock
```

### Fixing SELinux

Check the connection:

```console
podman -c podman-vfkit.local version
```

Example output:

```
Client:        Podman Engine
Version:       6.1.0
API Version:   6.1.0
Go Version:    go1.26.5
Built:         Wed Aug 12 20:04:26 2026
Build Origin:  brew
OS/Arch:       darwin/arm64
Cannot connect to Podman. Please verify your connection to the Linux system
using `podman system connection list`, or try `podman machine init` and
`podman machine start` to manage a new Linux VM
Error: unable to connect to Podman socket: Get "http://d/v6.1.0/libpod/_ping":
ssh: rejected: connect failed (open failed)
```

SELinux is blocking SSH from the podman socket. Confirm:

```console
ssh root@podman-vfkit.local bash -ls << 'EOF'
ausearch -if /var/log/audit/audit.log -m avc -c sshd-session
EOF
```

Example output:

```
----
time->Mon Aug 31 16:39:39 2026
type=AVC msg=audit(1788194379.948:128): avc:  denied  { write } for  pid=873 comm="sshd-session" name="podman.sock" dev="tmpfs" ino=1473 scontext=system_u:system_r:sshd_session_t:s0-s0:c0.c1023 tcontext=system_u:object_r:var_run_t:s0 tclass=sock_file permissive=0
```

Allow the access:

```console
ssh root@podman-vfkit.local 'cat > /root/sshd-podman-sock.cil && semodule -i /root/sshd-podman-sock.cil' << 'EOF'
(allow sshd_session_t var_run_t (sock_file (write)))
(allow sshd_session_t container_runtime_t (unix_stream_socket (connectto)))
EOF
```

Check the connection again:

```console
podman -c podman-vfkit.local version
```

### Cleanup

To remove the VM after you are done testing:

```console
podman system connection remove podman-vfkit.local
launchctl stop podman-vfkit.local
launchctl bootout gui/$(id -u)/podman-vfkit.local
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
write_files:
  - path: /etc/systemd/system/qemu-guest-agent.service
    content: |
      [Unit]
      Description=QEMU Guest Agent

      [Service]
      ExecStart=/usr/bin/qemu-ga --method=vsock-listen --path=3:1234
      Restart=always
      RestartSec=0

      [Install]
      WantedBy=multi-user.target
  - path: /root/qemu-ga-vsock.cil
    content: |
      (allow virt_qemu_ga_t self (vsock_socket (bind create getattr listen accept read write)))
runcmd:
  - semodule -i /root/qemu-ga-vsock.cil
  - systemctl daemon-reload
  - systemctl disable qemu-guest-agent
  - systemctl enable --now qemu-guest-agent
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
    <string>$VM_NAME.local</string>
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
        <string>--timesync</string>
        <string>vsockPort=1234</string>
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
launchctl start podman-krunkit.local
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
launchctl stop podman-krunkit.local
until launchctl print gui/$(id -u)/podman-krunkit.local | grep -q 'state = not running'; do sleep 1; done
launchctl start podman-krunkit.local
until nc -z podman-krunkit.local 22; do true; done
```

### Add a system connection

```console
podman system connection add podman-krunkit.local \
    --identity ~/.ssh/id_ed25519 \
    ssh://root@podman-krunkit.local/run/podman/podman.sock
```

### Fixing SELinux

Check the connection:

```console
podman -c podman-krunkit.local version
```

Example output:

```
Client:        Podman Engine
Version:       6.1.0
API Version:   6.1.0
Go Version:    go1.26.5
Built:         Wed Aug 12 20:04:26 2026
Build Origin:  brew
OS/Arch:       darwin/arm64
Cannot connect to Podman. Please verify your connection to the Linux system
using `podman system connection list`, or try `podman machine init` and
`podman machine start` to manage a new Linux VM
Error: unable to connect to Podman socket: Get "http://d/v6.1.0/libpod/_ping":
ssh: rejected: connect failed (open failed)
```

SELinux is blocking SSH from the podman socket. Confirm:

```console
ssh root@podman-krunkit.local bash -ls << 'EOF'
ausearch -if /var/log/audit/audit.log -m avc -c sshd-session
EOF
```

Example output:

```
----
time->Mon Aug 31 16:39:39 2026
type=AVC msg=audit(1788194379.948:128): avc:  denied  { write } for  pid=873 comm="sshd-session" name="podman.sock" dev="tmpfs" ino=1473 scontext=system_u:system_r:sshd_session_t:s0-s0:c0.c1023 tcontext=system_u:object_r:var_run_t:s0 tclass=sock_file permissive=0
```

Allow the access:

```console
ssh root@podman-krunkit.local 'cat > /root/sshd-podman-sock.cil && semodule -i /root/sshd-podman-sock.cil' << 'EOF'
(allow sshd_session_t var_run_t (sock_file (write)))
(allow sshd_session_t container_runtime_t (unix_stream_socket (connectto)))
EOF
```

Check the connection again:

```console
podman -c podman-krunkit.local version
```

### Cleanup

To remove the VM after you are done testing:

```console
podman system connection remove podman-krunkit.local
launchctl stop podman-krunkit.local
launchctl bootout gui/$(id -u)/podman-krunkit.local
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
for machine in podman-applehv podman-libkrun; do
    CONTAINERS_MACHINE_PROVIDER=${machine#podman-} podman machine init --rootful $machine
done
```

We test rootful podman with port forwarding. Traffic goes through the
gvproxy userspace network stack.

```console
for machine in podman-applehv podman-libkrun; do
    CONTAINERS_MACHINE_PROVIDER=${machine#podman-} podman machine start $machine

    podman -c $machine-root run -d --name iperf3 -p 5201:5201 docker.io/networkstatic/iperf3 -s
    iperf3 -c localhost --json --time 30 > out/$machine-root-tx.json
    iperf3 -c localhost --json --time 30 --reverse > out/$machine-root-rx.json
    podman -c $machine-root rm -f iperf3

    CONTAINERS_MACHINE_PROVIDER=${machine#podman-} podman machine stop $machine
done
```

### vmnet — port forwarding

We use rootful podman with port forwarding, implemented by the kernel using
nftables.

```console
for vm in podman-vfkit.local podman-krunkit.local; do
    launchctl start $vm
    until nc -z $vm 22; do true; done

    podman -c $vm run -d --name iperf3 -p 5201:5201 docker.io/networkstatic/iperf3 -s
    iperf3 -c $vm --json --time 30 > out/$vm-port-forwarding-tx.json
    iperf3 -c $vm --json --time 30 --reverse > out/$vm-port-forwarding-rx.json
    podman -c $vm rm -f iperf3

    launchctl stop $vm
    until launchctl print gui/$(id -u)/$vm | grep -q 'state = not running'; do sleep 1; done
done
```

### vmnet — host network

The container uses the host network directly, avoiding the port forwarding cost.
If your service can bind to any port, this is the fastest option.

```console
for vm in podman-vfkit.local podman-krunkit.local; do
    launchctl start $vm
    until nc -z $vm 22; do true; done

    podman -c $vm run -d --name iperf3 --network host docker.io/networkstatic/iperf3 -s
    iperf3 -c $vm --json --time 30 > out/$vm-host-network-tx.json
    iperf3 -c $vm --json --time 30 --reverse > out/$vm-host-network-rx.json
    podman -c $vm rm -f iperf3

    launchctl stop $vm
    until launchctl print gui/$(id -u)/$vm | grep -q 'state = not running'; do sleep 1; done
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
podman system connection default podman-krunkit.local
```

## Managing the VM

Start the VM:

```console
launchctl start podman-krunkit.local
```

Stop the VM:

```console
launchctl stop podman-krunkit.local
```

[xkcd]: https://xkcd.com/353/
[cc-by-nc]: https://creativecommons.org/licenses/by-nc/2.5/
[old-tap]: https://github.com/libkrun/krunkit#removing-the-old-homebrew-tap
[vfkit]: https://github.com/crc-org/vfkit
[krunkit]: https://github.com/libkrun/krunkit
[libkrun]: https://github.com/libkrun/libkrun
[ramalama]: https://github.com/containers/ramalama
[offloading]: /docs/performance.md#offloading
[installing]: /README.md#installing
[launchd guide]: /docs/launchd.md
