#!/bin/bash
#==============================================================================
# Cleanup Orphan Sensor Data
# Removes sensor_data records that reference non-existent devices
#==============================================================================

DB_PATH="${1:-$HOME/Gateway-Prasena/data/weatherstation.db}"

echo "=============================================="
echo "  Orphan Data Cleanup"
echo "=============================================="
echo ""

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Error: Database not found at $DB_PATH"
    exit 1
fi

echo "Database: $DB_PATH"
echo ""

# Count orphan records before cleanup
echo "Checking for orphan data..."
ORPHAN_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sensor_data WHERE device_id NOT IN (SELECT id FROM devices);")

if [ "$ORPHAN_COUNT" -eq 0 ]; then
    echo "✓ No orphan data found. Database is clean."
    exit 0
fi

echo "Found $ORPHAN_COUNT orphan records (sensor_data without matching device)"
echo ""

# Show breakdown by device_id
echo "Breakdown by device_id:"
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT
    device_id,
    COUNT(*) as record_count,
    MIN(timestamp) as oldest,
    MAX(timestamp) as newest
FROM sensor_data
WHERE device_id NOT IN (SELECT id FROM devices)
GROUP BY device_id;
SQL

echo ""
echo "These records will be DELETED."
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Delete orphan data
echo ""
echo "Deleting orphan data..."
sqlite3 "$DB_PATH" "DELETE FROM sensor_data WHERE device_id NOT IN (SELECT id FROM devices);"

# Verify cleanup
REMAINING=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sensor_data WHERE device_id NOT IN (SELECT id FROM devices);")

if [ "$REMAINING" -eq 0 ]; then
    echo "✓ Cleanup successful. Deleted $ORPHAN_COUNT orphan records."
else
    echo "Warning: $REMAINING orphan records still remain."
    exit 1
fi

# VACUUM to reclaim space
echo ""
echo "Running VACUUM to reclaim disk space..."
sqlite3 "$DB_PATH" "VACUUM;"
echo "✓ VACUUM completed"

echo ""
echo "=============================================="
echo "✓ Orphan data cleanup complete"
echo "=============================================="
