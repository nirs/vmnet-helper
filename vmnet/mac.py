# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import secrets


def random_mac_address():
    """
    Return locally administered unicast MAC address.
    https://en.wikipedia.org/wiki/MAC_address#Universal_vs._local_(U/L_bit)
    """
    b = bytearray(secrets.token_bytes(6))
    b[0] = (b[0] | 2) & 0xfe
    return f"{b[0]:02x}:{b[1]:02x}:{b[2]:02x}:{b[3]:02x}:{b[4]:02x}:{b[5]:02x}"
