-- ============================================================================
-- Weather Station & Energy Monitor System - Database Schema v2
-- ============================================================================

-- ============================================================================
-- DEVICES TABLE
-- Stores all registered devices (PZEM, weather stations, batteries)
-- ============================================================================
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    device_type TEXT NOT NULL,  -- 'pzem', 'weather_station', 'battery', 'mqtt'
    device_name TEXT,
    device_model TEXT,
    modbus_address INTEGER,  -- For PZEM devices (RS485 address)
    location TEXT,
    description TEXT,
    metadata TEXT,  -- JSON for extra device-specific data
    enabled INTEGER DEFAULT 1,
    online INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_enabled ON devices(enabled);
CREATE INDEX IF NOT EXISTS idx_devices_modbus ON devices(modbus_address);

-- ============================================================================
-- PZEM DATA TABLE
-- Stores energy monitoring data from PZEM sensors
-- ============================================================================
CREATE TABLE IF NOT EXISTS pzem_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    modbus_address INTEGER,

    -- Electrical measurements
    voltage REAL,           -- Volts (V)
    current REAL,           -- Amperes (A)
    power REAL,             -- Watts (W)
    energy REAL,            -- Kilowatt-hours (kWh)
    frequency REAL,         -- Hertz (Hz) - NULL for DC (PZEM-017)
    power_factor REAL,      -- Power factor (0-1) - NULL for DC

    -- Quality metrics
    read_quality INTEGER DEFAULT 100,  -- Read quality percentage
    error_code INTEGER DEFAULT 0,

    -- Upload tracking
    uploaded INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP,

    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_pzem_device ON pzem_data(device_id);
CREATE INDEX IF NOT EXISTS idx_pzem_uploaded ON pzem_data(uploaded);
CREATE INDEX IF NOT EXISTS idx_pzem_timestamp ON pzem_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_pzem_upload_pending ON pzem_data(uploaded, timestamp);

-- ============================================================================
-- WEATHER DATA TABLE
-- Stores weather station readings
-- ============================================================================
CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,

    -- Temperature
    temperature_outdoor REAL,  -- Celsius
    temperature_indoor REAL,   -- Celsius

    -- Humidity
    humidity_outdoor REAL,     -- Percentage
    humidity_indoor REAL,      -- Percentage

    -- Pressure
    pressure REAL,             -- hPa

    -- Wind
    wind_speed REAL,           -- m/s
    wind_direction REAL,       -- Degrees (0-360)
    wind_gust REAL,            -- m/s

    -- Rain
    rain_rate REAL,            -- mm/h
    rain_daily REAL,           -- mm
    rain_total REAL,           -- mm

    -- Light
    uv_index REAL,
    light_intensity REAL,      -- Lux

    -- Extra data (JSON)
    extra_data TEXT,

    -- Upload tracking
    uploaded INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP,

    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_weather_device ON weather_data(device_id);
CREATE INDEX IF NOT EXISTS idx_weather_uploaded ON weather_data(uploaded);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_data(timestamp);

-- ============================================================================
-- MQTT DATA TABLE
-- Stores data received via MQTT
-- ============================================================================
CREATE TABLE IF NOT EXISTS mqtt_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    topic TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON payload
    qos INTEGER,

    -- Upload tracking
    uploaded INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP,

    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mqtt_topic ON mqtt_data(topic);
CREATE INDEX IF NOT EXISTS idx_mqtt_uploaded ON mqtt_data(uploaded);
CREATE INDEX IF NOT EXISTS idx_mqtt_timestamp ON mqtt_data(timestamp);

-- ============================================================================
-- BATTERY DATA TABLE (uses PZEM-017 DC)
-- Battery monitoring via PZEM DC sensors
-- Note: Battery data is actually stored in pzem_data table
-- This table is for aggregated battery metrics
-- ============================================================================
CREATE TABLE IF NOT EXISTS battery_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,

    -- Battery metrics
    voltage REAL,              -- Volts
    current REAL,              -- Amperes (+ charging, - discharging)
    power REAL,                -- Watts
    state_of_charge REAL,      -- Percentage (calculated)
    temperature REAL,          -- Celsius

    -- Derived metrics
    charge_cycles INTEGER,
    health_percentage REAL,

    -- Upload tracking
    uploaded INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP,

    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_battery_device ON battery_data(device_id);
CREATE INDEX IF NOT EXISTS idx_battery_uploaded ON battery_data(uploaded);
CREATE INDEX IF NOT EXISTS idx_battery_timestamp ON battery_data(timestamp);

-- ============================================================================
-- ERROR LOGS TABLE
-- Device-specific error logging
-- ============================================================================
CREATE TABLE IF NOT EXISTS device_error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT,
    error_code INTEGER,
    extra_info TEXT,  -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_errors_device ON device_error_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON device_error_logs(timestamp);

-- ============================================================================
-- SYSTEM LOGS TABLE
-- General system event logging
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    module TEXT,
    message TEXT NOT NULL,
    device_id TEXT,
    extra_info TEXT,  -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    data_type TEXT NOT NULL,  -- 'pzem', 'weather', 'battery', 'mqtt'
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

-- System version
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2.0', 'Database schema version');

INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('created_at', datetime('now'), 'Database creation timestamp');
