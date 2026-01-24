# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# pyright: basic, reportOperatorIssue=false, reportOptionalSubscript=false
# pyright: reportOptionalMemberAccess=false

"""
Tests for vmnet-helper using scapy for network verification.

These tests start vmnet-helper and use scapy to verify network connectivity
without requiring a virtual machine. This makes tests fast and suitable for CI
on any macOS version and architecture.

Requirements:
- vmnet-helper installed at /opt/vmnet-helper
- scapy package installed
- sudo configured for passwordless vmnet-helper (for privileged mode)

Tests run in two modes:
- privileged: Uses sudo, skipped if /etc/sudoers.d/vmnet-helper not installed
- unprivileged: Direct execution, skipped on macOS < 26
"""

import contextlib
import ipaddress
import logging
import os
import socket
import time
from types import SimpleNamespace

import pytest
from scapy.all import ARP, ICMP, IP, Ether  # type: ignore[import-untyped]

from . import helper
from .helper import (
    NET_IPV4_MASK,
    NET_IPV4_SUBNET,
    NET_IPV6_PREFIX,
    NET_IPV6_PREFIX_LEN,
    VMNET_END_ADDRESS,
    VMNET_MAC_ADDRESS,
    VMNET_MAX_PACKET_SIZE,
    VMNET_START_ADDRESS,
    VMNET_SUBNET_MASK,
)


# ARP operation codes (RFC 826)
# https://www.iana.org/assignments/arp-parameters/arp-parameters.xhtml
ARP_REQUEST = 1
ARP_REPLY = 2

# ICMP types (RFC 792)
# https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0

log = logging.getLogger("test")

# --- Tests ---


class TestStart:
    """
    Test that vmnet-helper starts correctly with various options
    """

    def test_default_mode(self):
        """
        Test starting helper without mode default to "shared".
        """
        with run_helper() as (h, sock):
            self.check_interface(h.interface)

    def test_shared_mode(self):
        """
        Test starting helper with shared mode
        """
        with run_helper(operation_mode="shared") as (h, sock):
            self.check_interface(h.interface)

    def test_shared_mode_custom_subnet(self):
        """
        Test starting helper with custom subnet configuration
        """
        with run_helper(
            operation_mode="shared",
            start_address="192.168.200.1",
            end_address="192.168.200.254",
            subnet_mask="255.255.255.0",
        ) as (h, sock):
            self.check_interface(h.interface)
            assert h.interface[VMNET_START_ADDRESS] == "192.168.200.1"
            assert h.interface[VMNET_END_ADDRESS] == "192.168.200.254"
            assert h.interface[VMNET_SUBNET_MASK] == "255.255.255.0"

    def test_host_mode(self):
        """
        Test starting helper in host mode
        """
        with run_helper(
            operation_mode="host",
        ) as (h, sock):
            self.check_interface(h.interface)

    def test_host_mode_isolated(self):
        """
        Test starting helper in host mode with isolation
        """
        with run_helper(
            operation_mode="host",
            enable_isolation=True,
        ) as (h, sock):
            self.check_interface(h.interface)

    def check_interface(self, interface):
        assert VMNET_MAC_ADDRESS in interface
        assert VMNET_START_ADDRESS in interface
        assert VMNET_END_ADDRESS in interface
        assert VMNET_SUBNET_MASK in interface
        assert VMNET_MAX_PACKET_SIZE in interface


class TestConnectivity:
    """
    Test network connectivity using scapy
    """

    def test_arp_gateway(self):
        """
        Test ARP resolution to gateway
        """
        with run_helper(operation_mode="shared") as (h, sock):
            gateway_mac = arp_resolve(h, sock)
            assert gateway_mac is not None

    def test_ping_gateway(self):
        """
        Test ICMP ping to gateway
        """
        with run_helper(operation_mode="shared") as (h, sock):
            gateway_mac = arp_resolve(h, sock)
            gateway_ip = find_gateway_ip(h.interface)
            ping(h, sock, gateway_mac, gateway_ip)

    def test_ping_external_via_nat(self):
        """
        Test ICMP ping to external IP via NAT
        """
        external_ips = ["1.1.1.1", "8.8.8.8"]
        with run_helper(operation_mode="shared") as (h, sock):
            gateway_mac = arp_resolve(h, sock)
            retry(ping_any, h, sock, gateway_mac, external_ips)


# --- Helper runner ---


