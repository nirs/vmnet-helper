#!/usr/bin/env bash
set -euo pipefail

machine="$(uname -m)"
archive="vmnet-helper-$machine.tar.gz"
curl -LOf "https://github.com/nirs/vmnet-helper/releases/latest/download/$archive"
sudo tar xvf "$archive" -C / opt/vmnet-helper
rm "$archive"

# If called with -s, skip the prompt and install sudoers.
if [[ "${1:-}" == "-s" ]]; then
  sudo install -m 0640 /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/vmnet-helper /etc/sudoers.d/
else
  read -r -p "Do you want to confiigure soders rule to run without a password? (Y/n) " yn
  if [[ -z "$yn" || "$yn" =~ ^[Yy]$ ]]; then
    sudo install -m 0640 /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/vmnet-helper /etc/sudoers.d/
  fi
fi