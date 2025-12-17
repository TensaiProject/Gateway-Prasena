#!/bin/bash

##############################################
# Auto Installer: Subnet Keep-Alive Service
# For Raspberry Pi Weather Station
# Prevents ARP cache timeout issues
##############################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Subnet Keep-Alive Service Installer"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root or with sudo${NC}"
    echo "Usage: sudo bash $0"
    exit 1
fi

# Configuration
SUBNET="192.168.1.0/24"
PING_INTERVAL=10
SCRIPT_PATH="/usr/local/bin/keep-alive-subnet.sh"
SERVICE_PATH="/etc/systemd/system/subnet-keepalive.service"

echo -e "${YELLOW}[1/6]${NC} Checking dependencies..."
if ! command -v fping &> /dev/null; then
    echo "Installing fping..."
    apt-get update -qq
    apt-get install -y fping
    echo -e "${GREEN}✓ fping installed${NC}"
else
    echo -e "${GREEN}✓ fping already installed${NC}"
fi
echo ""

echo -e "${YELLOW}[2/6]${NC} Creating keep-alive script..."
cat > "$SCRIPT_PATH" << 'EOF'
#!/bin/bash

# Keep-alive ping entire subnet
# Prevents ARP cache timeout for all devices

SUBNET="192.168.1.0/24"
PING_INTERVAL=10  # Ping every 10 seconds

while true; do
    fping -g $SUBNET -c 1 -t 1000 > /dev/null 2>&1
    sleep $PING_INTERVAL
done
EOF

chmod +x "$SCRIPT_PATH"
echo -e "${GREEN}✓ Script created at $SCRIPT_PATH${NC}"
echo ""

echo -e "${YELLOW}[3/6]${NC} Creating systemd service..."
cat > "$SERVICE_PATH" << 'EOF'
[Unit]
Description=Keep-Alive Ping Entire Subnet
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/keep-alive-subnet.sh
Restart=always
RestartSec=5
StandardOutput=null

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Service file created at $SERVICE_PATH${NC}"
echo ""

echo -e "${YELLOW}[4/6]${NC} Reloading systemd daemon..."
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"
echo ""

echo -e "${YELLOW}[5/6]${NC} Enabling and starting service..."
systemctl enable subnet-keepalive.service
systemctl start subnet-keepalive.service
echo -e "${GREEN}✓ Service enabled and started${NC}"
echo ""

echo -e "${YELLOW}[6/6]${NC} Verifying installation..."
sleep 2

if systemctl is-active --quiet subnet-keepalive.service; then
    echo -e "${GREEN}✓ Service is running!${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo "Check logs with: sudo journalctl -u subnet-keepalive.service -n 20"
    exit 1
fi

if systemctl is-enabled --quiet subnet-keepalive.service; then
    echo -e "${GREEN}✓ Service will auto-start on boot${NC}"
else
    echo -e "${RED}✗ Service not enabled for auto-start${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  • Subnet: $SUBNET"
echo "  • Ping Interval: ${PING_INTERVAL}s"
echo "  • Script: $SCRIPT_PATH"
echo "  • Service: $SERVICE_PATH"
echo ""
echo "Useful Commands:"
echo "  • Check status:  sudo systemctl status subnet-keepalive"
echo "  • Stop service:  sudo systemctl stop subnet-keepalive"
echo "  • Start service: sudo systemctl start subnet-keepalive"
echo "  • View logs:     sudo journalctl -u subnet-keepalive -f"
echo "  • Verify pings:  sudo tcpdump -i any icmp -n | head -30"
echo ""
echo "Done! The service is now running and will prevent"
echo "ARP cache timeout issues with MISOL weather station."
echo ""
