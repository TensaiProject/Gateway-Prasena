#!/bin/bash
#
# Setup systemd services
#

set -e

echo "=============================================="
echo "Setting up systemd services..."
echo "=============================================="
echo ""

# Check if running as non-root
if [ "$EUID" -eq 0 ]; then
   echo "Please run as normal user (not root/sudo)"
   exit 1
fi

# Copy service files
echo "Copying service files to /etc/systemd/system/..."
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.timer /etc/systemd/system/

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable services
echo "Enabling services..."
sudo systemctl enable weatherstation-pzem.service
sudo systemctl enable weatherstation-upload.service
sudo systemctl enable weatherstation-mqtt.service
sudo systemctl enable weatherstation-weather.service
sudo systemctl enable weatherstation-cleanup.timer

echo ""
echo "Services installed and enabled!"
echo ""
echo "To start services:"
echo "  sudo systemctl start weatherstation-pzem"
echo "  sudo systemctl start weatherstation-upload"
echo "  sudo systemctl start weatherstation-mqtt"
echo "  sudo systemctl start weatherstation-weather"
echo ""
echo "Or start all at once:"
echo "  sudo systemctl start weatherstation-*"
echo ""
echo "Cleanup timer (runs daily at 3:00 AM):"
echo "  sudo systemctl start weatherstation-cleanup.timer"
echo "  sudo systemctl status weatherstation-cleanup.timer"
echo ""
echo "To check timer schedule:"
echo "  systemctl list-timers weatherstation-cleanup.timer"
echo ""
echo "To run cleanup manually:"
echo "  python3 run.py --service cleanup"
echo ""
echo "To check status:"
echo "  sudo systemctl status weatherstation-*"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u weatherstation-pzem -f"
echo "  sudo journalctl -u weatherstation-cleanup -f"
echo ""