@contextlib.contextmanager
def run_helper(
    vm_name="test",
    operation_mode=None,
    start_address=None,
    end_address=None,
    subnet_mask=None,
    shared_interface=None,
    network_name=None,
    enable_isolation=False,
    enable_offloading=False,
    verbose=True,
    privileged=helper.requires_root(),
):
    """
    Context manager to run vmnet-helper with a socketpair.

    Yields (helper, sock) tuple where:
    - helper: Started Helper instance with interface info
    - sock: Host-side socket for sending/receiving packets

    Example:
        with run_helper(operation_mode="shared") as (h, sock):
            assert VMNET_MAC_ADDRESS in h.interface
            sock.send(packet)
    """
    args = SimpleNamespace(
        vm_name=vm_name,
        operation_mode=operation_mode,
        start_address=start_address,
        end_address=end_address,
        subnet_mask=subnet_mask,
        shared_interface=shared_interface,
        network_name=network_name,
        enable_isolation=enable_isolation,
        enable_offloading=enable_offloading,
        verbose=verbose,
        privileged=privileged,
    )

    host_sock, vm_sock = helper.socketpair()
    try:
        h = helper.Helper(args, fd=vm_sock.fileno())
        h.start()
        assert h.interface is not None  # Set by start()
        try:
            yield h, host_sock
        finally:
            h.stop()
    finally:
        host_sock.close()
        vm_sock.close()


# --- Network functions ---


def arp_resolve(h, sock, timeout=1.0):
    """
    Send ARP request to gateway and return gateway MAC address.
    """
    gateway_ip = find_gateway_ip(h.interface)
    my_mac = h.interface[VMNET_MAC_ADDRESS]
    packet_size = h.interface[VMNET_MAX_PACKET_SIZE]
    my_ip = find_my_ip(h.interface)

    request = Ether(dst="ff:ff:ff:ff:ff:ff", src=my_mac) / ARP(
        op=ARP_REQUEST, hwsrc=my_mac, psrc=my_ip, pdst=gateway_ip
    )
    sock.send(bytes(request))
    log.info("Sent ARP request to %s", gateway_ip)

    # Wait for ARP reply, filtering out broadcast traffic.
    start = time.monotonic()
    deadline = start + timeout
    sock.settimeout(timeout)
    while time.monotonic() < deadline:
        try:
            response = sock.recv(packet_size)
        except socket.timeout:
            continue
        reply = Ether(response)
        if (
            reply.haslayer(ARP)
            and reply[ARP].op == ARP_REPLY
            and reply[ARP].psrc == gateway_ip
        ):
            elapsed = time.monotonic() - start
            log.info("Got ARP reply in %.6f seconds", elapsed)
            return reply[ARP].hwsrc

    raise AssertionError(f"No ARP reply from {gateway_ip}")


def ping(h, sock, gateway_mac, target_ip, timeout=1.0):
    """
    Send ICMP echo request and wait for reply.
    """
    gateway_ip = find_gateway_ip(h.interface)
    my_mac = h.interface[VMNET_MAC_ADDRESS]
    packet_size = h.interface[VMNET_MAX_PACKET_SIZE]
    my_ip = find_my_ip(h.interface)

    request = (
        Ether(dst=gateway_mac, src=my_mac)
        / IP(src=my_ip, dst=target_ip)
        / ICMP(type=ICMP_ECHO_REQUEST)
    )
    sock.send(bytes(request))
    log.info("Sent ICMP echo request to %s", target_ip)

    # Wait for ICMP reply, filtering out broadcast traffic.
    start = time.monotonic()
    deadline = start + timeout
    sock.settimeout(timeout)
    while time.monotonic() < deadline:
        try:
            response = sock.recv(packet_size)
        except socket.timeout:
            continue
        pkt = Ether(response)
        if pkt.haslayer(ICMP) and pkt[ICMP].type == ICMP_ECHO_REPLY:
            assert pkt[IP].src == target_ip, f"Expected reply from {target_ip}"
            elapsed = time.monotonic() - start
            log.info("Got ICMP reply in %.6f seconds", elapsed)
            return

    raise AssertionError(f"No ICMP echo reply from {target_ip}")


def ping_any(h, sock, gateway_mac, ips):
    """
    Try to ping any of the IPs, raise if all fail
    """
    for ip in ips:
        try:
            ping(h, sock, gateway_mac, ip)
            return
        except AssertionError:
            log.info("Failed to ping %s, trying next", ip)

    raise AssertionError(f"No reply from any of {ips}")


# --- Utilities ---


def find_gateway_ip(interface):
    """
    Return gateway IP, supporting both modes.
    """
    for key in (VMNET_START_ADDRESS, NET_IPV4_SUBNET):
        if key in interface:
            return interface[key]

    raise AssertionError("No gateway address in interface")


def find_my_ip(interface):
    """
    Return usable IP for this client, supporting both modes.

    NOTE: works in CI when the network is empty, may not work locally if the
    address is used by a VM, but this is very unlikely.
    """
    if VMNET_END_ADDRESS in interface:
        return interface[VMNET_END_ADDRESS]
    # --network mode: calculate from subnet and mask
    subnet = interface[NET_IPV4_SUBNET]
    mask = interface[NET_IPV4_MASK]
    network = ipaddress.IPv4Network(f"{subnet}/{mask}", strict=False)
    return str(network.broadcast_address - 1)


def retry(func, *args, retries=10, **kwargs):
    """
    Retry a function up to `retries` times on AssertionError.
    """
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except AssertionError as e:
            if i == retries - 1:
                raise
            log.info("Retry %d/%d: %s", i + 1, retries, e)
