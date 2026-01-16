#!/bin/bash

# -e            Exit if single command, fails
# -u            Exit when expanding unset variables
# -o pipefail   Exit if one of the command in a pipeline fails
set -e -u -o pipefail

# Interactive installation (default 1)
# Set to 0 to disable interaction.
interactive=${VMNET_INTERACTIVE:-1}

# Configure sudo to allow running vmnet-helper without a password.
# - Not set: auto mode (enabled on macOS 15 and earlier, disabled on macOS 26+)
# - Set to 1: enable (in interactive mode, asks for confirmation)
# - Set to 0: disable
configure_sudo=${VMNET_CONFIGURE_SUDO:-}

# GitHub user to install from (default nirs)
# Modify to install from your fork.
user=${VMNET_USER:-nirs}

# GitHub repo to install from (default vmnet-helper)
# Modify to install from your fork if you renamed it.
repo=${VMNET_REPO:-vmnet-helper}

# Version to install (default latest)
# Versions before v0.7.0 not supported.
version=${VMNET_VERSION:-latest}

# Temp directory for downloaded release, cleaned up on exit.
download_tmpdir=""

main() {
    local tarball="${1:-}"

    # Auto mode: configure sudo on macOS 15 and earlier, skip on macOS 26+.
    if [ -z "$configure_sudo" ]; then
        configure_sudo=$(recommend_sudo)
    fi

    if [ "$interactive" = "1" ]; then
        authorize_user
        if [ "$configure_sudo" = "1" ]; then
            confirm_sudo_configuration
        fi
    fi

    echo

    if [ -z "$tarball" ]; then
        create_download_tmpdir
        tarball="$download_tmpdir/vmnet-helper.tar.gz"
        download_release "$tarball"
    fi

    install_files "$tarball"

    if [ "$configure_sudo" = "1" ]; then
        install_sudoers
    fi

    echo
    echo "✅ vmnet-helper was installed successfully!"
}

recommend_sudo() {
    # On macOS 26+, vmnet-helper can run without root privileges.
    local major_version
    major_version=$(sw_vers -productVersion | cut -d. -f1)
    if [ "$major_version" -ge 26 ]; then
        echo 0
    else
        echo 1
    fi
}

create_download_tmpdir() {
    download_tmpdir=$(mktemp -d -t vmnet-helper)
    trap 'rm -rf "$download_tmpdir"' EXIT
}

download_release() {
    local tarball="$1"
    local url

    if [ "$version" = "latest" ]; then
        url="https://github.com/$user/$repo/releases/latest/download/vmnet-helper.tar.gz"
    else
        url="https://github.com/$user/$repo/releases/download/$version/vmnet-helper.tar.gz"
    fi

    echo "Downloading $url"
    curl --fail --silent --show-error --location --output "$tarball" "$url"
}

install_files() {
    local tarball="$1"

    echo "Installing vmnet-helper at /opt/vmnet-helper"

    # IMPORTANT: The vmnet-helper executable and the directory where it is installed
    # must be owned by root and may not be modifiable by unprivileged users.
    sudo tar --extract --verbose --gunzip --file "$tarball" --directory / opt/vmnet-helper 2>&1
}

install_sudoers() {
    echo "Installing /etc/sudoers.d/vmnet-helper"
    sudo install -m 0640 /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/vmnet-helper /etc/sudoers.d/
}

authorize_user() {
    echo "Installation requires your password to install vmnet-helper as root"
    sudo true
}

confirm_sudo_configuration() {
    read -p "Configure sudo to run vmnet-helper without a password? (Y/n): " reply </dev/tty
    case "$reply" in
        Y|y|"")
            ;;
        *)
            configure_sudo=0
            echo "Please check /opt/vmnet-helper/share/doc/vmnet-helper/sudoers.d/README.md"
            echo "if you want to configure sudo later."
            ;;
    esac
}

main "$@"
