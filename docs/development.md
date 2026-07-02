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

## Static IP addressing

When using `./run` to start virtual machines on a network without DHCP, you
should assign a static IP address to your guests. This should be used:
- In any mode, if the virtual machine should not use DHCP
- When setting `--network-id`, which disables DHCP on the entire network

### Without `--network-id`

On most networks, the DHCP range can be constrained using `--start-address`,
`--end-address` and `--subnet-mask`. Addresses outside this range are still
routable as long as they belong to the same subnet. A static IP can be set with
`--guest-ip-address`:

```console
./run vm3 \
    --start-address 192.168.12.1 \
    --end-address 192.168.12.128 \
    --subnet-mask 255.255.255.0 \
    --guest-ip-address 192.168.12.129
```

### With `--network-id`

When `--network-id` is set, you *must* request a static IP address using the
`--guest-ip-address` option.

```console
NETWORK_ID=D637004F-D2FC-4C44-940A-12FB093D92F1
./run vm1 --operation-mode host --network-id $NETWORK_ID --guest-ip-address 192.168.55.12
```

This is the simplest approach, and results in:
- A subnet mask of 255.255.255.0 (/24)
- The guest is assigned the requested address
- The host is assigned the first address in the guest address subnet
  (192.168.55.1)

`vmnet` will reject the assignment if the subnet is already in use by a
network in a different mode, or in host mode with a different `--network-id`.
It is your responsibility to ensure the subnet and addresses are available.

The following options are available for more control:
- `--host-subnet-mask` is the `vmnet-helper` option to set the subnet mask
  when a network ID is set. Defaults to 255.255.255.0.
- `--host-ip-address` is the `vmnet-helper` option to set the host's IP
  address when a network ID is set. When used with `./run`, defaults to the
  first address in the `--guest-ip-address` subnet.

```console
NETWORK_ID=D637004F-D2FC-4C44-940A-12FB093D92F1
./run vm2 \
    --operation-mode host \
    --network-id $NETWORK_ID \
    --host-ip-address 192.168.55.10 \
    --host-subnet-mask 255.255.255.240 \
    --guest-ip-address 192.168.55.11
```
