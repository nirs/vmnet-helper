<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Examples

The example tool shows how to integrate vmnet-helper with *vfkit* or
*qemu*.

To install the requirements for creating virtual machine using *vfkit*
*krunkit*, and *qemu* run:

```console
brew tap slp/krunkit
brew install python3 vfkit krunkit qemu cdrtools
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml
```

To start a virtual machine using *vfkit* run:

```console
% ./example vm
Starting vmnet-helper for 'vm' with interface id '391ea262-d812-45b9-9526-e0ab5aeff7a2'
Downloading image 'https://cloud-images.ubuntu.com/releases/24.10/release/ubuntu-24.10-server-cloudimg-arm64.img'
Converting image to raw format '/Users/nir/.vmnet-helper/cache/images/fe0930aca80e74ef9bcdc6e883fd6d716f490f765c8848d90f1d9c9cf69c43b2/disk.img'
Resizing image to 20g
Creating disk '/Users/nir/.vmnet-helper/vms/vm/disk.img'
Creating cloud-init iso '/Users/nir/.vmnet-helper/vms/vm/cidata.iso'
Starting 'vfkit' virtual machine 'vm' with mac address 'a2:89:b2:31:d7:fb'
Virtual machine IP address:  192.168.105.2
```

To stop the virtual machine and the vmnet-helper press *Control+C*.

## SSH configuration

To configure ssh for the test vms add this to your `.ssh/config`:

```
Include ~/.vmnet-helper/vms/*/ssh.config
```

With this configuration you can login to the example vm with:

```console
ssh vm
```
