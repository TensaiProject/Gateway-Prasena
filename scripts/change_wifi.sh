#!/bin/bash
# Gateway-Prasena WiFi Configuration Script
# Auto DHCP → Static IP Conversion (Zero User Configuration)

set -e

echo "======================================"
echo "Gateway-Prasena WiFi Configuration"
echo "======================================"
echo ""

# Check if running with sudo/root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run with sudo"
    echo "Usage: sudo bash $0"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"

echo "[1/5] Current WiFi Status"
echo "--------------------------------------"
CURRENT_SSID=$(iwgetid -r 2>/dev/null || echo "Not connected")
CURRENT_IP=$(hostname -I | awk '{print $1}')
echo "Current WiFi: $CURRENT_SSID"
echo "Current IP: $CURRENT_IP"
echo ""

# Ask if user wants to scan
read -p "Scan for available WiFi networks? (y/n): " SCAN_CHOICE
if [ "$SCAN_CHOICE" = "y" ]; then
    echo ""
    echo "[2/5] Scanning WiFi Networks..."
    echo "--------------------------------------"
    nmcli device wifi list
    echo ""
else
    echo ""
    echo "[2/5] Skipping WiFi scan"
    echo ""
fi

# Get WiFi SSID
echo "[3/5] WiFi Credentials"
echo "--------------------------------------"
read -p "Enter WiFi SSID: " WIFI_SSID

if [ -z "$WIFI_SSID" ]; then
    echo "ERROR: WiFi SSID cannot be empty"
    exit 1
fi

# Get WiFi Password
read -sp "Enter WiFi Password (leave empty for open network): " WIFI_PASSWORD
echo ""
echo ""

# Auto DHCP → Static Conversion
echo "[4/5] Connecting and Configuring WiFi"
echo "--------------------------------------"
echo "SSID: $WIFI_SSID"
echo "Method: Auto (DHCP → Static)"
echo ""

# Disconnect from current WiFi if connected
if [ "$CURRENT_SSID" != "Not connected" ]; then
    echo "Disconnecting from current WiFi: $CURRENT_SSID"
    nmcli connection down "$CURRENT_SSID" 2>/dev/null || true
    sleep 1
fi

# Step 1: Connect with DHCP mode (temporary)
echo "Connecting to $WIFI_SSID with DHCP..."
if [ -n "$WIFI_PASSWORD" ]; then
    nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD"
else
    nmcli device wifi connect "$WIFI_SSID"
fi

# Wait for connection to establish
sleep 3

# Step 2: Auto-detect network configuration
echo "Auto-detecting network configuration..."

# Detect WiFi interface (wlan0 or wlan1)
WIFI_INTERFACE=$(nmcli -t -f DEVICE,TYPE device | grep wifi | cut -d: -f1 | head -n1)

if [ -z "$WIFI_INTERFACE" ]; then
    echo "ERROR: WiFi interface not found!"
    exit 1
fi

# Detect IP address from DHCP (with retry)
DETECTED_IP=""
for i in {1..10}; do
    DETECTED_IP=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)
    if [ -n "$DETECTED_IP" ]; then
        break
    fi
    sleep 1
done

if [ -z "$DETECTED_IP" ]; then
    echo "ERROR: Failed to obtain IP from DHCP!"
    echo "Please check WiFi password and network availability."
    exit 1
fi

# Detect Gateway
DETECTED_GATEWAY=$(ip route | grep default | grep "$WIFI_INTERFACE" | awk '{print $3}' | head -n1)

if [ -z "$DETECTED_GATEWAY" ]; then
    echo "ERROR: Failed to detect Gateway!"
    exit 1
fi

# Detect Subnet (CIDR notation)
DETECTED_CIDR=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}/\d+' | cut -d/ -f2 | head -n1)

if [ -z "$DETECTED_CIDR" ]; then
    DETECTED_CIDR="24"  # Default /24
fi

# Convert CIDR to netmask for display
case "$DETECTED_CIDR" in
    8)  NETMASK="255.0.0.0" ;;
    16) NETMASK="255.255.0.0" ;;
    24) NETMASK="255.255.255.0" ;;
    *)  NETMASK="255.255.255.0" ;;
esac

# Use Google DNS (reliable and fast)
STATIC_DNS="8.8.8.8"

