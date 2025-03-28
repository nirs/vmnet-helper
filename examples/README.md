# Examples

This directory contains examples for using *vmnet-helper* and
*vmnet-client*:

- [qemu.sh](#qemu.sh)

> [!TIP]
> Log in as user `ubuntu` with password `password`

## qemu.sh

This example shows how to start a *QEMU* virtual machine connected to a vmnet
network interface using the vmnet-client wrapper.

To start the example virtual machine run:

```bash
./qemu.sh
```

The example downloads an Ubuntu server cloud image, creates a cloud-init
iso image, and starts a *QEMU* virtual machine with both images.

## Helper scripts

- `download.sh`: downloads an Ubuntu server cloud image and convert it
  to raw format.
- `create-iso.sh`: creates cloud-init iso image.
