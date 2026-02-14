# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import hashlib


def mac_address_from(name):
    """
    Return locally administered unicast MAC address generated from the VM name.
    This ensures the same VM always gets the same MAC address.
    https://en.wikipedia.org/wiki/MAC_address#Universal_vs._local_(U/L_bit)
    """
    full_name = f"vmnet-helper-mac-{name}"
    b = bytearray(hashlib.sha256(full_name.encode()).digest()[:6])
    b[0] = (b[0] | 2) & 0xFE
    return f"{b[0]:02x}:{b[1]:02x}:{b[2]:02x}:{b[3]:02x}:{b[4]:02x}:{b[5]:02x}"
