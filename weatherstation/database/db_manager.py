"""
Database Manager for Weather Station System
Handles all database operations for devices, data storage, and uploads
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from weatherstation.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Manages all database operations for the weather station system
    """

    def __init__(self, db_path: str = './data/weatherstation.db'):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Create database directory if not exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database (create tables if not exist)
        self._initialize_database()

    @contextmanager
    def get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _initialize_database(self):
        """Initialize database schema if not exists"""
        schema_file = Path(__file__).parent / 'database_schema_v2.sql'

        if not schema_file.exists():
            logger.warning(f"Schema file not found: {schema_file}")
            return

        with self.get_connection() as conn:
            with open(schema_file, 'r') as f:
                conn.executescript(f.read())
        logger.info("Database initialized successfully")

    # ============================================================================
    # DEVICE MANAGEMENT
    # ============================================================================

    def register_device(
        self,
        sensor_id: str,
        sensor_type: str,
        sensor_name: str = None,
        sensor_model: str = None,
        modbus_address: int = None,
        location: str = None,
        description: str = None,
        enabled: bool = True,
        **kwargs
    ) -> bool:
        """
        Register new device or update existing

        Args:
            sensor_id: Unique sensor identifier (ULID/UUID)
            sensor_type: Type of sensor ('battery', 'weather')
            sensor_name: Human-readable name
            sensor_model: Sensor model
            modbus_address: Modbus address (for RS485 sensors)
            location: Physical location
            description: Description
            enabled: Enable sensor
            **kwargs: Additional metadata

        Returns:
            True if successful
        """
        try:
            metadata = json.dumps(kwargs) if kwargs else None

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO devices (
                        sensor_id, sensor_type, sensor_name, sensor_model,
                        modbus_address, location, description, metadata, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sensor_id, sensor_type, sensor_name, sensor_model,
                    modbus_address, location, description, metadata,
                    1 if enabled else 0
                ))

            logger.info(f"Registered device: {sensor_id} ({sensor_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to register device {sensor_id}: {e}")
            return False

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device by ID"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?",
                (device_id,)
            ).fetchone()

            return dict(row) if row else None

    def get_enabled_devices(self, sensor_type: str = None) -> List[Dict[str, Any]]:
        """
        Get all enabled devices

        Args:
            sensor_type: Filter by sensor type (optional)

        Returns:
            List of device dictionaries
        """
        with self.get_connection() as conn:
            if sensor_type:
                rows = conn.execute(
                    "SELECT * FROM devices WHERE enabled = 1 AND sensor_type = ?",
                    (sensor_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM devices WHERE enabled = 1"
                ).fetchall()

            return [dict(row) for row in rows]

    def update_device_status(
        self,
        device_id: str,
        online: bool = None,
        last_seen: str = None,
        error_count: int = None
    ) -> bool:
        """
        Update device status

        Args:
            device_id: Device ID
            online: Online status
            last_seen: Last seen timestamp
            error_count: Error count

        Returns:
            True if successful
        """
        try:
            updates = []
            params = []

            if online is not None:
                updates.append("online = ?")
                params.append(1 if online else 0)

            if last_seen is not None:
                updates.append("last_seen = ?")
                params.append(last_seen)

            if error_count is not None:
                updates.append("error_count = ?")
                params.append(error_count)

            if not updates:
                return True

            params.append(device_id)
            query = f"UPDATE devices SET {', '.join(updates)} WHERE device_id = ?"

            with self.get_connection() as conn:
                conn.execute(query, params)

            return True

        except Exception as e:
            logger.error(f"Failed to update device status {device_id}: {e}")
            return False

    # ============================================================================
    # SENSOR DATA (UNIVERSAL)
    # ============================================================================

    def insert_sensor_data(
        self,
        sensor_id: str,
        data: Dict[str, Any],
        read_quality: int = 100,
        error_code: int = 0
    ) -> bool:
        """
        Insert sensor data to universal sensor_data table

        Args:
            sensor_id: Sensor ID (external ULID/UUID)
            data: Sensor readings as dictionary (will be JSON encoded)
            read_quality: Quality percentage (0-100)
            error_code: Error code (0 = no error)

        Returns:
            True if successful
        """
        try:
            # Get internal device_id from sensor_id
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM devices WHERE sensor_id = ?",
                    (sensor_id,)
                ).fetchone()

                if not row:
                    logger.error(f"Sensor not found: {sensor_id}")
                    return False

                device_id = row['id']

                # Insert sensor data
                timestamp = data.pop('timestamp', datetime.utcnow().isoformat() + 'Z')
                data_json = json.dumps(data)

                conn.execute("""
                    INSERT INTO sensor_data (
                        device_id, data, read_quality, error_code, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    device_id,
                    data_json,
                    read_quality,
                    error_code,
                    timestamp
                ))

            return True

        except Exception as e:
            logger.error(f"Failed to insert sensor data for {sensor_id}: {e}")
            return False

    def get_pending_sensor_data(
        self,
        sensor_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get pending sensor data for upload

        Args:
            sensor_type: Filter by sensor type (optional)
            limit: Maximum records to return

        Returns:
            List of sensor data records with device info
        """
        with self.get_connection() as conn:
            if sensor_type:
                query = """
                    SELECT
                        sd.id,
                        d.sensor_id,
                        d.sensor_type,
                        sd.data,
                        sd.timestamp
                    FROM sensor_data sd
                    JOIN devices d ON sd.device_id = d.id
                    WHERE sd.uploaded = 0 AND d.sensor_type = ?
                    ORDER BY sd.timestamp ASC
                    LIMIT ?
                """
                rows = conn.execute(query, (sensor_type, limit)).fetchall()
            else:
                query = """
                    SELECT
                        sd.id,
                        d.sensor_id,
                        d.sensor_type,
                        sd.data,
                        sd.timestamp
                    FROM sensor_data sd
                    JOIN devices d ON sd.device_id = d.id
                    WHERE sd.uploaded = 0
                    ORDER BY sd.timestamp ASC
                    LIMIT ?
                """
                rows = conn.execute(query, (limit,)).fetchall()

            # Parse JSON data
            results = []
            for row in rows:
                record = dict(row)
                record['data'] = json.loads(record['data'])
                results.append(record)

            return results

    def delete_sensor_data(self, record_ids: List[int]) -> int:
        """
        Delete sensor data records by IDs (immediate delete after upload)

        Args:
            record_ids: List of record IDs to delete

        Returns:
            Number of records deleted
        """
        if not record_ids:
            return 0

        try:
            with self.get_connection() as conn:
                placeholders = ','.join('?' * len(record_ids))
                result = conn.execute(
                    f"DELETE FROM sensor_data WHERE id IN ({placeholders})",
                    record_ids
                )
                deleted = result.rowcount
                logger.info(f"Deleted {deleted} sensor data records")
                return deleted

        except Exception as e:
            logger.error(f"Failed to delete sensor data: {e}")
            return 0

    def mark_sensor_data_uploaded(self, record_ids: List[int]) -> bool:
        """Mark sensor data records as uploaded"""
        try:
            with self.get_connection() as conn:
                placeholders = ','.join('?' * len(record_ids))
                conn.execute(
                    f"UPDATE sensor_data SET uploaded = 1, uploaded_at = ? WHERE id IN ({placeholders})",
                    [datetime.utcnow().isoformat() + 'Z'] + record_ids
                )
            return True
        except Exception as e:
            logger.error(f"Failed to mark sensor data as uploaded: {e}")
            return False

    # ============================================================================
    # WEATHER DATA (Optional: structured table)
    # ============================================================================

    def insert_weather_data(self, device_id: str, data: Dict[str, Any]) -> bool:
        """Insert weather station data"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO weather_data (
                        device_id, temperature_outdoor, temperature_indoor,
                        humidity_outdoor, humidity_indoor, pressure,
                        wind_speed, wind_direction, wind_gust,
                        rain_rate, rain_daily, rain_total,
                        uv_index, light_intensity, extra_data, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_id,
                    data.get('temperature_outdoor'),
                    data.get('temperature_indoor'),
                    data.get('humidity_outdoor'),
                    data.get('humidity_indoor'),
                    data.get('pressure'),
                    data.get('wind_speed'),
                    data.get('wind_direction'),
                    data.get('wind_gust'),
                    data.get('rain_rate'),
                    data.get('rain_daily'),
                    data.get('rain_total'),
                    data.get('uv_index'),
                    data.get('light_intensity'),
                    json.dumps(data.get('extra_data', {})),
                    data.get('timestamp', datetime.utcnow().isoformat() + 'Z')
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to insert weather data: {e}")
            return False

    # ============================================================================
    # ERROR LOGGING
    # ============================================================================

    def log_device_error(
        self,
        device_id: str,
        error_type: str,
        error_message: str,
        error_code: int = None,
        extra_info: Dict[str, Any] = None
    ) -> bool:
        """Log device error"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO device_error_logs (
                        device_id, error_type, error_message,
                        error_code, extra_info
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    device_id,
                    error_type,
                    error_message,
                    error_code,
                    json.dumps(extra_info) if extra_info else None
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to log device error: {e}")
            return False

    def log_system(
        self,
        level: str,
        module: str,
        message: str,
        device_id: str = None,
        extra_info: Dict[str, Any] = None
    ) -> bool:
        """Log system event"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO system_logs (
                        level, module, message, device_id, extra_info
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    level,
                    module,
                    message,
                    device_id,
                    json.dumps(extra_info) if extra_info else None
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            return False

    # ============================================================================
    # UPLOAD LOGS
    # ============================================================================

    def log_upload(
        self,
        batch_id: str,
        data_type: str,
        record_count: int,
        status: str,
        http_status_code: int = None,
        error_message: str = None
    ) -> bool:
        """Log upload attempt"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO upload_logs (
                        batch_id, data_type, record_count, status,
                        http_status_code, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    batch_id, data_type, record_count, status,
                    http_status_code, error_message
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to log upload: {e}")
            return False

    # ============================================================================
    # CONFIGURATION
    # ============================================================================

    def get_config(self, key: str) -> Optional[str]:
        """Get configuration value"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT config_value FROM system_config WHERE config_key = ?",
                (key,)
            ).fetchone()
            return row['config_value'] if row else None

    def set_config(self, key: str, value: str) -> bool:
        """Set configuration value"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO system_config (config_key, config_value)
                    VALUES (?, ?)
                """, (key, value))
            return True
        except Exception as e:
            logger.error(f"Failed to set config {key}: {e}")
            return False

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_pending_upload_count(self, data_type: str = None) -> int:
        """Get count of pending uploads"""
        with self.get_connection() as conn:
            if data_type == 'pzem':
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM pzem_data WHERE uploaded = 0"
                ).fetchone()
            elif data_type == 'weather':
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM weather_data WHERE uploaded = 0"
                ).fetchone()
            else:
                # Total - use sensor_data table
                row = conn.execute("""
                    SELECT COUNT(*) as count FROM sensor_data WHERE uploaded = 0
                """).fetchone()

            return row['count'] if row else 0

    # ============================================================================
    # DATA CLEANUP
    # ============================================================================

    def delete_uploaded_data(
        self,
        data_type: str,
        days_old: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Delete uploaded data older than specified days

        Args:
            data_type: Type of data ('battery', 'weather')
            days_old: Delete data older than this many days
            dry_run: If True, only count records without deleting

        Returns:
            Dictionary with deletion statistics
        """
        try:
            # Legacy support - will be removed
            table_map = {
                'pzem': 'pzem_data',
                'weather': 'weather_data',
                'battery': 'battery_data'
            }

            if data_type not in table_map:
                logger.error(f"Invalid data_type: {data_type}")
                return {'error': 'Invalid data_type'}

            table_name = table_map[data_type]

            with self.get_connection() as conn:
                # Check if table exists
                table_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                ).fetchone()

                if not table_check:
                    logger.debug(f"Table {table_name} does not exist, skipping")
                    return {
                        'data_type': data_type,
                        'records_deleted': 0,
                        'dry_run': dry_run,
                        'skipped': True
                    }

                # Count records to be deleted
                count_query = f"""
                    SELECT COUNT(*) as count
                    FROM {table_name}
                    WHERE uploaded = 1
                    AND timestamp < datetime('now', '-{days_old} days')
                """
                count_row = conn.execute(count_query).fetchone()
                records_count = count_row['count'] if count_row else 0

                if records_count == 0:
                    logger.info(f"No {data_type} records to delete (older than {days_old} days)")
                    return {
                        'data_type': data_type,
                        'records_deleted': 0,
                        'dry_run': dry_run
                    }

                # Get timestamp range
                range_query = f"""
                    SELECT
                        MIN(timestamp) as oldest,
                        MAX(timestamp) as newest
                    FROM {table_name}
                    WHERE uploaded = 1
                    AND timestamp < datetime('now', '-{days_old} days')
                """
                range_row = conn.execute(range_query).fetchone()

                if not dry_run:
                    # Actually delete the records
                    delete_query = f"""
                        DELETE FROM {table_name}
                        WHERE uploaded = 1
                        AND timestamp < datetime('now', '-{days_old} days')
                    """
                    conn.execute(delete_query)
                    logger.info(
                        f"Deleted {records_count} {data_type} records "
                        f"older than {days_old} days"
                    )
                else:
                    logger.info(
                        f"DRY RUN: Would delete {records_count} {data_type} records "
                        f"older than {days_old} days"
                    )

                return {
                    'data_type': data_type,
                    'records_deleted': records_count,
                    'days_old': days_old,
                    'oldest_timestamp': dict(range_row)['oldest'] if range_row else None,
                    'newest_timestamp': dict(range_row)['newest'] if range_row else None,
                    'dry_run': dry_run
                }

        except Exception as e:
            logger.error(f"Failed to delete {data_type} data: {e}")
            return {
                'error': str(e),
                'data_type': data_type,
                'records_deleted': 0
            }

    def cleanup_all_uploaded_data(
        self,
        days_old: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Cleanup all uploaded data older than specified days

        Args:
            days_old: Delete data older than this many days
            dry_run: If True, only count records without deleting

        Returns:
            Dictionary with cleanup statistics for all data types
        """
        logger.info("=" * 60)
        logger.info(f"Starting cleanup: data older than {days_old} days")
        if dry_run:
            logger.info("DRY RUN MODE - No data will be deleted")
        logger.info("=" * 60)

        results = {
            'total_records_deleted': 0,
            'data_types': {},
            'dry_run': dry_run,
            'days_old': days_old
        }

        # Cleanup each data type (legacy tables)
        for data_type in ['pzem', 'weather', 'battery']:
            result = self.delete_uploaded_data(data_type, days_old, dry_run)
            results['data_types'][data_type] = result
            results['total_records_deleted'] += result.get('records_deleted', 0)

        # Log cleanup summary
        if not dry_run and results['total_records_deleted'] > 0:
            self.log_system(
                level='INFO',
                module='db_cleanup',
                message=f"Cleanup complete: deleted {results['total_records_deleted']} records",
                extra_info=results
            )

        logger.info("=" * 60)
        logger.info(f"Cleanup complete: {results['total_records_deleted']} records deleted")
        logger.info("=" * 60)

        return results

    def get_cleanup_stats(self) -> Dict[str, Any]:
        """
        Get statistics about data that can be cleaned up

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            'total_uploaded': 0,
            'total_pending': 0,
            'by_data_type': {}
        }

        with self.get_connection() as conn:
            # Check which tables exist
            existing_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            existing_table_names = [t['name'] for t in existing_tables]

            # Stats for each data type (legacy tables)
            for data_type, table_name in [
                ('pzem', 'pzem_data'),
                ('weather', 'weather_data'),
                ('battery', 'battery_data')
            ]:
                # Skip if table doesn't exist
                if table_name not in existing_table_names:
                    stats['by_data_type'][data_type] = {
                        'uploaded': 0,
                        'pending': 0,
                        'oldest_uploaded': None
                    }
                    continue

                # Count uploaded records
                uploaded_row = conn.execute(
                    f"SELECT COUNT(*) as count FROM {table_name} WHERE uploaded = 1"
                ).fetchone()

                # Count pending records
                pending_row = conn.execute(
                    f"SELECT COUNT(*) as count FROM {table_name} WHERE uploaded = 0"
                ).fetchone()

                # Oldest uploaded record
                oldest_row = conn.execute(
                    f"""SELECT MIN(timestamp) as oldest
                        FROM {table_name}
                        WHERE uploaded = 1"""
                ).fetchone()

                uploaded_count = uploaded_row['count'] if uploaded_row else 0
                pending_count = pending_row['count'] if pending_row else 0

                stats['by_data_type'][data_type] = {
                    'uploaded': uploaded_count,
                    'pending': pending_count,
                    'oldest_uploaded': dict(oldest_row)['oldest'] if oldest_row else None
                }

                stats['total_uploaded'] += uploaded_count
                stats['total_pending'] += pending_count

        return stats
