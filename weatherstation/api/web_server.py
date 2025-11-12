"""
Flask Web Server for Configuration Management
Provides REST API to configure sensors, upload settings, and PZEM mappings
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.logger import get_logger

logger = get_logger(__name__)


def create_app(
    config_path: str = './weatherstation/config/system_config.yaml',
    db_path: str = './data/weatherstation.db'
) -> Flask:
    """
    Create and configure Flask application

    Args:
        config_path: Path to system configuration file
        db_path: Path to database file

    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    app.config['CONFIG_PATH'] = config_path
    app.config['DB_PATH'] = db_path

    # Enable CORS for web interface
    CORS(app)

    # Initialize database
    db = DatabaseManager(db_path)

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================

    def load_config() -> Dict[str, Any]:
        """Load YAML configuration"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def save_config(config: Dict[str, Any]) -> None:
        """Save YAML configuration"""
        with open(config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    # =========================================================================
    # SENSOR/DEVICE MANAGEMENT
    # =========================================================================

    @app.route('/api/devices', methods=['GET'])
    def get_devices() -> Response:
        """Get all registered devices"""
        try:
            device_type = request.args.get('type')
            devices = db.get_enabled_devices(device_type)
            return jsonify({
                'status': 'success',
                'count': len(devices),
                'devices': devices
            })
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/devices/<device_id>', methods=['GET'])
    def get_device(device_id: str) -> Response:
        """Get specific device by ID"""
        try:
            device = db.get_device(device_id)
            if device:
                return jsonify({'status': 'success', 'device': device})
            else:
                return jsonify({'status': 'error', 'message': 'Device not found'}), 404
        except Exception as e:
            logger.error(f"Failed to get device {device_id}: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/devices', methods=['POST'])
    def register_device() -> Response:
        """
        Register new device

        Body:
        {
            "device_id": "01K9RSSBEVE5X1CV7ZGTB46MZP",
            "device_type": "pzem",
            "device_name": "TEGANGAN",
            "modbus_address": 1,
            "location": "Panel A",
            "enabled": true
        }
        """
        try:
            data = request.json
            required_fields = ['device_id', 'device_type']

            # Validate required fields
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }), 400

            # Register device
            success = db.register_device(**data)

            if success:
                return jsonify({
                    'status': 'success',
                    'message': f'Device {data["device_id"]} registered',
                    'device_id': data['device_id']
                }), 201
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to register device'
                }), 500

        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/devices/<device_id>', methods=['PUT'])
    def update_device(device_id: str) -> Response:
        """Update device configuration"""
        try:
            data = request.json
            data['device_id'] = device_id

            success = db.register_device(**data)  # INSERT OR REPLACE

            if success:
                return jsonify({
                    'status': 'success',
                    'message': f'Device {device_id} updated'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to update device'
                }), 500

        except Exception as e:
            logger.error(f"Failed to update device {device_id}: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # =========================================================================
    # PZEM MAPPING CONFIGURATION
    # =========================================================================

    @app.route('/api/config/pzem_mapping', methods=['GET'])
    def get_pzem_mapping() -> Response:
        """
        Get PZEM modbus address to sensor ID mapping

        Returns devices with modbus_address
        """
        try:
            devices = db.get_enabled_devices('pzem')
            mapping = [
                {
                    'modbus_address': d['modbus_address'],
                    'sensor_id': d['device_id'],
                    'device_name': d['device_name'],
                    'location': d['location']
                }
                for d in devices if d.get('modbus_address')
            ]
            return jsonify({
                'status': 'success',
                'count': len(mapping),
                'mapping': mapping
            })
        except Exception as e:
            logger.error(f"Failed to get PZEM mapping: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/config/pzem_mapping', methods=['POST'])
    def update_pzem_mapping() -> Response:
        """
        Update PZEM mapping

        Body:
        {
            "mapping": [
                {
                    "modbus_address": 1,
                    "sensor_id": "01K9RSSBEVE5X1CV7ZGTB46MZP",
                    "device_name": "TEGANGAN"
                },
                ...
            ]
        }
        """
        try:
            data = request.json
            mapping = data.get('mapping', [])

            if not mapping:
                return jsonify({
                    'status': 'error',
                    'message': 'No mapping provided'
                }), 400

            # Update each device
            updated = 0
            for item in mapping:
                success = db.register_device(
                    device_id=item['sensor_id'],
                    device_type='pzem',
                    device_name=item.get('device_name'),
                    modbus_address=item['modbus_address'],
                    location=item.get('location'),
                    enabled=True
                )
                if success:
                    updated += 1

            return jsonify({
                'status': 'success',
                'message': f'Updated {updated} PZEM mappings'
            })

        except Exception as e:
            logger.error(f"Failed to update PZEM mapping: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # =========================================================================
    # SYSTEM CONFIGURATION
    # =========================================================================

    @app.route('/api/config', methods=['GET'])
    def get_config() -> Response:
        """Get current system configuration"""
        try:
            config = load_config()
            return jsonify({'status': 'success', 'config': config})
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/config/upload', methods=['GET'])
    def get_upload_config() -> Response:
        """Get upload configuration"""
        try:
            config = load_config()
            return jsonify({
                'status': 'success',
                'upload': config.get('upload', {})
            })
        except Exception as e:
            logger.error(f"Failed to get upload config: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/config/upload', methods=['PUT'])
    def update_upload_config() -> Response:
        """
        Update upload configuration

        Body:
        {
            "main_server_url": "http://new-server.com/api",
            "interval": 120,
            "batch_size": 50
        }
        """
        try:
            config = load_config()
            new_upload_config = request.json

            # Update upload section
            if 'upload' not in config:
                config['upload'] = {}

            config['upload'].update(new_upload_config)

            # Save config
            save_config(config)

            logger.info(f"Upload config updated: {new_upload_config}")

            return jsonify({
                'status': 'success',
                'message': 'Upload configuration updated',
                'upload': config['upload']
            })

        except Exception as e:
            logger.error(f"Failed to update upload config: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/config/database', methods=['PUT'])
    def update_database_config() -> Response:
        """Update database configuration (cleanup settings)"""
        try:
            config = load_config()
            new_db_config = request.json

            if 'database' not in config:
                config['database'] = {}

            config['database'].update(new_db_config)
            save_config(config)

            logger.info(f"Database config updated: {new_db_config}")

            return jsonify({
                'status': 'success',
                'message': 'Database configuration updated',
                'database': config['database']
            })

        except Exception as e:
            logger.error(f"Failed to update database config: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # =========================================================================
    # SYSTEM STATUS & MONITORING
    # =========================================================================

    @app.route('/api/status', methods=['GET'])
    def get_status() -> Response:
        """Get system status"""
        try:
            stats = db.get_cleanup_stats()
            config = load_config()

            return jsonify({
                'status': 'success',
                'data': {
                    'pending_uploads': stats['total_pending'],
                    'uploaded_records': stats['total_uploaded'],
                    'by_type': stats['by_data_type'],
                    'upload_enabled': config.get('upload', {}).get('enabled', False),
                    'auto_cleanup_enabled': config.get('database', {}).get('auto_cleanup_enabled', False)
                }
            })

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/health', methods=['GET'])
    def health_check() -> Response:
        """Health check endpoint"""
        return jsonify({'status': 'ok', 'service': 'weatherstation-api'})

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @app.errorhandler(404)
    def not_found(error) -> Response:
        return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error) -> Response:
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

    return app


def main():
    """Main entry point for running web server"""
    import argparse

    parser = argparse.ArgumentParser(description='Weather Station Configuration API')
    parser.add_argument(
        '--config',
        default='./weatherstation/config/system_config.yaml',
        help='Path to config file'
    )
    parser.add_argument(
        '--db',
        default='./data/weatherstation.db',
        help='Path to database file'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )

    args = parser.parse_args()

    app = create_app(config_path=args.config, db_path=args.db)

    logger.info("=" * 60)
    logger.info("Weather Station Configuration API")
    logger.info("=" * 60)
    logger.info(f"Config: {args.config}")
    logger.info(f"Database: {args.db}")
    logger.info(f"Listening on: http://{args.host}:{args.port}")
    logger.info("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
