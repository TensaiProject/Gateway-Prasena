#!/bin/bash
#
# Start weatherstation services WITHOUT web admin
# Web admin will be handled by systemd socket activation
#

cd /home/weatherstation1/Gateway-Prasena

echo "Starting weatherstation services (no web admin)..."

# Start battery reader
nohup python3 -m weatherstation.main --service battery > /dev/null 2>&1 &
echo "Started: Battery Reader"

# Start weather receiver
nohup python3 -m weatherstation.main --service weather > /dev/null 2>&1 &
echo "Started: Weather Receiver"

# Start MQTT publisher
nohup python3 -m weatherstation.main --service mqtt > /dev/null 2>&1 &
echo "Started: MQTT Publisher"

sleep 2

# Show running services
echo ""
echo "Running services:"
ps aux | grep "[p]ython.*weatherstation" | awk '{print $2, $11, $12, $13}'

echo ""
echo "Socket activation status:"
sudo systemctl status web-admin.socket --no-pager | grep -E "Active:|Listen:"

echo ""
echo "✅ Services started!"
echo "Web admin: http://100.113.1.115:8080 (on-demand via socket)"
