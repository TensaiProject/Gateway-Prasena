"""
Web Admin Service for Weather Station Gateway
Provides web interface for configuration and device management
"""

import os
import sys
import socket
import yaml
import logging
import threading
import time
import signal
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.serving import run_simple

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.ulid_generator import generate_ulid

logger = logging.getLogger(__name__)


class WebAdminService:
    """
    Web Admin Service - Flask-based web interface

    Features:
    - Dashboard: System status, recent data, service health
    - Settings: Configure intervals (battery, MQTT, upload)
    - Devices: Register and manage sensors
    - Real-time data display
    """

    def __init__(self, config: Dict[str, Any], db_path: str = './data/weatherstation.db'):
        """
        Initialize Web Admin Service

        Args:
            config: System configuration dictionary
            db_path: Path to SQLite database
        """
        self.config = config
        self.db = DatabaseManager(db_path)

        # Web admin configuration
        web_config = config.get('web_admin', {})
        self.host = web_config.get('host', '0.0.0.0')
        self.port = web_config.get('port', 8080)
        self.debug = web_config.get('debug', False)

        # Idle timeout configuration (default: 60 seconds)
        self.idle_timeout = web_config.get('idle_timeout', 60)
        self.last_request_time = time.time()
        self.idle_check_thread = None

        # Config file path
        self.config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'system_config.yaml'
        )

        # Flask app setup
        self.app = Flask(
            __name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', 'static')
        )
        CORS(self.app)  # Enable CORS for API calls

        self.running = False
        self.server_thread = None
        self.server = None

        # Register idle timeout middleware
        @self.app.before_request
        def update_last_request_time():
            """Update last request time on every request"""
            self.last_request_time = time.time()

        # Register routes
        self._register_routes()

        logger.info(f"Web Admin Service initialized on {self.host}:{self.port} with {self.idle_timeout}s idle timeout")

    def _register_routes(self):
        """Register all Flask routes"""

        # ============================================
        # HTML PAGES
        # ============================================

        @self.app.route('/')
        def dashboard():
            """Dashboard page - system status and recent data"""
            return render_template('dashboard.html')

        @self.app.route('/settings')
        def settings():
            """Settings page - configure intervals"""
            return render_template('settings.html')

        @self.app.route('/devices')
        def devices():
            """Devices page - manage sensors"""
            return render_template('devices.html')

        # ============================================
        # API ENDPOINTS - CONFIG MANAGEMENT
        # ============================================

        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            """Get full system configuration"""
            try:
                config = self._read_config()
                return jsonify({
                    'success': True,
                    'data': config
                })
            except Exception as e:
                logger.error(f"Error reading config: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/config/intervals', methods=['GET'])
        def get_intervals():
            """Get all configurable intervals"""
            try:
                config = self._read_config()
                intervals = {
                    'battery_sensors': {
                        'sampling_rate': config.get('battery_sensors', {}).get('sampling_rate', 1),
                        'poll_interval': config.get('battery_sensors', {}).get('poll_interval', 10),
                        'aggregation_window': config.get('battery_sensors', {}).get('aggregation_window', 300)
                    },
                    'mqtt': {
                        'publisher': {
                            'poll_interval': config.get('mqtt', {}).get('publisher', {}).get('poll_interval', 5),
                            'batch_size': config.get('mqtt', {}).get('publisher', {}).get('batch_size', 10)
                        }
                    },
                    'upload': {
                        'interval': config.get('upload', {}).get('interval', 60)
                    },
                    'database': {
                        'backup_interval': config.get('database', {}).get('backup_interval', 86400)
                    }
                }
                return jsonify({
                    'success': True,
                    'data': intervals
                })
            except Exception as e:
                logger.error(f"Error reading intervals: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/config/intervals', methods=['PUT'])
        def update_intervals():
            """Update configurable intervals"""
            try:
                new_intervals = request.json

                # Validate intervals
                validation_error = self._validate_intervals(new_intervals)
                if validation_error:
                    return jsonify({
                        'success': False,
                        'error': validation_error
                    }), 400

                # Read current config
                config = self._read_config()

                # Update intervals
                if 'battery_sensors' in new_intervals:
                    if 'battery_sensors' not in config:
                        config['battery_sensors'] = {}
                    config['battery_sensors'].update(new_intervals['battery_sensors'])

                if 'mqtt' in new_intervals and 'publisher' in new_intervals['mqtt']:
                    if 'mqtt' not in config:
                        config['mqtt'] = {}
                    if 'publisher' not in config['mqtt']:
                        config['mqtt']['publisher'] = {}
                    config['mqtt']['publisher'].update(new_intervals['mqtt']['publisher'])

                if 'upload' in new_intervals:
                    if 'upload' not in config:
                        config['upload'] = {}
                    config['upload'].update(new_intervals['upload'])

                if 'database' in new_intervals:
                    if 'database' not in config:
                        config['database'] = {}
                    config['database'].update(new_intervals['database'])

                # Write config back
                self._write_config(config)

                logger.info(f"Intervals updated successfully: {new_intervals}")

                return jsonify({
                    'success': True,
                    'message': 'Intervals updated successfully. Restart services for changes to take effect.',
                    'data': new_intervals
                })
            except Exception as e:
                logger.error(f"Error updating intervals: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/config/mqtt', methods=['GET'])
        def get_mqtt_config():
            """Get MQTT connection configuration"""
            try:
                config = self._read_config()
                mqtt_config = config.get('mqtt', {})

                # Return MQTT connection settings (mask password for security)
                mqtt_data = {
                    'broker_host': mqtt_config.get('broker_host', ''),
                    'broker_port': mqtt_config.get('broker_port', 1883),
                    'username': mqtt_config.get('username', ''),
                    'password': mqtt_config.get('password', ''),
                    'qos': mqtt_config.get('qos', 1),
                    'keepalive': mqtt_config.get('keepalive', 60),
                    'client_id': mqtt_config.get('client_id', '')
                }

                return jsonify({
                    'success': True,
                    'data': mqtt_data
                })
            except Exception as e:
                logger.error(f"Error reading MQTT config: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/config/mqtt', methods=['PUT'])
        def update_mqtt_config():
            """Update MQTT connection configuration"""
            try:
                new_mqtt = request.json

                # Validate MQTT config
                validation_error = self._validate_mqtt_config(new_mqtt)
                if validation_error:
                    return jsonify({
                        'success': False,
                        'error': validation_error
                    }), 400

                # Read current config
                config = self._read_config()

                # Ensure mqtt section exists
                if 'mqtt' not in config:
                    config['mqtt'] = {}

                # Update MQTT settings
                if 'broker_host' in new_mqtt:
                    config['mqtt']['broker_host'] = new_mqtt['broker_host']
                    # Also update broker_url for compatibility
                    port = new_mqtt.get('broker_port', config['mqtt'].get('broker_port', 1883))
                    config['mqtt']['broker_url'] = f"mqtt://{new_mqtt['broker_host']}:{port}"

                if 'broker_port' in new_mqtt:
                    config['mqtt']['broker_port'] = new_mqtt['broker_port']
                    # Update broker_url
                    host = config['mqtt'].get('broker_host', 'localhost')
                    config['mqtt']['broker_url'] = f"mqtt://{host}:{new_mqtt['broker_port']}"

                if 'username' in new_mqtt:
                    config['mqtt']['username'] = new_mqtt['username']

                if 'password' in new_mqtt:
                    config['mqtt']['password'] = new_mqtt['password']

                if 'qos' in new_mqtt:
                    config['mqtt']['qos'] = new_mqtt['qos']

                if 'keepalive' in new_mqtt:
                    config['mqtt']['keepalive'] = new_mqtt['keepalive']

                if 'client_id' in new_mqtt:
                    if new_mqtt['client_id']:
                        config['mqtt']['client_id'] = new_mqtt['client_id']
                    elif 'client_id' in config['mqtt']:
                        # Remove client_id if empty (use auto-generated)
                        del config['mqtt']['client_id']

                # Write config back
                self._write_config(config)

                logger.info(f"MQTT config updated successfully")

                return jsonify({
                    'success': True,
                    'message': 'MQTT configuration updated. Restart services for changes to take effect.'
                })
            except Exception as e:
                logger.error(f"Error updating MQTT config: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        # ============================================
        # API ENDPOINTS - DEVICE MANAGEMENT
        # ============================================

        @self.app.route('/api/devices', methods=['GET'])
        def get_devices():
            """Get all registered devices"""
            try:
                devices = self.db.get_all_devices()

                # Map sensor_* fields to device_* for frontend compatibility
                mapped_devices = []
                for device in devices:
                    mapped_device = {
                        'device_id': device.get('sensor_id'),
                        'device_type': device.get('sensor_type'),
                        'device_name': device.get('sensor_name'),
                        'modbus_address': device.get('modbus_address'),
                        'location': device.get('location'),
                        'enabled': device.get('enabled'),
                        'online': device.get('online'),
                        'created_at': device.get('created_at'),
                        'updated_at': device.get('updated_at')
                    }
                    mapped_devices.append(mapped_device)

                return jsonify({
                    'success': True,
                    'data': mapped_devices
                })
            except Exception as e:
                logger.error(f"Error getting devices: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/devices/<device_id>', methods=['GET'])
        def get_device(device_id):
            """Get device details by ID"""
            try:
                device = self.db.get_device_by_id(device_id)
                if device:
                    return jsonify({
                        'success': True,
                        'data': device
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Device not found'
                    }), 404
            except Exception as e:
                logger.error(f"Error getting device {device_id}: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/devices/register', methods=['POST'])
        def register_device():
            """Register a new device"""
            try:
                device_data = request.json

                # Validate device data
                validation_error = self._validate_device(device_data)
                if validation_error:
                    return jsonify({
                        'success': False,
                        'error': validation_error
                    }), 400

                # Generate ULID
                sensor_id = generate_ulid()
                sensor_type = device_data['type']
                sensor_name = device_data.get('name', f"{sensor_type.capitalize()} Sensor")
                modbus_address = device_data.get('modbus_address')

                # Register device in database
                self.db.register_device(
                    sensor_id=sensor_id,
                    sensor_type=sensor_type,
                    sensor_name=sensor_name,
                    modbus_address=modbus_address
                )

                logger.info(f"Device registered: {sensor_id} ({sensor_type})")

                return jsonify({
                    'success': True,
                    'message': f'Device registered successfully',
                    'data': {
                        'device_id': sensor_id,
                        'device_type': sensor_type,
                        'device_name': sensor_name,
                        'modbus_address': modbus_address
                    }
                }), 201
            except Exception as e:
                logger.error(f"Error registering device: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/devices/<device_id>', methods=['DELETE'])
        def delete_device(device_id):
            """Delete a device"""
            try:
                # Check if device exists
                device = self.db.get_device_by_id(device_id)
                if not device:
                    return jsonify({
                        'success': False,
                        'error': 'Device not found'
                    }), 404

                # Delete device
                self.db.delete_device(device_id)

                logger.info(f"Device deleted: {device_id}")

                return jsonify({
                    'success': True,
                    'message': 'Device deleted successfully'
                })
            except Exception as e:
                logger.error(f"Error deleting device {device_id}: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/devices/scan', methods=['GET'])
        def scan_devices():
            """Scan for available modbus devices"""
            try:
                # Import scanner
                from weatherstation.sensors.battery_reader import BatteryReaderService

                # Get modbus config
                modbus_config = self.config.get('modbus', {})

                # Create temporary battery reader for scanning
                scanner = BatteryReaderService(
                    config=self.config,
                    db_path='./data/weatherstation.db'
                )

                # Scan addresses 1-10
                found_devices = []
                for address in range(1, 11):
                    try:
                        # Try to read from this address
                        data = scanner.read_sensor(address)
                        if data:
                            found_devices.append({
                                'address': address,
                                'voltage': data.get('voltage'),
                                'current': data.get('current'),
                                'power': data.get('power'),
                                'energy': data.get('energy')
                            })
                    except Exception as e:
                        # Address not responding
                        continue

                logger.info(f"Modbus scan complete. Found {len(found_devices)} devices")

                return jsonify({
                    'success': True,
                    'data': found_devices
                })
            except Exception as e:
                logger.error(f"Error scanning devices: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        # ============================================
        # API ENDPOINTS - SYSTEM STATUS (Simplified)
        # ============================================

        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Get basic system status"""
            try:
                # Get device count
                devices = self.db.get_all_devices()
                battery_count = len([d for d in devices if d.get('sensor_type') == 'battery'])
                weather_count = len([d for d in devices if d.get('sensor_type') == 'weather'])

                return jsonify({
                    'success': True,
                    'data': {
                        'total_devices': len(devices),
                        'battery_sensors': battery_count,
                        'weather_stations': weather_count
                    }
                })
            except Exception as e:
                logger.error(f"Error getting status: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/system/restart', methods=['POST'])
        def restart_services():
            """Restart all weather station services"""
            try:
                import subprocess

                # Get service names from config
                services = ['battery-reader', 'mqtt-publisher', 'weather-receiver', 'upload-service']

                # Restart each service
                restarted = []
                failed = []

                for service in services:
                    try:
                        # Use sudo systemctl restart
                        result = subprocess.run(
                            ['sudo', 'systemctl', 'restart', f'{service}.service'],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        if result.returncode == 0:
                            restarted.append(service)
                            logger.info(f"Service restarted: {service}")
                        else:
                            failed.append(f"{service}: {result.stderr}")
                            logger.error(f"Failed to restart {service}: {result.stderr}")
                    except Exception as e:
                        failed.append(f"{service}: {str(e)}")
                        logger.error(f"Error restarting {service}: {e}")

                if failed:
                    return jsonify({
                        'success': False,
                        'message': f'Some services failed to restart',
                        'data': {
                            'restarted': restarted,
                            'failed': failed
                        }
                    }), 500

                return jsonify({
                    'success': True,
                    'message': f'All services restarted successfully',
                    'data': {
                        'restarted': restarted
                    }
                })
            except Exception as e:
                logger.error(f"Error restarting services: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

    # ============================================
    # HELPER METHODS
    # ============================================

    def _read_config(self) -> Dict[str, Any]:
        """Read system configuration from YAML file"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _write_config(self, config: Dict[str, Any]):
        """Write system configuration to YAML file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def _validate_intervals(self, intervals: Dict[str, Any]) -> Optional[str]:
        """
        Validate interval values

        Returns:
            Error message if invalid, None if valid
        """
        try:
            # Validate battery intervals
            if 'battery_sensors' in intervals:
                battery = intervals['battery_sensors']
                if 'sampling_rate' in battery:
                    if not (0 < battery['sampling_rate'] <= 60):
                        return "Battery sampling_rate must be between 1-60 seconds"
                if 'poll_interval' in battery:
                    if not (1 <= battery['poll_interval'] <= 3600):
                        return "Battery poll_interval must be between 1-3600 seconds"
                if 'aggregation_window' in battery:
                    if not (15 <= battery['aggregation_window'] <= 86400):
                        return "Battery aggregation_window must be between 15-86400 seconds"

            # Validate MQTT intervals
            if 'mqtt' in intervals and 'publisher' in intervals['mqtt']:
                mqtt = intervals['mqtt']['publisher']
                if 'poll_interval' in mqtt:
                    if not (1 <= mqtt['poll_interval'] <= 300):
                        return "MQTT poll_interval must be between 1-300 seconds"
                if 'batch_size' in mqtt:
                    if not (1 <= mqtt['batch_size'] <= 100):
                        return "MQTT batch_size must be between 1-100 records"

            # Validate upload interval
            if 'upload' in intervals:
                if 'interval' in intervals['upload']:
                    if not (10 <= intervals['upload']['interval'] <= 3600):
                        return "Upload interval must be between 10-3600 seconds"

            # Validate database interval
            if 'database' in intervals:
                if 'backup_interval' in intervals['database']:
                    if not (3600 <= intervals['database']['backup_interval'] <= 604800):
                        return "Database backup_interval must be between 3600-604800 seconds"

            return None
        except Exception as e:
            return f"Validation error: {str(e)}"

    def _validate_mqtt_config(self, mqtt_data: Dict[str, Any]) -> Optional[str]:
        """
        Validate MQTT configuration values

        Returns:
            Error message if invalid, None if valid
        """
        try:
            # Validate broker_host
            if 'broker_host' in mqtt_data:
                host = mqtt_data['broker_host']
                if not host or not isinstance(host, str):
                    return "Broker host is required"
                if len(host) > 255:
                    return "Broker host must be less than 255 characters"

            # Validate broker_port
            if 'broker_port' in mqtt_data:
                port = mqtt_data['broker_port']
                if not isinstance(port, int) or not (1 <= port <= 65535):
                    return "Broker port must be between 1-65535"

            # Validate username
            if 'username' in mqtt_data:
                username = mqtt_data['username']
                if not isinstance(username, str):
                    return "Username must be a string"
                if len(username) > 255:
                    return "Username must be less than 255 characters"

            # Validate password
            if 'password' in mqtt_data:
                password = mqtt_data['password']
                if not isinstance(password, str):
                    return "Password must be a string"

            # Validate QoS
            if 'qos' in mqtt_data:
                qos = mqtt_data['qos']
                if not isinstance(qos, int) or qos not in [0, 1, 2]:
                    return "QoS must be 0, 1, or 2"

            # Validate keepalive
            if 'keepalive' in mqtt_data:
                keepalive = mqtt_data['keepalive']
                if not isinstance(keepalive, int) or not (10 <= keepalive <= 3600):
                    return "Keepalive must be between 10-3600 seconds"

            # Validate client_id
            if 'client_id' in mqtt_data:
                client_id = mqtt_data['client_id']
                if client_id and not isinstance(client_id, str):
                    return "Client ID must be a string"
                if client_id and len(client_id) > 255:
                    return "Client ID must be less than 255 characters"

            return None
        except Exception as e:
            return f"Validation error: {str(e)}"

    def _validate_device(self, device_data: Dict[str, Any]) -> Optional[str]:
        """
        Validate device registration data

        Returns:
            Error message if invalid, None if valid
        """
        # Check required fields
        if 'type' not in device_data:
            return "Device type is required"

        device_type = device_data['type']

        # Normalize device type
        if device_type == 'pzem':
            device_type = 'battery'
            device_data['type'] = 'battery'
        elif device_type == 'weather_station':
            device_type = 'weather'
            device_data['type'] = 'weather'

        # Validate device type
        if device_type not in ['battery', 'weather']:
            return "Device type must be 'battery' or 'weather'"

        # Battery sensors require modbus address
        if device_type == 'battery':
            if 'modbus_address' not in device_data:
                return "Modbus address is required for battery sensors"

            modbus_address = device_data['modbus_address']
            if not isinstance(modbus_address, int) or not (1 <= modbus_address <= 247):
                return "Modbus address must be between 1-247"

            # Check if address already registered
            devices = self.db.get_all_devices()
            for device in devices:
                if device['device_type'] == 'battery' and device.get('modbus_address') == modbus_address:
                    return f"Modbus address {modbus_address} is already registered"

        return None

    # ============================================
    # SERVICE LIFECYCLE
    # ============================================

    def start(self):
        """Start the web admin service"""
        if self.running:
            logger.warning("Web Admin Service already running")
            return

        self.running = True

        # Run Flask in a separate thread
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

        logger.info(f"Web Admin Service started on http://{self.host}:{self.port}")

    def _get_systemd_socket(self):
        """
        Get socket from systemd socket activation

        Returns:
            socket object if available, None otherwise
        """
        try:
            # Check if we're running under systemd socket activation
            listen_fds = int(os.environ.get('LISTEN_FDS', 0))
            listen_pid = int(os.environ.get('LISTEN_PID', 0))

            if listen_fds > 0 and listen_pid == os.getpid():
                # LISTEN_FDS contains number of file descriptors passed
                # File descriptors start at 3 (0=stdin, 1=stdout, 2=stderr)
                fd = 3

                # Create socket from file descriptor
                sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
                sock.set_inheritable(True)

                logger.info("Using systemd socket activation (socket-based startup)")
                return sock

            return None
        except Exception as e:
            logger.error(f"Error getting systemd socket: {e}")
            return None

    def _check_idle_timeout(self):
        """Background thread to check idle timeout and shutdown if exceeded"""
        while self.running:
            time.sleep(5)  # Check every 5 seconds

            if self.running:
                idle_time = time.time() - self.last_request_time
                if idle_time > self.idle_timeout:
                    logger.info(f"Idle timeout reached ({idle_time:.1f}s > {self.idle_timeout}s). Shutting down...")
                    # Shutdown the server
                    os.kill(os.getpid(), signal.SIGTERM)
                    break

    def _run_server(self):
        """Run Flask server (with systemd socket activation support)"""
        from werkzeug.serving import BaseWSGIServer, WSGIRequestHandler
        from socketserver import ThreadingMixIn

        # Start idle timeout checker thread
        self.idle_check_thread = threading.Thread(target=self._check_idle_timeout, daemon=True)
        self.idle_check_thread.start()
        logger.info(f"Idle timeout monitor started (timeout: {self.idle_timeout}s)")

        # Try to get systemd socket first
        systemd_socket = self._get_systemd_socket()

        if systemd_socket:
            # Use systemd socket
            logger.info(f"Starting web admin with systemd socket on port {self.port}")

            # Create custom threaded WSGI server
            class ThreadedWSGIServer(ThreadingMixIn, BaseWSGIServer):
                daemon_threads = True
                multithread = True

                def __init__(self, host, port, app, handler=None, passthrough_errors=False,
                             ssl_context=None, fd=None):
                    """Initialize server, optionally with systemd socket"""
                    self.app = app
                    self.passthrough_errors = passthrough_errors
                    self.ssl_context = ssl_context

                    if fd is not None:
                        # Use existing socket (systemd activation)
                        from http.server import HTTPServer
                        # Initialize base classes without binding
                        HTTPServer.__init__(self, (host, port), handler or WSGIRequestHandler,
                                           bind_and_activate=False)
                        # Replace socket with systemd socket
                        self.socket = fd
                        self.server_address = fd.getsockname()
                        self.server_activate()
                    else:
                        # Normal initialization
                        super().__init__(host, port, app, handler, passthrough_errors, ssl_context)

            # Create server with systemd socket
            server = ThreadedWSGIServer(
                'localhost',  # host (not used for socket activation)
                0,  # port (not used for socket activation)
                self.app,  # WSGI application
                handler=WSGIRequestHandler,
                fd=systemd_socket  # Pass systemd socket
            )

            logger.info(f"Web admin bound to systemd socket at {server.server_address}")

            # Serve requests forever
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                logger.info("Server interrupted")
            finally:
                server.server_close()
        else:
            # Normal Flask startup (no socket activation)
            logger.info(f"Starting web admin normally on {self.host}:{self.port}")
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                use_reloader=False  # Disable reloader in thread
            )

    def stop(self):
        """Stop the web admin service"""
        if not self.running:
            return

        self.running = False
        logger.info("Web Admin Service stopped")

    def run(self):
        """Run service (blocking) - for systemd socket activation, run directly in main thread"""
        if self.running:
            logger.warning("Web Admin Service already running")
            return

        self.running = True

        try:
            # Run server directly in main thread (required for systemd socket activation)
            logger.info(f"Web Admin Service starting on http://{self.host}:{self.port}")
            self._run_server()
        except KeyboardInterrupt:
            logger.info("Web Admin Service interrupted")
        finally:
            self.stop()
