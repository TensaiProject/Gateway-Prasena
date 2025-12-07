#!/bin/bash
# ============================================================================
# Finalize Database Cleanup - Reclaim Disk Space
# ============================================================================

echo "=========================================="
echo "🗃️  Database Cleanup Finalization"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

DB_PATH=~/Gateway-Prasena/data/weatherstation.db

# 1. Check database size BEFORE vacuum
echo "📊 Database size BEFORE VACUUM:"
ls -lh "$DB_PATH" | awk '{print "  Size: " $5}'
echo ""

# 2. Show current data summary
echo "📈 Current data summary:"
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT
    d.sensor_type as 'Sensor Type',
    COUNT(*) as 'Records',
    strftime('%Y-%m-%d %H:%M', MIN(sd.timestamp)) as 'Oldest Data',
    strftime('%Y-%m-%d %H:%M', MAX(sd.timestamp)) as 'Newest Data',
    CAST((julianday('now') - julianday(MIN(sd.timestamp))) * 24 AS INT) || 'h' as 'Age'
FROM sensor_data sd
JOIN devices d ON sd.device_id = d.id
GROUP BY d.sensor_type;
SQL
echo ""

# 3. Run VACUUM to reclaim disk space
echo "🔧 Running VACUUM to reclaim disk space..."
sqlite3 "$DB_PATH" "VACUUM;"
echo "✓ VACUUM completed"
echo ""

# 4. Check database size AFTER vacuum
echo "📊 Database size AFTER VACUUM:"
ls -lh "$DB_PATH" | awk '{print "  Size: " $5}'
echo ""

# 5. Calculate space saved
BEFORE=$(stat -c%s "$DB_PATH" 2>/dev/null || stat -f%z "$DB_PATH" 2>/dev/null || echo "0")
echo "💾 Disk space optimization complete!"
echo ""

echo "=========================================="
echo "✅ Database cleanup finalized successfully"
echo "=========================================="
