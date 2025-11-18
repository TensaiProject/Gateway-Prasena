"""
Sensor Error Code Definitions
Weather Station Gateway
"""

# Battery sensor error codes (1-99)
ERROR_BATTERY_TIMEOUT = 1           # Modbus communication timeout (RX too short)
ERROR_BATTERY_CRC_FAIL = 2          # CRC validation failed
ERROR_BATTERY_NO_RESPONSE = 3       # Device not responding
ERROR_BATTERY_IO_ERROR = 4          # General IO error
ERROR_BATTERY_INVALID_DATA = 5      # Data validation failed
ERROR_BATTERY_ADDRESS_MISMATCH = 6  # Address mismatch in response
ERROR_BATTERY_EXCEPTION = 7         # Modbus exception response

# Weather sensor error codes (100-199)
ERROR_WEATHER_HTTP_TIMEOUT = 101    # HTTP request timeout
ERROR_WEATHER_INVALID_JSON = 102    # Invalid JSON payload
ERROR_WEATHER_MISSING_FIELDS = 103  # Required fields missing

# Database error codes (200-299)
ERROR_DB_INSERT_FAIL = 201          # Database insert failed
ERROR_DB_CONNECTION_FAIL = 202      # Database connection failed

# MQTT error codes (300-399)
ERROR_MQTT_PUBLISH_FAIL = 301       # MQTT publish failed
ERROR_MQTT_DISCONNECTED = 302       # MQTT broker disconnected

# General error codes (400+)
ERROR_UNKNOWN = 999                 # Unknown error


def get_error_description(error_code: int) -> str:
    """
    Get human-readable error description

    Args:
        error_code: Error code number

    Returns:
        Error description string
    """
    descriptions = {
        # Battery errors
        1: "Modbus communication timeout (no response from sensor)",
        2: "CRC validation failed (data corruption)",
        3: "Device not responding",
        4: "General I/O error",
        5: "Data validation failed (out of range values)",
        6: "Address mismatch in Modbus response",
        7: "Modbus exception response from device",

        # Weather errors
        101: "HTTP request timeout",
        102: "Invalid JSON payload",
        103: "Required fields missing in data",

        # Database errors
        201: "Database insert failed",
        202: "Database connection failed",

        # MQTT errors
        301: "MQTT publish failed",
        302: "MQTT broker disconnected",

        # General
        999: "Unknown error"
    }
    return descriptions.get(error_code, f"Unknown error code: {error_code}")


def classify_battery_error(exception: Exception) -> int:
    """
    Classify battery sensor exception to error code

    Args:
        exception: Exception object

    Returns:
        Error code integer
    """
    error_msg = str(exception).lower()

    if isinstance(exception, TimeoutError) or "rx too short" in error_msg or "timeout" in error_msg:
        return ERROR_BATTERY_TIMEOUT
    elif "crc" in error_msg:
        return ERROR_BATTERY_CRC_FAIL
    elif "address mismatch" in error_msg:
        return ERROR_BATTERY_ADDRESS_MISMATCH
    elif "modbus exception" in error_msg:
        return ERROR_BATTERY_EXCEPTION
    elif isinstance(exception, IOError):
        return ERROR_BATTERY_IO_ERROR
    else:
        return ERROR_BATTERY_NO_RESPONSE
