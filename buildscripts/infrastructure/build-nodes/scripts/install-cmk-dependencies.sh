#!/bin/bash
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# Prepares the current system (must be a supported distro) for installing a
# Checkmk package.

set -e -o pipefail

TARGET_DIR="/opt"
if [ "$DISTRO" = "cma-3" ]; then
    # as there are no system tests with CMA-3, an installation of CMK
    # dependencies is not required
    exit
fi
FILE_NAME=$(echo "${DISTRO^^}.mk" | tr '-' '_')

extract_needed_packages() {
    echo "Extracting needed packages of $FILE_NAME"
    mkdir -p "$TARGET_DIR"
    cd "$TARGET_DIR"
    echo -e ".PHONY: needed-packages\nneeded-packages:\n\t@echo \$(OS_PACKAGES) > needed-packages\n" |
        make -f - -f "${FILE_NAME}" --no-print-directory needed-packages
}

add_gpg_key() {
    echo "Add Check_MK-pubkey.gpg to RPM"
    rpm --import "$TARGET_DIR"/Check_MK-pubkey.gpg
}

cleanup() {
    rm -f "$TARGET_DIR"/needed-packages
    rm -rf /var/lib/apt/lists/*
}

extract_needed_packages

case "$DISTRO" in
    centos-* | almalinux-*)
        add_gpg_key
        # shellcheck disable=SC2046  # we want word splitting here
        yum install -y $(cat "$TARGET_DIR"/needed-packages)
        ;;
    sles-*)
        add_gpg_key
        # shellcheck disable=SC2046  # we want word splitting here
        zypper in -y $(cat "$TARGET_DIR"/needed-packages)
        ;;
    ubuntu-* | debian-*)
        apt-get update
        # shellcheck disable=SC2046  # we want word splitting here
        apt-get install -y $(cat "$TARGET_DIR"/needed-packages)
        ;;
    *)
        echo "ERROR: Unhandled DISTRO: $DISTRO"
        exit 1
        ;;
esac

cleanup
