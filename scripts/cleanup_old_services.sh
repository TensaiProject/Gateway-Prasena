#!/bin/bash
# Cleanup Old Weather Station Services
# Kills any weatherstation processes NOT managed by systemd
# Run this if you see duplicate services running

echo "=== Weather Station Service Cleanup ==="
echo ""

# Get systemd-managed PIDs
SYSTEMD_PIDS=$(systemctl show battery-reader mqtt-publisher weather-receiver upload-service web-admin --property=MainPID | grep -v "MainPID=0" | cut -d= -f2 | tr '\n' ' ')

echo "Systemd-managed PIDs: $SYSTEMD_PIDS"
echo ""

# Get all weatherstation Python processes
ALL_PIDS=$(ps aux | grep "python3 -m weatherstation" | grep -v grep | awk '{print $2}')

echo "All weatherstation processes:"
ps aux | grep "python3 -m weatherstation" | grep -v grep | awk '{print "  PID", $2, "→", $11, $12, $13, $14}'
echo ""

# Kill processes that are NOT managed by systemd
KILLED=0
for pid in $ALL_PIDS; do
    if ! echo "$SYSTEMD_PIDS" | grep -q "$pid"; then
        echo "Killing old process: PID $pid"
        sudo kill $pid
        KILLED=$((KILLED + 1))
    fi
done

echo ""
if [ $KILLED -eq 0 ]; then
    echo "✅ No old processes found. All clean!"
else
    echo "✅ Killed $KILLED old process(es)"
    echo ""
    echo "Remaining processes:"
    sleep 1
    ps aux | grep "python3 -m weatherstation" | grep -v grep | awk '{print "  PID", $2, "→", $11, $12, $13, $14}'
fi

echo ""
echo "=== Systemd Services Status ==="
sudo systemctl is-active battery-reader mqtt-publisher weather-receiver upload-service | nl
