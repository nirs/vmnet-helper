#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Create cidata iso for examples.

MAC_ADDRESS="${1:?Usage: create-iso MAC_ADDRESS [FILENAME]}"
CIDATA_ISO="${2:-cidata.iso}"

cat > user-data << EOF
#cloud-config
password: password
chpasswd:
  expire: false
EOF

cat > meta-data << EOF
instance-id: $(uuidgen)
local-hostname: example
EOF

cat > network-config << EOF
version: 2
ethernets:
  eth0:
    match:
      macaddress: $MAC_ADDRESS
    set-name: eth0
    dhcp4: true
    dhcp-identifier: mac
EOF

mkisofs \
    -output "$CIDATA_ISO" \
    -volid cidata \
    -joliet \
    -rock \
    user-data meta-data network-config
