#!/bin/bash
#
# Setup Web Admin with Systemd Socket Activation
# On-demand start: Web admin only runs when accessed via browser
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "Weather Station - Web Admin Socket Activation"
echo "=================================================="
echo ""
echo "This will configure web admin to start ON-DEMAND"
echo "Only when you access http://localhost:8080"
echo ""
echo "Benefits:"
echo "  ✓ Zero memory usage when idle"
echo "  ✓ Auto-start when accessed"
echo "  ✓ Auto-stop after idle timeout"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (or use sudo)"
    exit 1
fi

echo ""
echo "📦 Installing systemd socket and service..."

# Copy socket file
cp "$SCRIPT_DIR/web-admin.socket" /etc/systemd/system/
chmod 644 /etc/systemd/system/web-admin.socket

# Copy service file
cp "$SCRIPT_DIR/web-admin.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/web-admin.service

# Reload systemd
systemctl daemon-reload

echo ""
echo "🔌 Enabling socket activation..."

# Enable and start socket (NOT the service!)
systemctl enable web-admin.socket
systemctl start web-admin.socket

echo ""
echo "✅ Setup complete!"
echo ""
echo "=================================================="
echo "USAGE"
echo "=================================================="
echo ""
echo "Web admin is now in STANDBY mode:"
echo "  • Socket listening on port 8080"
echo "  • Service NOT running (zero memory)"
echo ""
echo "To access:"
echo "  1. Open browser to http://$(hostname -I | awk '{print $1}'):8080"
echo "  2. Web admin will AUTO-START (may take 2-3 seconds)"
echo "  3. After 5 minutes idle, will AUTO-STOP"
echo ""
echo "Check status:"
echo "  sudo systemctl status web-admin.socket"
echo "  sudo systemctl status web-admin.service"
echo ""
echo "View logs:"
echo "  sudo journalctl -u web-admin -f"
echo ""
echo "Disable socket activation:"
echo "  sudo systemctl stop web-admin.socket"
echo "  sudo systemctl disable web-admin.socket"
echo ""
