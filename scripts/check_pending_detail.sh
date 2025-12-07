#!/bin/bash
echo "=========================================="
echo "📊 Pending Data Report"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

sqlite3 ~/Gateway-Prasena/data/weatherstation.db << 'SQL'
.mode column
.headers on
SELECT
    d.sensor_type as Type,
    COUNT(*) as Pending,
    strftime('%Y-%m-%d %H:%M', MIN(sd.timestamp)) as 'From (Time)',
    strftime('%Y-%m-%d %H:%M', MAX(sd.timestamp)) as 'To (Time)',
    CAST((julianday('now') - julianday(MIN(sd.timestamp))) * 24 AS INT) || 'h ' ||
    CAST(((julianday('now') - julianday(MIN(sd.timestamp))) * 24 * 60) % 60 AS INT) || 'm' as 'Age'
FROM sensor_data sd
JOIN devices d ON sd.device_id = d.id
WHERE sd.uploaded = 0
GROUP BY d.sensor_type;
SQL

echo ""
TOTAL=$(sqlite3 ~/Gateway-Prasena/data/weatherstation.db "SELECT COUNT(*) FROM sensor_data WHERE uploaded=0")
if [ "$TOTAL" -eq 0 ]; then
    echo "✅ Status: All data uploaded (0 pending)"
elif [ "$TOTAL" -lt 50 ]; then
    echo "🟢 Status: Low pending ($TOTAL records)"
elif [ "$TOTAL" -lt 200 ]; then
    echo "🟡 Status: Medium pending ($TOTAL records)"
else
    echo "🔴 Status: High pending ($TOTAL records) - CHECK MQTT!"
fi

echo "=========================================="
