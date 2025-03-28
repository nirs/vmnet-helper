# Examples

This directory contains examples for using vmnet-helper and
vmnet-client:

- [qemu.sh](#qemu.sh)

> [!TIP]
> Log in as `ubuntu` with password `password`

## qemu.sh

This example shows how to start QEMU VM connected to vment network
interface using the vmnet-client wrapper.

To start the example VM run:

```bash
./qemu.sh
```

The example downloads an Ubuntu server cloud image, creates a cloud-init
iso image for configuring the VM, and starts QEMU vm.

## Helper scripts

- `download.sh`: downloads an Ubuntu server cloud image and convert it
  to raw format.
- `create-iso.sh`: creates cloud-init iso image.
