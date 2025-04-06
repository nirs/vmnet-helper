#!/bin/sh

# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

# Create cidata iso for examples.

MAC_ADDRESS="${1:?Usage: create-iso MAC_ADDRESS [FILENAME]}"
CIDATA_ISO="${2:-cidata.iso}"
SERIAL_CONSOLE="${3:-hvc0}"

# The runcmd script runs on every boot to report the IP address. The tests uses
# this to provision the VM.
cat > user-data << EOF
#cloud-config
password: password
chpasswd:
  expire: false
runcmd:
- "ip_address=\$(ip -4 -j addr show dev vmnet0 | jq -r '.[0].addr_info[0].local')"
- "echo > /dev/$SERIAL_CONSOLE"
- "echo example address: \$ip_address > /dev/$SERIAL_CONSOLE"
ssh_authorized_keys:
EOF

# We use the public key to provision the VM in the tests.
for name in ~/.ssh/id_*.pub; do
    echo "- $(cat $name)" >> user-data
done

cat > meta-data << EOF
instance-id: $(uuidgen)
local-hostname: example
EOF

# We rename the interface to to make it easy to find the IP address during
# boot.
cat > network-config << EOF
version: 2
ethernets:
  vmnet0:
    match:
      macaddress: $MAC_ADDRESS
    set-name: vmnet0
    dhcp4: true
    dhcp-identifier: mac
EOF

mkisofs \
    -output "$CIDATA_ISO" \
    -volid cidata \
    -joliet \
    -rock \
    user-data meta-data network-config
