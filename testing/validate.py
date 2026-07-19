# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import ipaddress


def ip_list(s):
    # TODO: validate that values are IP addresses.
    return s.split(",")


def cpus(s):
    n = int(s)
    if n < 1:
        raise ValueError(f"Invalid number of cpus: '{s}'")
    return n


def subnet_mask(s):
    """
    Raises NetmaskValueError if 's' is not a valid netmask.

    Returns the unmodified string.
    """
    ipaddress.IPv4Network(f"0.0.0.0/{s}")
    return s


def bridged_mode(p, args):
    if args.operation_mode == "bridged":
        if not args.shared_interface:
            p.error("--shared-interface required for --operation-mode=bridged")
        if args.enable_isolation:
            p.error("--enable-isolation not compatible with --operation-mode=bridged")


def network_options(p, args):
    """
    Validate the network options passed to run.
    """
    if args.network_name:
        if args.operation_mode:
            p.error("--network cannot be used with --operation-mode")
        if args.start_address:
            p.error("--network cannot be used with --start-address")
        if args.end_address:
            p.error("--network cannot be used with --end-address")
        if args.subnet_mask:
            p.error("--network cannot be used with --subnet-mask")

    if args.ip_address and not (
        args.start_address and args.end_address and args.subnet_mask
    ):
        p.error("--ip-address requires --start-address, --end-address, --subnet-mask")

    if args.start_address and args.end_address and args.subnet_mask:
        # vmnet does not enforce the order of --start-address and --end-address.
        start_address = ipaddress.IPv4Interface((args.start_address, args.subnet_mask))
        subnet = start_address.network
        if args.end_address not in subnet:
            p.error("--start-address and --end-address must be in the same subnet")
        # --ip-address inside the DHCP range may cause conflicts, but works.
        if args.ip_address and args.ip_address not in subnet:
            p.error(
                "--ip-address, --start-address and --end-address must be in the same subnet",
            )


def private_ipv4_address(ip):
    """
    Validates that "ip" is in the RFC 1918 private range.

    Returns an ipaddress.IPv4Address object, or raises ValueError if validation fails.
    """
    address = ipaddress.IPv4Address(ip)
    rfc1918_subnets = ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]
    for subnet in rfc1918_subnets:
        network = ipaddress.IPv4Network(subnet)
        if address in network:
            return address
    raise ValueError(f"{ip} is not a valid RFC 1918 IP address")
