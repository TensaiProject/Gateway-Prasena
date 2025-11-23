#!/bin/bash
# Gateway-Prasena WiFi Configuration Script (DHCP Mode)
# Phase 1: Change WiFi connection with DHCP
# Safe for remote (Tailscale) usage

set -e

echo "======================================"
echo "Gateway-Prasena WiFi Change (DHCP)"
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

echo "[1/4] Current WiFi Status"
echo "--------------------------------------"
CURRENT_SSID=$(iwgetid -r 2>/dev/null || echo "Not connected")
CURRENT_IP=$(hostname -I | awk '{print $1}')

# Detect WiFi interface
WIFI_INTERFACE=$(nmcli -t -f DEVICE,TYPE device | grep wifi | cut -d: -f1 | head -n1)

if [ -z "$WIFI_INTERFACE" ]; then
    echo "ERROR: WiFi interface not found!"
    exit 1
fi

echo "Current WiFi: $CURRENT_SSID"
echo "Current IP: $CURRENT_IP"
echo "WiFi Interface: $WIFI_INTERFACE"
echo ""

# Detect if connected via Tailscale (remote connection)
CURRENT_SSH_IP=$(echo $SSH_CONNECTION | awk '{print $3}' 2>/dev/null || echo "")
IS_REMOTE=false

if [[ "$CURRENT_SSH_IP" == 100.* ]]; then
    IS_REMOTE=true
    echo "⚠ NOTICE: Remote connection detected (Tailscale: $CURRENT_SSH_IP)"
    echo ""
fi

# Ask if user wants to scan
read -p "Scan for available WiFi networks? (y/n): " SCAN_CHOICE
if [ "$SCAN_CHOICE" = "y" ]; then
    echo ""
    echo "[2/4] Scanning WiFi Networks..."
    echo "--------------------------------------"
    # Add timeout to prevent hang
    timeout 15 nmcli device wifi list 2>/dev/null || echo "Scan timeout or failed"
    echo ""
else
    echo ""
    echo "[2/4] Skipping WiFi scan"
    echo ""
fi

# Get WiFi SSID
echo "[3/4] WiFi Credentials"
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

# Remote connection warning
if [ "$IS_REMOTE" = true ]; then
    echo "⚠ REMOTE CONNECTION WARNING"
    echo "--------------------------------------"
    echo "You are connected via Tailscale (VPN)."
    echo ""
    echo "Changing WiFi will:"
    echo "  1. Disconnect current WiFi ($CURRENT_SSID)"
    echo "  2. Disconnect Tailscale temporarily (~30-60 seconds)"
    echo "  3. Connect to new WiFi ($WIFI_SSID) with DHCP"
    echo "  4. Tailscale will auto-reconnect when internet restored"
    echo ""
    echo "After WiFi change:"
    echo "  - Wait 1-2 minutes for Tailscale to reconnect"
    echo "  - Reconnect SSH: ssh $ACTUAL_USER@$CURRENT_SSH_IP"
    echo "  - Then run 'static_ip.sh' to make IP static"
    echo ""
    read -p "Continue with WiFi change? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        echo "WiFi change cancelled."
        exit 0
    fi
    echo ""
fi

# Connect to WiFi with DHCP
echo "[4/4] Connecting to WiFi"
echo "--------------------------------------"
echo "SSID: $WIFI_SSID"
echo "IP Method: DHCP (automatic)"
echo ""

# Disconnect from current WiFi if connected
if [ "$CURRENT_SSID" != "Not connected" ]; then
    echo "Disconnecting from current WiFi: $CURRENT_SSID"
    nmcli connection down "$CURRENT_SSID" 2>/dev/null || true
    sleep 1
fi

# Connect to new WiFi with DHCP mode (with timeout)
echo "Connecting to $WIFI_SSID with DHCP..."

if [ -n "$WIFI_PASSWORD" ]; then
    timeout 60 nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD"
else
    timeout 60 nmcli device wifi connect "$WIFI_SSID"
fi

CONNECT_RESULT=$?

if [ $CONNECT_RESULT -eq 124 ]; then
    echo ""
    echo "======================================"
    echo "✗ Connection Timeout"
    echo "======================================"
    echo ""
    echo "WiFi connection timed out after 60 seconds."
    echo ""
    echo "Possible reasons:"
    echo "  - WiFi SSID not found or out of range"
    echo "  - Incorrect password"
    echo "  - WiFi using 5GHz band (Raspi may only support 2.4GHz)"
    echo "  - WiFi router not responding"
    echo ""
    echo "Reconnecting to old WiFi: $CURRENT_SSID"
    nmcli connection up "$CURRENT_SSID" 2>/dev/null || true
    exit 1
elif [ $CONNECT_RESULT -ne 0 ]; then
    echo ""
    echo "======================================"
    echo "✗ Connection Failed"
    echo "======================================"
    echo ""
    echo "Failed to connect to WiFi: $WIFI_SSID"
    echo ""
    echo "Reconnecting to old WiFi: $CURRENT_SSID"
    nmcli connection up "$CURRENT_SSID" 2>/dev/null || true
    exit 1
fi

# Wait for connection to establish
sleep 3

# Get new IP
NEW_SSID=$(iwgetid -r 2>/dev/null || echo "Not connected")
NEW_IP=$(ip -4 addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)

# Verify connection
if [ "$NEW_SSID" = "$WIFI_SSID" ] && [ -n "$NEW_IP" ]; then
    # Test internet connectivity
    echo ""
    echo "Testing internet connectivity..."
    if timeout 10 ping -c 2 8.8.8.8 &>/dev/null; then
        INTERNET_STATUS="✓ Working"
    else
        INTERNET_STATUS="⚠ Failed (no internet)"
    fi

    echo ""
    echo "======================================"
    echo "✓ WiFi Connected Successfully!"
    echo "======================================"
    echo ""
    echo "WiFi SSID: $NEW_SSID"
    echo "IP Address: $NEW_IP (DHCP)"
    echo "Internet: $INTERNET_STATUS"
    echo ""

    if [ "$IS_REMOTE" = true ]; then
        echo "Remote Connection Notice:"
        echo "--------------------------------------"
        echo "Your SSH connection will disconnect soon."
        echo ""
        echo "To reconnect:"
        echo "  1. Wait 1-2 minutes for Tailscale to reconnect"
        echo "  2. SSH: ssh $ACTUAL_USER@$CURRENT_SSH_IP"
        echo ""
        echo "After reconnecting, run Phase 2:"
        echo "  sudo bash scripts/static_ip.sh"
        echo ""
        echo "This will convert DHCP IP ($NEW_IP) to Static IP."
    else
        echo "Next Step:"
        echo "--------------------------------------"
        echo "WiFi is using DHCP (IP may change on reboot)."
        echo ""
        echo "To make IP static, run:"
        echo "  sudo bash scripts/static_ip.sh"
        echo ""
        echo "This will convert current IP ($NEW_IP) to Static IP."
    fi
    echo ""
else
    echo ""
    echo "======================================"
    echo "✗ WiFi Connection Failed"
    echo "======================================"
    echo ""
    echo "Expected SSID: $WIFI_SSID"
    echo "Actual SSID: $NEW_SSID"
    echo "IP Address: $NEW_IP"
    echo ""
    echo "Reconnecting to old WiFi: $CURRENT_SSID"
    nmcli connection up "$CURRENT_SSID" 2>/dev/null || true
    exit 1
fi
