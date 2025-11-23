#!/bin/bash
# Gateway-Prasena WiFi Configuration Script
# Interactive script to change WiFi connection via SSH

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

echo "[1/6] Current WiFi Status"
echo "--------------------------------------"
CURRENT_SSID=$(iwgetid -r 2>/dev/null || echo "Not connected")
echo "Current WiFi: $CURRENT_SSID"
echo ""

# Ask if user wants to scan
read -p "Scan for available WiFi networks? (y/n): " SCAN_CHOICE
if [ "$SCAN_CHOICE" = "y" ]; then
    echo ""
    echo "[2/6] Scanning WiFi Networks..."
    echo "--------------------------------------"
    nmcli device wifi list
    echo ""
else
    echo ""
    echo "[2/6] Skipping WiFi scan"
    echo ""
fi

# Get WiFi SSID
echo "[3/6] WiFi Credentials"
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

# IP Configuration
echo "[4/6] IP Configuration"
echo "--------------------------------------"
echo "1) DHCP (Automatic IP)"
echo "2) Static IP"
read -p "Choose IP configuration method (1 or 2): " IP_METHOD

if [ "$IP_METHOD" = "2" ]; then
    # Static IP configuration
    read -p "Enter IP Address (e.g., 192.168.1.100): " STATIC_IP
    read -p "Enter Gateway (e.g., 192.168.1.1): " GATEWAY
    read -p "Enter Subnet Mask [255.255.255.0]: " NETMASK
    NETMASK=${NETMASK:-255.255.255.0}
    read -p "Enter DNS Server [8.8.8.8]: " DNS
    DNS=${DNS:-8.8.8.8}

    # Convert netmask to CIDR
    if [ "$NETMASK" = "255.255.255.0" ]; then
        CIDR="24"
    elif [ "$NETMASK" = "255.255.0.0" ]; then
        CIDR="16"
    elif [ "$NETMASK" = "255.0.0.0" ]; then
        CIDR="8"
    else
        CIDR="24"  # Default
    fi

    IP_CONFIG="static"
    STATIC_IP_CIDR="$STATIC_IP/$CIDR"
else
    IP_CONFIG="dhcp"
fi

echo ""
echo "[5/6] Connecting to WiFi"
echo "--------------------------------------"
echo "SSID: $WIFI_SSID"
echo "IP Method: $IP_CONFIG"

# Disconnect from current WiFi if connected
if [ "$CURRENT_SSID" != "Not connected" ]; then
    echo "Disconnecting from current WiFi: $CURRENT_SSID"
    nmcli connection down "$CURRENT_SSID" 2>/dev/null || true
fi

# Connect to WiFi
if [ -n "$WIFI_PASSWORD" ]; then
    echo "Connecting to $WIFI_SSID with password..."
    nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD"
else
    echo "Connecting to $WIFI_SSID (open network)..."
    nmcli device wifi connect "$WIFI_SSID"
fi

# Wait for connection
sleep 2

# Configure IP settings
if [ "$IP_CONFIG" = "static" ]; then
    echo "Configuring static IP: $STATIC_IP"
    nmcli connection modify "$WIFI_SSID" ipv4.addresses "$STATIC_IP_CIDR"
    nmcli connection modify "$WIFI_SSID" ipv4.gateway "$GATEWAY"
    nmcli connection modify "$WIFI_SSID" ipv4.dns "$DNS"
    nmcli connection modify "$WIFI_SSID" ipv4.method manual

    # Restart connection to apply static IP
    nmcli connection down "$WIFI_SSID" 2>/dev/null || true
    sleep 1
    nmcli connection up "$WIFI_SSID"
    sleep 2
else
    echo "Using DHCP (automatic IP)..."
    nmcli connection modify "$WIFI_SSID" ipv4.method auto
fi

echo ""
echo "[6/6] Verification"
echo "--------------------------------------"

# Get new connection info
NEW_SSID=$(iwgetid -r 2>/dev/null || echo "Not connected")
NEW_IP=$(hostname -I | awk '{print $1}')

echo "Connected WiFi: $NEW_SSID"
echo "IP Address: $NEW_IP"
echo ""

if [ "$NEW_SSID" = "$WIFI_SSID" ]; then
    echo "======================================"
    echo "✓ WiFi Configuration Successful!"
    echo "======================================"
    echo ""
    echo "WiFi SSID: $NEW_SSID"
    echo "IP Address: $NEW_IP"
    echo "IP Method: $IP_CONFIG"
    echo ""
    echo "Note: SSH connection may disconnect if IP changed."
    echo "Reconnect using: ssh $ACTUAL_USER@$NEW_IP"
    echo ""
else
    echo "======================================"
    echo "✗ WiFi Connection Failed"
    echo "======================================"
    echo ""
    echo "Please check:"
    echo "- WiFi SSID is correct"
    echo "- WiFi password is correct"
    echo "- WiFi network is in range"
    echo ""
    exit 1
fi
