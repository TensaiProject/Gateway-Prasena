#!/bin/bash
# Gateway-Prasena Static IP Configuration Script
# Phase 2: Convert current DHCP IP to Static IP
# Safe for remote (Tailscale) usage - current IP is already working!

set -e

echo "======================================"
echo "Gateway-Prasena Static IP Setup"
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

echo "[1/3] Current Network Configuration"
echo "--------------------------------------"

# Detect WiFi interface
WIFI_INTERFACE=$(nmcli -t -f DEVICE,TYPE device | grep wifi | cut -d: -f1 | head -n1)

if [ -z "$WIFI_INTERFACE" ]; then
    echo "ERROR: WiFi interface not found!"
    echo "Please ensure WiFi is connected first."
    exit 1
fi

# Get current SSID (for display only)
CURRENT_SSID=$(iwgetid -r 2>/dev/null || echo "")

if [ -z "$CURRENT_SSID" ]; then
    echo "ERROR: No WiFi connection detected!"
    echo "Please connect to WiFi first using: sudo bash scripts/change_wifi_dhcp.sh"
    exit 1
fi

# Get ACTUAL active connection name (NOT SSID!)
# This is the key fix: connection name might be different from SSID
CONNECTION_NAME=$(nmcli -t -f NAME,DEVICE connection show --active | grep ":$WIFI_INTERFACE$" | cut -d: -f1)

if [ -z "$CONNECTION_NAME" ]; then
    echo "ERROR: No active connection found for $WIFI_INTERFACE!"
    echo "Please ensure WiFi is connected."
    exit 1
fi

# Get current IP configuration
CURRENT_IP=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)
CURRENT_GATEWAY=$(ip route | grep default | grep "$WIFI_INTERFACE" | awk '{print $3}' | head -n1)
CURRENT_CIDR=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}/\d+' | cut -d/ -f2 | head -n1)
CURRENT_METHOD=$(nmcli -t -f ipv4.method connection show "$CONNECTION_NAME" | cut -d: -f2)

if [ -z "$CURRENT_IP" ]; then
    echo "ERROR: Failed to detect current IP address!"
    exit 1
fi

if [ -z "$CURRENT_GATEWAY" ]; then
    echo "ERROR: Failed to detect gateway!"
    exit 1
fi

if [ -z "$CURRENT_CIDR" ]; then
    CURRENT_CIDR="24"  # Default /24
fi

# Convert CIDR to netmask for display
case "$CURRENT_CIDR" in
    8)  NETMASK="255.0.0.0" ;;
    16) NETMASK="255.255.0.0" ;;
    24) NETMASK="255.255.255.0" ;;
    *)  NETMASK="255.255.255.0" ;;
esac

echo "WiFi SSID: $CURRENT_SSID"
echo "Connection Name: $CONNECTION_NAME"
echo "WiFi Interface: $WIFI_INTERFACE"
echo "Current IP: $CURRENT_IP"
echo "Current Gateway: $CURRENT_GATEWAY"
echo "Current Subnet: /$CURRENT_CIDR ($NETMASK)"
echo "Current Method: $CURRENT_METHOD"
echo ""

# Check if already static
if [ "$CURRENT_METHOD" = "manual" ]; then
    echo "⚠ NOTICE: IP is already configured as STATIC!"
    echo ""
    read -p "Do you want to reconfigure static IP? (y/n): " RECONFIGURE
    if [ "$RECONFIGURE" != "y" ]; then
        echo "Static IP configuration cancelled."
        exit 0
    fi
    echo ""
fi

# Test internet connectivity
echo "Testing internet connectivity..."
if timeout 5 ping -c 2 8.8.8.8 &>/dev/null; then
    echo "✓ Internet connection working!"
else
    echo "⚠ WARNING: Internet test failed!"
    echo "  Current IP may not have working internet."
    echo ""
    read -p "Continue anyway? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 0
    fi
fi
echo ""

# Confirmation
echo "[2/3] Static IP Configuration"
echo "--------------------------------------"
echo "This script will convert your current DHCP IP to Static IP."
echo ""
echo "Configuration to be applied:"
echo "  IP Address: $CURRENT_IP/$CURRENT_CIDR"
echo "  Gateway: $CURRENT_GATEWAY"
echo "  DNS: 8.8.8.8 (Google DNS)"
echo "  Auto-connect: Enabled"
echo ""
echo "Benefits:"
echo "  ✓ IP will not change after reboot"
echo "  ✓ Persistent across power failures"
echo "  ✓ Reliable remote access"
echo ""

