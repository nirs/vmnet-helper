# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import ipaddress


def ip_list(s):
    return [str(ipaddress.IPv4Address(x)) for x in s.split(",")]


def cpus(s):
    n = int(s)
    if n < 1:
        raise ValueError(f"Invalid number of cpus: '{s}'")
    return n


def subnet_mask(s):
    """
    Raises NetmaskValueError if 's' is not a valid netmask.

    Returns the unmodified string expected by ipaddress.IPv4Network.
    """
    ipaddress.IPv4Network(f"0.0.0.0/{s}")
    return s


def _one_dhcp_option_set(args):
    """
    Returns True if one or more DHCP option is set.
    """
    return args.start_address or args.end_address or args.subnet_mask


def _all_dhcp_options_set(args):
    """
    Returns True if all DHCP options are set.
    """
    return args.start_address and args.end_address and args.subnet_mask


def _dhcp_options(p, args):
    if _one_dhcp_option_set(args) and not _all_dhcp_options_set(args):
        p.error(
            "--start-address, --end-address, --subnet-mask must all be set or all omitted"
        )


def _bridged_mode(p, args):
    if not args.shared_interface:
        p.error("--shared-interface required for --operation-mode=bridged")
    if args.enable_isolation:
        p.error("--enable-isolation not compatible with --operation-mode=bridged")


def _shared_mode(p, args):
    _dhcp_options(p, args)


def _host_mode(p, args):
    _dhcp_options(p, args)


def operation_mode(p, args):
    if args.operation_mode == "shared" or not args.operation_mode:
        _shared_mode(p, args)
    elif args.operation_mode == "host":
        _host_mode(p, args)
    elif args.operation_mode == "bridged":
        _bridged_mode(p, args)


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
        if args.ip_address:
            p.error("--network cannot be used with --ip-address")

    if args.ip_address and not _all_dhcp_options_set(args):
        p.error("--ip-address requires --start-address, --end-address, --subnet-mask")

    if _all_dhcp_options_set(args):
        # vmnet does not enforce the order of --start-address and --end-address.
        network = ipaddress.IPv4Interface(
            (args.start_address, args.subnet_mask)
        ).network
        if args.end_address not in network:
            p.error("--start-address and --end-address must be in the same subnet")
        # --ip-address inside the DHCP range may cause conflicts, but works.
        if args.ip_address:
            if args.ip_address not in network:
                p.error(
                    "--ip-address, --start-address and --end-address "
                    "must be in the same subnet",
                )
            # Only reserve --start-address, since it gets assigned to the host.
            if args.ip_address == args.start_address:
                p.error("--ip-address must be different from --start-address")


_RFC1918_NETWORKS = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
]


def private_ipv4_address(ip):
    """
    Validates that "ip" is in the RFC 1918 private range.

    Returns an ipaddress.IPv4Address object, or raises ValueError if validation fails.
    """
    address = ipaddress.IPv4Address(ip)
    for network in _RFC1918_NETWORKS:
        if address in network:
            return address
    raise ValueError(f"{ip} is not a valid RFC 1918 IP address")
