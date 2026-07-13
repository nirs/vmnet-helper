<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# Development

## Setup

```console
brew install meson qemu
python3 -m venv .venv
source .venv/bin/activate
pip install pytest scapy pyyaml black matplotlib
```

## Building

```console
./build.sh build
```

This creates a universal binary (arm64 + x86_64) at `build/vmnet-helper.tar.gz`.

## Installing

To install from a locally built tarball:

```console
./install.sh build/vmnet-helper.tar.gz
```

## Tests

To run the tests, activate the virtual environment first:

```console
source .venv/bin/activate
pytest -v
```

## Formatting

```console
./fmt.sh
```

## Benchmarking

Activate the virtual environment first:

```console
source .venv/bin/activate
```

Create VMs for benchmarking (see [examples](/docs/examples.md) for
details on the run tool):

```console
./bench create
```

To run all benchmarks with all drivers and all operation modes and store
iperf3 results in json format use:

```console
./bench run performance/benchmarks/full.yaml
```

The benchmark results are stored under `out/bench/vmnet-helper`.

See the [benchmarks](/benchmarks) directory for additional configurations.

When done you can delete the vms using:

```console
./bench delete
```

### Creating plots

To create plots from benchmark results run:

```console
./bench plot -o out performance/plots/drivers.yaml
```

The plots use the results stored under `out/bench` and created under
`out/plot`.

See the [plots](/plots) directory for additional configurations.

### socket_vmnet

Running socket_vmnet as launchd service, creating virtual machines with
lima 1.0.6.

Tests run using socket_vmnet `test/perf.sh` script:

```console
test/perf.sh create
test/perf.sh run
```

To include socket_vmnet results in the plots copy the test results to
the output directory:

```console
cp ~/src/socket_vmnet/test/perf.out/socket_vmnet out/bench/
```

## `run`: start a virtual machine for testing

The `run` script starts vmnet-helper and a Linux virtual machine. It allows
for quick integration testing with various distributions and helper options.
All helper options are supported. By default, the script starts a Ubuntu 26.04
VM on a shared network. To see all options, use `./run -h`.

```console
% ./run test
[   0.035] INFO Starting vmnet-helper for 'test' with interface id '83fa1a6e-13ec-408f-ae44-2c26bc31
7160'
[   0.115] INFO Creating image '/Users/user/.vmnet-helper/vms/test/disk.img'
[   0.121] INFO Creating cloud-init iso '/Users/user/.vmnet-helper/vms/test/cidata.iso'
[   0.128] INFO Starting 'vfkit' virtual machine 'test' with mac address '1a:ad:75:f7:ca:a2'
[   0.128] INFO Creating ssh config '/Users/user/.vmnet-helper/vms/test/ssh.config'
[  17.123] INFO VM is ready at test-vmnet-helper.local
```

Virtual machine resources can be customized. The following example sets 4 vcpus
and 4 GiB of memory:

```console
% ./run test --cpus 4 --memory 4096
```

By default, `run` uses vfkit, connected to the helper using a file descriptor.
The following example uses the qemu driver, and connects using vmnet-run:

```console
% ./run test --driver qemu --connection runner
[   0.031] INFO Starting 'qemu' virtual machine 'test' with mac address '9a:a9:fe:3c:db:46'
[  16.630] INFO VM is ready at test-vmnet-helper.local
```

### Storage and debugging

The script downloads cloud images to `~/.vmnet-helper/cache/images`, converts
them to RAW, and uses APFS reflinks to provision individual VM images. Each
VM has a directory under `~/.vmnet-helper/vms` for storage, configuration, and
logs.

For a given VM `$VM` and driver `$DRIVER`, the following logs are available
for debugging relative to the VM storage directory `~/.vmnet-helper/$VM`:
- `serial.log`: the output of the VM's serial console
- `$DRIVER.command`: the driver command used to start the VM
- `$DRIVER.log`: any logs from the hypervisor driver
- `vmnet-helper.log`: logs from `vmnet-helper` itself

```console
% tree ~/.vmnet-helper/vms/test
/Users/tofugarden/.vmnet-helper/vms/test
├── cidata.iso
├── disk.img
├── efi-variable-store
├── meta-data
├── network-config
├── serial.log
├── ssh.config
├── user-data
├── vfkit.command
├── vfkit.log
└── vmnet-helper.log
```

### Limitations

The `qemu` driver is not compatible with `--connection` set to `socket`.

Multicast DNS setup requires network access. To use mDNS with
`--operation-mode` set to `host`, create the VM in shared mode, then restart it
in host mode.
