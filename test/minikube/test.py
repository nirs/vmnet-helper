#!/usr/bin/env python3
# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

"""
Minikube performance testing with iperf3
"""

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time

import matplotlib.pyplot as plt

log = logging.getLogger("test")

MINIKUBE = "minikube"
DRIVERS = ["krunkit", "vfkit"]
NETWORKS = ["host", "pod"]
WHERES = ["host", "vm"]
TESTS = ["tx", "rx", "bidir"]


def main():
    args = parse_args()
    setup_logging(args.output)
    args.func(args)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Minikube performance testing with iperf3",
    )
    sp = parser.add_subparsers(title="commands", dest="command", required=True)

    run_parser = sp.add_parser("run", help="Run performance tests")
    run_parser.set_defaults(func=do_run)
    run_parser.add_argument(
        "--minikube",
        default=MINIKUBE,
        help="path to minikube binary (default: minikube)",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        default="out",
        help="output directory (default: out)",
    )
    run_parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=60,
        help="iperf3 test duration in seconds (default: 60)",
    )
    run_parser.add_argument(
        "-d",
        "--drivers",
        nargs="+",
        default=DRIVERS,
        choices=DRIVERS,
        help="drivers to test (default: krunkit vfkit)",
    )
    run_parser.add_argument(
        "-n",
        "--networks",
        nargs="+",
        default=NETWORKS,
        choices=NETWORKS,
        help="network modes to test (default: host pod)",
    )
    run_parser.add_argument(
        "-w",
        "--where",
        nargs="+",
        default=WHERES,
        choices=WHERES,
        help="where to run iperf3 client (default: host vm)",
    )
    run_parser.add_argument(
        "--tests",
        nargs="+",
        default=TESTS,
        choices=TESTS,
        help="test types to run (default: tx rx bidir)",
    )

    analyze_parser = sp.add_parser(
        "analyze", help="Create plots and report from results"
    )
    analyze_parser.set_defaults(func=do_analyze)
    analyze_parser.add_argument(
        "-o",
        "--output",
        default="out",
        help="output directory (default: out)",
    )

    return parser.parse_args()


# --- run command ---


def do_run(args):
    global MINIKUBE
    MINIKUBE = args.minikube

    bench_dir = os.path.join(args.output, "bench")
    os.makedirs(bench_dir, exist_ok=True)

    for driver in args.drivers:
        log.info("Setup %s server", driver)
        setup_cluster(driver, "server")
        server = run(MINIKUBE, "ip", "--profile=server").strip()

        log.info("Setup %s client", driver)
        setup_cluster(driver, "client")

        for network in args.networks:
            log.info("Deploying %s", network)
            deploy(network, server)

            for where in args.where:
                for test in args.tests:
                    name = f"{driver}-{network}-{where}-{test}"
                    log.info("Testing %s...", name)
                    output = os.path.join(bench_dir, f"{name}.json")
                    run_test(output, server, args.timeout, network, where, test)

            log.info("Undeploying %s", network)
            undeploy(network)

        log.info("Cleanup %s", driver)
        cleanup()


# --- Cluster lifecycle ---


def setup_cluster(driver, profile):
    args = [
        "start",
        f"--driver={driver}",
        "--container-runtime=containerd",
        f"--profile={profile}",
    ]
    if driver == "vfkit":
        args.append("--network=vmnet-shared")
    minikube(*args)


def cleanup():
    minikube("delete", "--profile=server")
    minikube("delete", "--profile=client")


# --- Deploy / undeploy ---


def deploy(network, server):
    for context in ("server", "client"):
        kubectl(
            "apply",
            f"--context={context}",
            f"--kustomize=iperf3/{context}/{network}-network",
        )
    for context in ("server", "client"):
        kubectl(
            "rollout",
            "status",
            "deploy/iperf3",
            f"--context={context}",
            "--timeout=30s",
        )
    if network == "pod":
        wait_for_port(server, 30201)


