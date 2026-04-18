<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Examples

The example tool shows how to integrate vmnet-helper with *vfkit* or
*qemu*. See the [integration guide](/docs/integration.md) for all
available options.

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
[   0.038] INFO Starting vmnet-helper for 'vm' with interface id '391ea262-d812-45b9-9526-e0ab5aeff7a2'
[   0.058] INFO Downloading image 'https://cloud-images.ubuntu.com/releases/25.04/release/ubuntu-25.04-server-cloudimg-arm64.img'
[  19.384] INFO Converting image to 'raw' format '/Users/nir/.vmnet-helper/cache/images/7fef961f75d830af5d20db6da02bff7e33ce662a49bd4b433ed8f35a9f6a18c0/data'
[  21.558] INFO Resizing image to 20g
[  21.585] INFO Creating image '/Users/nir/.vmnet-helper/vms/vm/disk.img'
[  21.591] INFO Creating cloud-init iso '/Users/nir/.vmnet-helper/vms/vm/cidata.iso'
[  21.597] INFO Starting 'vfkit' virtual machine 'vm' with mac address 'a2:89:b2:31:d7:fb'
[  21.598] INFO Creating ssh config '/Users/nir/.vmnet-helper/vms/vm/ssh.config'
[  36.842] INFO VM is ready at vm-vmnet-helper.local
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
