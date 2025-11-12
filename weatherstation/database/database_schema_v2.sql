-- ============================================================================
-- Weather Station & Energy Monitor System - Database Schema v2
-- Optimized: Universal sensor_data table with device reference
-- ============================================================================

-- ============================================================================
-- DEVICES TABLE
-- Master reference for all sensors (battery, weather, etc)
-- Internal ID (auto increment) + External unique sensor_id
-- ============================================================================
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Internal ID (small, efficient)
    sensor_id TEXT UNIQUE NOT NULL,        -- External unique ID (ULID/UUID)
    sensor_type TEXT NOT NULL,             -- 'battery', 'weather'
    sensor_name TEXT,
    sensor_model TEXT,

    -- Sensor-specific attributes
    modbus_address INTEGER,                -- For RS485/Modbus sensors
    location TEXT,
    description TEXT,
    metadata TEXT,                         -- JSON for extra config

    -- Status
    enabled INTEGER DEFAULT 1,
    online INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    error_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_devices_sensor_id ON devices(sensor_id);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(sensor_type);
CREATE INDEX IF NOT EXISTS idx_devices_enabled ON devices(enabled);
CREATE INDEX IF NOT EXISTS idx_devices_modbus ON devices(modbus_address);

-- ============================================================================
-- SENSOR DATA TABLE (UNIVERSAL)
-- Single table for ALL sensor readings
-- Data stored as JSON for flexibility
-- ============================================================================
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,            -- Foreign key to devices.id (small int)

    -- Sensor readings (JSON)
    -- Example battery: {"voltage": 12.5, "current": 2.3, "power": 28.75, "energy": 1.234}
    -- Example weather: {"temp": 25.5, "humidity": 60, "wind_speed": 3.2}
    data TEXT NOT NULL,                    -- JSON data

    -- Quality metrics
    read_quality INTEGER DEFAULT 100,
    error_code INTEGER DEFAULT 0,

    -- Upload tracking
    uploaded INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP,

    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sensor_device ON sensor_data(device_id);
CREATE INDEX IF NOT EXISTS idx_sensor_uploaded ON sensor_data(uploaded);
CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_pending ON sensor_data(device_id, uploaded, timestamp);

-- ============================================================================
-- WEATHER DATA TABLE (OPTIONAL - for structured weather data)
-- If you prefer structured columns for weather instead of JSON
-- ============================================================================
CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,

    -- Temperature
    temperature_outdoor REAL,
    temperature_indoor REAL,

    -- Humidity
    humidity_outdoor REAL,
    humidity_indoor REAL,

    -- Pressure
    pressure REAL,

    -- Wind
    wind_speed REAL,
    wind_direction REAL,
    wind_gust REAL,

    -- Rain
    rain_rate REAL,
    rain_daily REAL,
    rain_total REAL,

    -- Light
    uv_index REAL,
    light_intensity REAL,

    -- Upload tracking
    uploaded INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_weather_device ON weather_data(device_id);
CREATE INDEX IF NOT EXISTS idx_weather_uploaded ON weather_data(uploaded);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_data(timestamp);

-- ============================================================================
-- ERROR LOGS TABLE
-- Device-specific error logging
-- ============================================================================
CREATE TABLE IF NOT EXISTS device_error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    error_type TEXT NOT NULL,
    error_message TEXT,
    error_code INTEGER,
    extra_info TEXT,  -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_errors_device ON device_error_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON device_error_logs(timestamp);

-- ============================================================================
-- SYSTEM LOGS TABLE
-- General system event logging
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    module TEXT,
    message TEXT NOT NULL,
    device_id INTEGER,
    extra_info TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp);

-- ============================================================================
-- UPLOAD LOGS TABLE
-- Track upload attempts and results
-- ============================================================================
CREATE TABLE IF NOT EXISTS upload_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    data_type TEXT NOT NULL,  -- 'battery', 'weather'
    record_count INTEGER,
    status TEXT NOT NULL,  -- 'success', 'failed', 'partial'
    http_status_code INTEGER,
    error_message TEXT,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_upload_logs_status ON upload_logs(status);
CREATE INDEX IF NOT EXISTS idx_upload_logs_timestamp ON upload_logs(upload_timestamp);

-- ============================================================================
-- SYSTEM CONFIG TABLE
-- Key-value store for system configuration
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2.0', 'Database schema version');

INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('created_at', datetime('now'), 'Database creation timestamp');
