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


@app.route('/data', methods=['POST'])
def receive_data():
    """
    Receive weather station data via HTTP POST

    Expected JSON payload (example):
    {
        "sensor_id": "01K9RSSBEVE5X1CV7ZGTB46MZP",
        "temp": 25.5,
        "hum": 60.0,
        "press": 1013.25
    }
    """
    global config, db_manager

    try:
        # Parse JSON
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400

        raw_data = request.get_json()

        # Get sensor_id
        sensor_id = raw_data.get('sensor_id')
        if not sensor_id:
            return jsonify({'error': 'Missing sensor_id'}), 400

        # Parse and validate data
        weather_config = config.get('weather_station', {})
        field_mapping = weather_config.get('field_mapping', {})
        validation = weather_config.get('validation', {})

        parser = WeatherDataParser(field_mapping, validation)
        parsed_data = parser.parse(raw_data)

        if parsed_data is None:
            return jsonify({'error': 'Invalid data format'}), 400

        # Store to database
        success = db_manager.insert_sensor_data(sensor_id, parsed_data)

        if success:
            logger.info(f"Stored weather data from {sensor_id}")
            return jsonify({
                'status': 'success',
                'sensor_id': sensor_id,
                'timestamp': parsed_data['received_at']
            }), 200
        else:
            logger.error(f"Failed to store data for {sensor_id}")
            return jsonify({'error': 'Database error'}), 500

    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


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