# Show detected configuration
echo "  Detected IP: $DETECTED_IP"
echo "  Detected Gateway: $DETECTED_GATEWAY"
echo "  Detected Subnet: /$DETECTED_CIDR ($NETMASK)"
echo "  Using DNS: $STATIC_DNS (Google DNS)"
echo ""

# Step 3: Convert to Static IP (Atomic operation)
echo "Converting DHCP to Static IP..."

# Modify connection with all settings at once (atomic)
nmcli connection modify "$WIFI_SSID" \
    ipv4.method manual \
    ipv4.addresses "${DETECTED_IP}/${DETECTED_CIDR}" \
    ipv4.gateway "$DETECTED_GATEWAY" \
    ipv4.dns "$STATIC_DNS" \
    connection.autoconnect yes

# Sync to disk (force write)
sync

# Step 4: Verify config saved to disk
CONFIG_FILE="/etc/NetworkManager/system-connections/${WIFI_SSID}.nmconnection"
if [ -f "$CONFIG_FILE" ]; then
    if grep -q "method=manual" "$CONFIG_FILE" 2>/dev/null; then
        echo "✓ Static config saved to disk!"
    else
        echo "✗ Config save verification failed!"
        exit 1
    fi
else
    # Try alternative location (older NetworkManager versions)
    CONFIG_FILE="/etc/NetworkManager/system-connections/${WIFI_SSID}"
    if [ -f "$CONFIG_FILE" ] && grep -q "method=manual" "$CONFIG_FILE" 2>/dev/null; then
        echo "✓ Static config saved to disk!"
    else
        echo "⚠ Config file verification skipped (file not accessible)"
    fi
fi

# Step 5: Restart connection to apply Static IP
echo "Restarting connection to apply Static IP..."
nmcli connection down "$WIFI_SSID" 2>/dev/null || true
sleep 2
nmcli connection up "$WIFI_SSID"

# Wait for connection
sleep 3

echo "✓ Connection restarted with Static IP"
echo ""

# Verification
echo "[5/5] Verification"
echo "--------------------------------------"

# Get new connection info
NEW_SSID=$(iwgetid -r 2>/dev/null || echo "Not connected")
NEW_IP=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)
IP_METHOD=$(nmcli -t -f ipv4.method connection show "$WIFI_SSID" | cut -d: -f2)

echo "Connected WiFi: $NEW_SSID"
echo "IP Address: $NEW_IP (${IP_METHOD^^})"
echo "Gateway: $DETECTED_GATEWAY"
echo "DNS: $STATIC_DNS"
echo "Subnet Mask: $NETMASK"
echo ""

# Test internet connectivity
echo "Testing internet connectivity..."
if ping -c 2 8.8.8.8 &>/dev/null; then
    echo "✓ Internet connection working!"
else
    echo "⚠ Internet connection test failed (ping timeout)"
fi
echo ""

# Final verification
if [ "$NEW_SSID" = "$WIFI_SSID" ] && [ "$IP_METHOD" = "manual" ] && [ "$NEW_IP" = "$DETECTED_IP" ]; then
    echo "======================================"
    echo "✓ WiFi Configuration Successful!"
    echo "======================================"
    echo ""
    echo "WiFi SSID: $NEW_SSID"
    echo "IP Address: $NEW_IP (STATIC)"
    echo "Gateway: $DETECTED_GATEWAY"
    echo "DNS: $STATIC_DNS"
    echo ""
    echo "Configuration Features:"
    echo "  ✓ Static IP (persistent across reboots)"
    echo "  ✓ Auto-connect enabled"
    echo "  ✓ Google DNS (8.8.8.8)"
    echo "  ✓ No manual reboot required"
    echo ""
    echo "Note: SSH connection may disconnect briefly."
    echo "Reconnect using: ssh $ACTUAL_USER@$NEW_IP"
    echo ""
else
    echo "======================================"
    echo "✗ WiFi Configuration Failed"
    echo "======================================"
    echo ""
    echo "Verification failed:"
    echo "  Expected SSID: $WIFI_SSID"
    echo "  Actual SSID: $NEW_SSID"
    echo "  Expected IP Method: manual"
    echo "  Actual IP Method: $IP_METHOD"
    echo "  Expected IP: $DETECTED_IP"
    echo "  Actual IP: $NEW_IP"
    echo ""
    exit 1
fi
