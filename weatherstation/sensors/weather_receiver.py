#!/usr/bin/env python3
"""
Weather Station HTTP Receiver
Receives weather data via HTTP POST with dynamic field mapping
"""

import argparse
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

app = Flask(__name__)

# Global config and db (set by main())
config = None
db_manager = None


class WeatherDataParser:
    """
    Dynamic parser for weather station data
    Supports configurable field mapping and validation
    """

    def __init__(self, field_mapping: Dict[str, str], validation: Dict[str, Any]):
        """
        Args:
            field_mapping: Map internal field names to incoming field names
                          e.g., {"temperature": "temp", "humidity": "hum"}
            validation: Validation rules (required_fields, value_ranges)
        """
        self.field_mapping = field_mapping
        self.required_fields = validation.get('required_fields', [])
        self.value_ranges = validation.get('value_ranges', {})

    def parse(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse and validate incoming weather data

        Args:
            raw_data: Raw JSON data from weather station

        Returns:
            Parsed and validated data dict, or None if invalid
        """
        try:
            # Check required fields
            for field in self.required_fields:
                if field not in raw_data:
                    logger.error(f"Missing required field: {field}")
                    return None

            parsed = {}

            # Map fields according to configuration
            for internal_name, external_name in self.field_mapping.items():
                if external_name in raw_data:
                    value = raw_data[external_name]

                    # Validate range if configured
                    if internal_name in self.value_ranges:
                        min_val, max_val = self.value_ranges[internal_name]
                        if not (min_val <= value <= max_val):
                            logger.warning(
                                f"Value out of range for {internal_name}: "
                                f"{value} not in [{min_val}, {max_val}]"
                            )
                            # Still include but log warning

                    parsed[internal_name] = value

            # Include any unmapped fields (pass-through)
            for key, value in raw_data.items():
                if key not in self.field_mapping.values():
                    parsed[key] = value

            # Add metadata
            parsed['received_at'] = datetime.utcnow().isoformat() + 'Z'

            return parsed

        except Exception as e:
            logger.error(f"Parse error: {e}", exc_info=True)
            return None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'weather_receiver',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@app.route('/data/report/', methods=['GET'])
def receive_ecowitt_data():
    """
    Receive Ecowitt weather station data via HTTP GET

    Ecowitt protocol sends data as URL query parameters:
    GET /data/report/?PASSKEY=XXX&stationtype=EasyWeatherV1.6.4&dateutc=2025-11-15+11:30:45&tempf=77.5&humidity=65&...

    All fields are dynamic and optional (except stationtype and dateutc)
    """
    global config, db_manager

    try:
        # Get all query parameters as dict
        raw_data = request.args.to_dict()

        if not raw_data:
            return jsonify({'error': 'No data received'}), 400

        logger.debug(f"Received Ecowitt data: {raw_data}")

        # Get weather station config
        weather_config = config.get('weather_station', {})

        # Get sensor_id from config or use stationtype as fallback
        sensor_id = weather_config.get('sensor_id', raw_data.get('stationtype', 'weather_station_default'))

        # Parse all fields (fully dynamic - accept everything Ecowitt sends)
        parsed_data = {}

        # Common Ecowitt fields (optional, just for reference)
        # Temperature fields (Fahrenheit)
        if 'tempf' in raw_data:
            parsed_data['temperature_outdoor_f'] = float(raw_data['tempf'])
            parsed_data['temperature_outdoor_c'] = (float(raw_data['tempf']) - 32) * 5/9
        if 'tempinf' in raw_data:
            parsed_data['temperature_indoor_f'] = float(raw_data['tempinf'])
            parsed_data['temperature_indoor_c'] = (float(raw_data['tempinf']) - 32) * 5/9

        # Humidity
        if 'humidity' in raw_data:
            parsed_data['humidity_outdoor'] = int(raw_data['humidity'])
        if 'humidityin' in raw_data:
            parsed_data['humidity_indoor'] = int(raw_data['humidityin'])

        # Pressure (inches Hg)
        if 'baromrelin' in raw_data:
            parsed_data['pressure_inhg'] = float(raw_data['baromrelin'])
            parsed_data['pressure_hpa'] = float(raw_data['baromrelin']) * 33.8639
        if 'baromabsin' in raw_data:
            parsed_data['pressure_abs_inhg'] = float(raw_data['baromabsin'])

        # Wind (mph)
        if 'windspeedmph' in raw_data:
            parsed_data['wind_speed_mph'] = float(raw_data['windspeedmph'])
            parsed_data['wind_speed_kmh'] = float(raw_data['windspeedmph']) * 1.60934
        if 'windgustmph' in raw_data:
            parsed_data['wind_gust_mph'] = float(raw_data['windgustmph'])
            parsed_data['wind_gust_kmh'] = float(raw_data['windgustmph']) * 1.60934
        if 'winddir' in raw_data:
            parsed_data['wind_direction'] = int(raw_data['winddir'])

        # Rain (inches)
        if 'rainratein' in raw_data:
            parsed_data['rain_rate_in'] = float(raw_data['rainratein'])
            parsed_data['rain_rate_mm'] = float(raw_data['rainratein']) * 25.4
        if 'dailyrainin' in raw_data:
            parsed_data['rain_daily_in'] = float(raw_data['dailyrainin'])
            parsed_data['rain_daily_mm'] = float(raw_data['dailyrainin']) * 25.4
        if 'weeklyrainin' in raw_data:
            parsed_data['rain_weekly_in'] = float(raw_data['weeklyrainin'])
        if 'monthlyrainin' in raw_data:
            parsed_data['rain_monthly_in'] = float(raw_data['monthlyrainin'])
        if 'yearlyrainin' in raw_data:
            parsed_data['rain_yearly_in'] = float(raw_data['yearlyrainin'])

        # Solar & UV
        if 'solarradiation' in raw_data:
            parsed_data['solar_radiation'] = float(raw_data['solarradiation'])
        if 'uv' in raw_data:
            parsed_data['uv_index'] = int(raw_data['uv'])

        # Additional sensors (if present)
        # Ecowitt supports many sensor types, store all dynamically
        for key, value in raw_data.items():
            # Skip already processed and metadata fields
            if key in ['PASSKEY', 'stationtype', 'dateutc', 'model', 'freq']:
                continue

            # Store any additional fields not yet processed
            if key not in parsed_data:
                try:
                    # Try to convert to number
                    if '.' in str(value):
                        parsed_data[key] = float(value)
                    else:
                        parsed_data[key] = int(value)
                except (ValueError, TypeError):
                    # Keep as string if not a number
                    parsed_data[key] = str(value)

        # Add metadata
        parsed_data['stationtype'] = raw_data.get('stationtype', 'unknown')
        parsed_data['dateutc'] = raw_data.get('dateutc', datetime.utcnow().isoformat() + 'Z')
        parsed_data['received_at'] = datetime.utcnow().isoformat() + 'Z'

        # Store to database
        success = db_manager.insert_sensor_data(sensor_id, parsed_data)

        if success:
            logger.info(f"Stored Ecowitt weather data from {sensor_id} ({len(parsed_data)} fields)")
            # Ecowitt expects simple "OK" response
            return "OK", 200
        else:
            logger.error(f"Failed to store data for {sensor_id}")
            return "ERROR", 500

    except Exception as e:
        logger.error(f"Error handling Ecowitt request: {e}", exc_info=True)
        return "ERROR", 500


def main():
    """Main entry point"""
    global config, db_manager

    parser = argparse.ArgumentParser(description='Weather Station HTTP Receiver')
    parser.add_argument(
        '-c', '--config',
        default='./weatherstation/config/system_config.yaml',
        help='Path to config file'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Listen host (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        help='Listen port (default: from config)'
    )

    args = parser.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Setup logging
    log_config = config.get('logging', {})
    setup_logging(
        log_level=log_config.get('level', 'INFO'),
        log_file=log_config.get('weather_log_file', './logs/weather_receiver.log')
    )

    # Initialize database
    db_path = config.get('database', {}).get('path', './data/weatherstation.db')
    db_manager = DatabaseManager(db_path)

    # Get config
    weather_config = config.get('weather_station', {})
    enabled = weather_config.get('enabled', True)

    if not enabled:
        logger.info("Weather station receiver disabled in config")
        return 0

    port = args.port or weather_config.get('http_port', 5001)

    logger.info("=" * 60)
    logger.info("Weather Station HTTP Receiver starting...")
    logger.info(f"Listening on {args.host}:{port}")
    logger.info(f"Endpoint: POST /data")
    logger.info("=" * 60)

    try:
        app.run(
            host=args.host,
            port=port,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Received shutdown signal (Ctrl+C)")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        return 1

    logger.info("Weather Station Receiver stopped")
    return 0


if __name__ == '__main__':
    exit(main())