def undeploy(network):
    # Start deletion on both clusters without waiting.
    for context in ("server", "client"):
        kubectl(
            "delete",
            f"--context={context}",
            "--ignore-not-found",
            f"--kustomize=iperf3/{context}/{network}-network",
            "--wait=false",
        )
    # Wait for both to complete.
    for context in ("server", "client"):
        kubectl(
            "delete",
            f"--context={context}",
            "--ignore-not-found",
            f"--kustomize=iperf3/{context}/{network}-network",
            "--timeout=30s",
        )


def wait_for_port(host, port, timeout=30):
    """Wait until a TCP port is accepting connections."""
    log.info("Waiting for %s:%s...", host, port)
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                log.info("%s:%s is ready", host, port)
                return
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timeout waiting for {host}:{port}")
            time.sleep(1)


# --- iperf3 tests ---


def run_test(output, server, timeout, network, where, test):
    """Run a single iperf3 test, writing JSON output to a file."""
    iperf_cmd = iperf3_command(server, timeout, network, test)

    if where == "vm":
        cmd = [
            "kubectl",
            "exec",
            "deploy/iperf3",
            "--context=client",
            "--",
            *iperf_cmd,
        ]
    else:
        cmd = iperf_cmd

    with open(output, "w") as f:
        subprocess.run(cmd, stdout=f, check=True)


OMIT_THRESHOLD = 10
OMIT_SECONDS = 5


def iperf3_command(server, timeout, network, test):
    """Build an iperf3 command."""
    args = ["iperf3", "-c", server, "--json", "-t", f"{timeout}"]
    if timeout >= OMIT_THRESHOLD:
        args.append(f"--omit={OMIT_SECONDS}")
    if network == "pod":
        args.append("--port=30201")
    if test == "rx":
        args.append("-R")
    elif test == "bidir":
        args.append("--bidir")
    return args


# --- analyze command ---


def do_analyze(args):
    bench_dir = os.path.join(args.output, "bench")
    plots_dir = os.path.join(args.output, "plots")

    results = load_results(bench_dir)
    if not results:
        sys.exit(f"No result files found in {bench_dir}")

    os.makedirs(plots_dir, exist_ok=True)

    networks = sorted({r["network"] for r in results})
    wheres = sorted({r["where"] for r in results})
    drivers = sorted({r["driver"] for r in results})

    plots = []

    for network in networks:
        for where in wheres:
            group = [
                r for r in results if r["network"] == network and r["where"] == where
            ]
            if not group:
                continue

            group_tests = sorted({r["test"] for r in group}, key=TESTS.index)
            fig, axes = plt.subplots(
                len(group_tests), 1, figsize=(8, 3 * len(group_tests)), squeeze=False
            )

            for i, test in enumerate(group_tests):
                ax = axes[i, 0]
                for driver in drivers:
                    matches = [
                        r for r in group if r["driver"] == driver and r["test"] == test
                    ]
                    if not matches:
                        continue
                    r = matches[0]
                    if test == "bidir":
                        plot_bidir(ax, r, driver)
                    else:
                        plot_single(ax, r, driver)

                ax.set_title(f"{test}")
                ax.set_ylabel("Gbits/s")
                ax.set_ylim(bottom=0)
                ax.set_xlim(left=0)
                ax.grid(True, alpha=0.3)
                ax.legend()

            axes[-1, 0].set_xlabel("Time (s)")
            fig.suptitle(
                f"{network} network - iperf3 on {where}",
                fontsize=12,
                fontweight="bold",
            )
            fig.tight_layout()

            filename = f"{network}-{where}.png"
            path = os.path.join(plots_dir, filename)
            fig.savefig(path)
            plt.close(fig)
            log.info("Created %s", path)
            plots.append({"network": network, "where": where, "filename": filename})

    write_report(args.output, plots)


def load_results(bench_dir):
    """Load all result JSON files from bench directory."""
    results = []
    for driver in DRIVERS:
        for network in NETWORKS:
            for where in WHERES:
                for test in TESTS:
                    path = os.path.join(
                        bench_dir, f"{driver}-{network}-{where}-{test}.json"
                    )
                    if not os.path.exists(path):
                        continue
                    with open(path) as f:
                        data = json.load(f)
                    results.append(
                        {
                            "driver": driver,
                            "network": network,
                            "where": where,
                            "test": test,
                            "data": data,
                        }
                    )
    return results


