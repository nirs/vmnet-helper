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

Create vms for benchmarking:

```console
./bench create
```

To run all benchmarks with all drivers and all operation modes and store
iperf3 results in json format use:

```console
./bench run benchmarks/full.yaml
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
./bench plot -o out plots/drivers.yaml
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
