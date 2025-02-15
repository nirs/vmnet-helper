#!/usr/bin/env python3

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

"""
Generate plots from iperf3 json output.

Requirments:

    brew install python-matplotlib

Assumes this directory layout:

    bench.out/
        vmnet-helper/
            {mode}-{driver}-{vms}/
                {test}.json
        socket_vmnet/
            {mode}-{driver}-{vms}/
                {test}.json

"""

import argparse
import json
import os
import glob

import matplotlib.pyplot as plt

import vmnet

p = argparse.ArgumentParser()
p.add_argument(
    "-m",
    "--operation-mode",
    choices=vmnet.OPERATION_MODES,
    default=vmnet.OPERATION_MODES[0],
    help=f"Operation mode ({vmnet.OPERATION_MODES[0]})",
)
p.add_argument(
    "-t",
    "--test",
    choices=["host-to-vm", "vm-to-host", "vm-to-vm"],
    default="host-to-vm",
    help="Test scenario (host-to-vm)",
)
p.add_argument("-o", "--output", help="Benchmark results directory")
args = p.parse_args()

configs = []
bitrate = []

# out/network/mode-driver-vms/test.json
results = glob.glob(f"{args.output}/*/{args.operation_mode}-*-*/{args.test}.json")

for filename in reversed(sorted(results)):
    # Build config name from the test path, excluding the mode and test, since
    # we create a graph for mode and test name.
    _, network, config, test_json = filename.rsplit(os.sep, 3)
    _, driver, vms = config.split("-")
    test, _ = os.path.splitext(test_json)
    configs.append(f"{network}/{driver}-{vms}")

    # Add the bitrate for this test.
    with open(filename) as f:
        data = json.load(f)
    gbits_per_second = data["end"]["sum_received"]["bits_per_second"] / 1000**3
    bitrate.append(gbits_per_second)

plt.style.use(["web.mplstyle"])

fig, ax = plt.subplots(layout="constrained")

ax.barh(configs, bitrate, zorder=2)

for i in range(len(configs)):
    v = round(bitrate[i], 1)
    label = f"{v:.1f}  "
    plt.text(
        bitrate[i],
        i,
        label,
        va="center",
        ha="right",
        color="white",
        fontsize=8,
        zorder=3,
    )

ax.grid(visible=True, axis="x", zorder=0)

ax.set(
    xlabel="Bitrate Gbits/s",
    ylabel="Configurations",
    title=f"{args.operation_mode} - {args.test}",
)

path = os.path.join(args.output, f"{args.operation_mode}-{args.test}.png")
fig.savefig(path, bbox_inches="tight")
