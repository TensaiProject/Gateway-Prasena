#!/bin/bash
# One-command deployment script for Raspberry Pi
# Usage: curl -sSL https://raw.githubusercontent.com/.../deploy.sh | bash

set -e

REPO_URL="https://github.com/TensaiProject/Gateway-Prasena.git"
INSTALL_DIR="/home/$USER/Gateway-Prasena"

echo "======================================"
echo "Gateway-Prasena Auto-Deploy"
echo "======================================"
echo ""

# Quick check
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Do not run as root"
    exit 1
fi

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Run installation
echo ""
echo "Running installation script..."
bash "$INSTALL_DIR/scripts/install.sh"

# Setup systemd
echo ""
read -p "Setup systemd auto-start? (y/N): " setup_systemd
if [ "$setup_systemd" = "y" ]; then
    sudo bash "$INSTALL_DIR/scripts/setup_systemd.sh"
fi

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