def measured_intervals(data):
    """Return intervals that are not omitted or partial."""
    return [
        iv
        for iv in data["intervals"]
        if not iv["sum"]["omitted"] and iv["sum"]["end"] > iv["sum"]["start"]
    ]


def plot_times(intervals):
    """Return normalized times starting from 0."""
    t0 = intervals[0]["sum"]["start"]
    return [iv["sum"]["end"] - t0 for iv in intervals]


def plot_single(ax, result, driver):
    """Plot a single-direction iperf3 test (tx or rx)."""
    intervals = measured_intervals(result["data"])
    times = plot_times(intervals)
    bitrates = [iv["sum"]["bits_per_second"] / 1e9 for iv in intervals]
    ax.plot(times, bitrates, label=driver)


def plot_bidir(ax, result, driver):
    """Plot a bidirectional iperf3 test (sender + receiver)."""
    intervals = measured_intervals(result["data"])
    times = plot_times(intervals)
    tx_bitrates = [iv["sum"]["bits_per_second"] / 1e9 for iv in intervals]
    rx_bitrates = [iv["sum_bidir_reverse"]["bits_per_second"] / 1e9 for iv in intervals]
    ax.plot(times, tx_bitrates, label=f"{driver} tx")
    ax.plot(times, rx_bitrates, label=f"{driver} rx", linestyle="--")


DESCRIPTIONS = {
    ("host", "host"): (
        "Host network with iperf3 client running on the host. "
        "Measures network performance between the host and the VM "
        "using the host network (no pod network overhead)."
    ),
    ("host", "vm"): (
        "Host network with iperf3 client running inside the client VM. "
        "Measures VM-to-VM network performance using the host network."
    ),
    ("pod", "host"): (
        "Pod network with iperf3 client running on the host. "
        "Measures network performance between the host and the VM "
        "through the Kubernetes pod network and NodePort service."
    ),
    ("pod", "vm"): (
        "Pod network with iperf3 client running inside the client VM. "
        "Measures VM-to-VM network performance through the Kubernetes "
        "pod network and NodePort service."
    ),
}


def write_report(output_dir, plots):
    """Generate a markdown report with embedded plots."""
    path = os.path.join(output_dir, "report.md")
    with open(path, "w") as f:
        f.write("# Minikube Performance Test Results\n\n")
        for p in plots:
            network, where = p["network"], p["where"]
            f.write(f"## {network} network - iperf3 on {where}\n\n")
            desc = DESCRIPTIONS.get((network, where), "")
            if desc:
                f.write(f"{desc}\n\n")
            f.write(f"![{network}-{where}](plots/{p['filename']})\n\n")
    log.info("Created %s", path)


# --- Command helpers ---


def setup_logging(output_dir):
    log.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(console)

    os.makedirs(output_dir, exist_ok=True)
    logfile = logging.FileHandler(os.path.join(output_dir, "test.log"), mode="a")
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    log.addHandler(logfile)


def minikube(*args):
    run(MINIKUBE, *args)


def kubectl(*args):
    run("kubectl", *args)


def run(*args):
    """Run a command, log it and its output, and return decoded stdout."""
    log.debug("Running: %s", " ".join(args))
    result = subprocess.run(args, capture_output=True, text=True)
    log.debug("  exitcode: %s", result.returncode)
    if result.stdout:
        log.debug("  stdout:")
        for line in result.stdout.splitlines():
            log.debug("    %s", line)
    if result.stderr and result.returncode == 0:
        log.debug("  stderr:")
        for line in result.stderr.splitlines():
            log.debug("    %s", line)
    if result.returncode != 0:
        error = result.stderr.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{' '.join(args)}: {error}")
    return result.stdout


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception:
        log.exception("Test failed")
        sys.exit(1)
