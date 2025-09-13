#!/bin/bash

# -e            Exit if single command, fails
# -u            Exit when expanding unset variables
# -o pipefail   Exit if one of the command in a pipeline fails
set -e -u -o pipefail

# Interactive installation (default 1)
# Set to 0 to disable interaction.
interactive=${VMNET_INTERACTIVE:-1}

# Configur sudo to allow running vmnet-helper without a password (default 1)
# Set to 0 to skip sudoers configuration.
configure_sudo=${VMNET_CONFIGURE_SUDO:-1}

# GitHub user to install from (default nirs)
# Modify to install from your fork.
user=${VMNET_USER:-nirs}

# Version to install (default latest)
# Versions before v0.7.0 not supported.
version=${VMNET_VERSION:-latest}

# Release download URL.
if [ "$version" = "latest" ]; then
    release_url="https://github.com/$user/vmnet-helper/releases/latest/download/vmnet-helper.tar.gz"
else
    release_url="https://github.com/$user/vmnet-helper/releases/download/$version/vmnet-helper.tar.gz"
fi

if [ "$interactive" = "1" ]; then
    echo "Installation requires your password to install vmnet-helper as root"
    sudo true

    read -p "Configure sudo to run vmnet-helper without a password? (Y/n): " reply </dev/tty
    case "$reply" in
        Y|y|"")
            configure_sudo=1
            ;;
        *)
            configure_sudo=0
            echo "Please check /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/README.md"
            echo "if you want to configure sudo later."
            ;;
    esac
fi

echo
echo "Installing vmnet-helper at /opt/vmnet-helper"
curl --fail --silent --show-error --location "$release_url" \
    | sudo tar --extract --verbose --file - --directory / opt/vmnet-helper

if [ $configure_sudo -eq 1 ]; then
    echo "Installing /etc/sudoers.d/vmnet-helper"
    sudo install -m 0640 /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/vmnet-helper /etc/sudoers.d/
fi

echo
echo "✅ vmnet-helper was installed successfully!"