read -p "Apply static IP configuration? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Static IP configuration cancelled."
    exit 0
fi

echo ""

# Apply static IP configuration
echo "[3/3] Applying Static IP"
echo "--------------------------------------"

# Use Google DNS for reliability
STATIC_DNS="8.8.8.8"

echo "Converting to Static IP..."

# Modify connection with all settings at once (atomic operation)
# Use CONNECTION_NAME (not SSID) because they might be different!
nmcli connection modify "$CONNECTION_NAME" \
    ipv4.method manual \
    ipv4.addresses "${CURRENT_IP}/${CURRENT_CIDR}" \
    ipv4.gateway "$CURRENT_GATEWAY" \
    ipv4.dns "$STATIC_DNS" \
    connection.autoconnect yes

# Sync to disk (force write)
sync

echo "✓ Configuration saved to disk"

# Verify config saved
CONFIG_FILE="/etc/NetworkManager/system-connections/${CONNECTION_NAME}.nmconnection"
if [ -f "$CONFIG_FILE" ]; then
    if grep -q "method=manual" "$CONFIG_FILE" 2>/dev/null; then
        echo "✓ Static config verified on disk"
    else
        CONFIG_FILE="/etc/NetworkManager/system-connections/${CONNECTION_NAME}"
        if [ -f "$CONFIG_FILE" ] && grep -q "method=manual" "$CONFIG_FILE" 2>/dev/null; then
            echo "✓ Static config verified on disk"
        else
            echo "⚠ Config file verification skipped (file not accessible)"
        fi
    fi
else
    echo "⚠ Config file verification skipped (file not accessible)"
fi

# Restart connection to apply static IP
echo "Restarting connection to apply Static IP..."
nmcli connection down "$CONNECTION_NAME" 2>/dev/null || true
sleep 2
nmcli connection up "$CONNECTION_NAME"

# Wait for connection
sleep 3

echo "✓ Connection restarted"
echo ""

# Verify static IP applied
NEW_IP=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)
IP_METHOD=$(nmcli -t -f ipv4.method connection show "$CONNECTION_NAME" | cut -d: -f2)

# Test internet again
echo "Verifying internet connectivity..."
if timeout 5 ping -c 2 8.8.8.8 &>/dev/null; then
    INTERNET_STATUS="✓ Working"
else
    INTERNET_STATUS="⚠ Failed"
fi

echo ""

if [ "$IP_METHOD" = "manual" ] && [ "$NEW_IP" = "$CURRENT_IP" ]; then
    echo "======================================"
    echo "✓ Static IP Applied Successfully!"
    echo "======================================"
    echo ""
    echo "Network Configuration:"
    echo "  WiFi SSID: $CURRENT_SSID"
    echo "  IP Address: $NEW_IP (STATIC)"
    echo "  Gateway: $CURRENT_GATEWAY"
    echo "  DNS: $STATIC_DNS"
    echo "  Subnet: $NETMASK"
    echo "  Internet: $INTERNET_STATUS"
    echo ""
    echo "Features:"
    echo "  ✓ Static IP (persistent across reboots)"
    echo "  ✓ Auto-connect enabled"
    echo "  ✓ Google DNS (8.8.8.8)"
    echo "  ✓ Configuration saved to disk"
    echo ""
    echo "Your Raspi will always use IP: $NEW_IP"
    echo "You can now access via: ssh $ACTUAL_USER@$NEW_IP"
    echo ""
else
    echo "======================================"
    echo "⚠ Static IP Verification Warning"
    echo "======================================"
    echo ""
    echo "Configuration applied but verification shows:"
    echo "  Expected IP: $CURRENT_IP"
    echo "  Actual IP: $NEW_IP"
    echo "  Expected Method: manual"
    echo "  Actual Method: $IP_METHOD"
    echo ""
    echo "This may be temporary. Try:"
    echo "  1. Wait 30 seconds"
    echo "  2. Check IP: ip addr show $WIFI_INTERFACE"
    echo "  3. Check method: nmcli connection show \"$CURRENT_SSID\" | grep ipv4.method"
    echo ""
fi
