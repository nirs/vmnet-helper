#!/usr/bin/env bash
set -euo pipefail

machine="$(uname -m)"
archive="vmnet-helper-$machine.tar.gz"

# Fail the download if GitHub returns an error page
curl -fsSLo "$archive" "https://github.com/nirs/vmnet-helper/releases/latest/download/$archive"

# Extract the archive into / (it contains ./opt/vmnet-helper/...)
sudo tar -xvvmf "$archive" -C / opt/vmnet-helper
rm -f "$archive"

install_sudoers() {
  sudo install -d -m 0755 /etc/sudoers.d
  sudo install -m 0640 /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/vmnet-helper /etc/sudoers.d/
}

# Non-interactive (CI or no TTY) OR explicit -s flag => install without prompting
if [[ "${1:-}" == "-s" || -n "${CI:-}" || ! -t 0 ]]; then
  install_sudoers
else
  yn=""
  # If read fails (e.g. user hits Ctrl-D), default to Yes
  read -r -p "Do you want to configure sudoers rule to run without a password? (Y/n) " yn || yn="Y"
  if [[ -z "$yn" || "$yn" =~ ^[Yy]$ ]]; then
    install_sudoers
  fi
fi

exit 0