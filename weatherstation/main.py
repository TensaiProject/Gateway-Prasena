#!/usr/bin/env python3
"""
Weather Station & Energy Monitor System
Main entry point for starting all services
"""

import sys
import subprocess
import argparse
import yaml
from pathlib import Path

from weatherstation.utils.logger import get_logger, setup_logging

setup_logging(log_level='INFO', log_file='./logs/main.log')
logger = get_logger(__name__)


# ==============================================================================
# SERVICE WRAPPER FUNCTIONS (for multi-threading)
# ==============================================================================

def run_battery_service(config_path: str):
    """Run battery sensor reader service"""
    import yaml
    from weatherstation.sensors.battery_reader import BatteryReaderService
    from weatherstation.utils.logger import setup_logging

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    log_config = config.get('logging', {})
    setup_logging(
        log_level=log_config.get('level', 'INFO'),
        log_file='./logs/battery_reader.log'
    )

    db_path = config.get('database', {}).get('path', './data/weatherstation.db')
    service = BatteryReaderService(config, db_path)
    service.run()


def run_upload_service(config_path: str):
    """Run upload service"""
    from weatherstation.services.upload_service import UploadService
    from weatherstation.utils.logger import setup_logging

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    log_config = config.get('logging', {})
    setup_logging(
        log_level=log_config.get('level', 'INFO'),
        log_file='./logs/upload_service.log'
    )

    service = UploadService(config=config)
    service.run()


def run_weather_service(config_path: str):
    """Run weather receiver service"""
    from weatherstation.sensors.weather_receiver import main as weather_main
    sys.argv = ['weather_receiver', '-c', config_path]
    weather_main()


def run_mqtt_service(config_path: str):
    """Run MQTT publisher service"""
    from weatherstation.services.mqtt_publisher import main as mqtt_main
    sys.argv = ['mqtt_publisher', '-c', config_path]
    mqtt_main()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Weather Station & Energy Monitor System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --service battery        # Run battery sensor reader
  %(prog)s --service upload         # Run upload service
  %(prog)s --service weather        # Run weather station receiver
  %(prog)s --service mqtt           # Run MQTT publisher
  %(prog)s --service api            # Run web API server
  %(prog)s --service cleanup        # Run data cleanup service
  %(prog)s --service all            # Run all services (testing only)
  %(prog)s --init-db                # Initialize database
  %(prog)s --register-device        # Register new device (interactive)
        """
    )

    parser.add_argument(
        '--service',
        choices=['battery', 'upload', 'weather', 'mqtt', 'api', 'cleanup', 'all'],
        help='Service to run'
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize database with schema'
    )
    parser.add_argument(
        '--register-device',
        action='store_true',
        help='Register new device (interactive)'
    )
    parser.add_argument(
        '--config',
        default='./weatherstation/config/system_config.yaml',
        help='Path to config file'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run in test mode (single iteration)'
    )

    args = parser.parse_args()

    # Initialize database
    if args.init_db:
        return init_database()

    # Register device
    if args.register_device:
        return register_device_interactive()

    # Run service
    if args.service:
        return run_service(args.service, args.config, args.test)

    # No arguments, show help
    parser.print_help()
    return 0


def init_database():
    """Initialize database"""
    logger.info("Initializing database...")

    from weatherstation.database.db_manager import DatabaseManager

    try:
        db = DatabaseManager('./data/weatherstation.db')
        logger.info("Database initialized successfully!")
        logger.info("Location: ./data/weatherstation.db")
        return 0
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1


def register_device_interactive():
    """Register device interactively"""
    from weatherstation.database.db_manager import DatabaseManager

    print("\n" + "=" * 60)
    print("Device Registration")
    print("=" * 60 + "\n")

    device_type = input("Device type (pzem/weather_station/battery): ").strip()
    device_id = input("Device ID (e.g., pzem_01): ").strip()
    device_name = input("Device name: ").strip()
    location = input("Location: ").strip()

    # Type-specific fields
    modbus_address = None
    if device_type == 'pzem':
        modbus_address = int(input("Modbus address (1-247): "))

    try:
        db = DatabaseManager('./data/weatherstation.db')
        db.register_device(
            device_id=device_id,
            device_type=device_type,
            device_name=device_name,
            location=location,
            modbus_address=modbus_address,
            enabled=True
        )

        print(f"\n✓ Device registered successfully: {device_id}")
        return 0

    except Exception as e:
        print(f"\n✗ Failed to register device: {e}")
        return 1


def run_service(service: str, config: str, test_mode: bool = False):
    """Run specified service"""

    if service == 'battery':
        from weatherstation.sensors.battery_reader import main as battery_main
        sys.argv = ['battery_reader', '-c', config]
        if test_mode:
            sys.argv.append('--test')
        return battery_main()

    elif service == 'upload':
        from weatherstation.services.upload_service import main as upload_main
        sys.argv = ['upload_service', '-c', config]
        if test_mode:
            sys.argv.append('--test')
        return upload_main()

    elif service == 'weather':
        from weatherstation.sensors.weather_receiver import main as weather_main
        sys.argv = ['weather_receiver', '-c', config]
        return weather_main()

    elif service == 'mqtt':
        from weatherstation.services.mqtt_publisher import main as mqtt_main
        sys.argv = ['mqtt_publisher', '-c', config]
        return mqtt_main()

    elif service == 'cleanup':
        from weatherstation.services.cleanup_service import main as cleanup_main
        sys.argv = ['cleanup_service', '--db', './data/weatherstation.db']
        if test_mode:
            sys.argv.extend(['--once', '--dry-run'])
        else:
            sys.argv.append('--once')
        return cleanup_main()

    elif service == 'api':
        from weatherstation.api.web_server import main as api_main
        sys.argv = ['api_server', '--config', config]
        return api_main()

    elif service == 'all':
        from weatherstation.service_manager import ServiceManager

        logger.info("=" * 60)
        logger.info("Starting Weather Station Gateway (Production Mode)")
        logger.info("Multi-threaded single-process execution")
        logger.info("=" * 60)

        # Create service manager
        manager = ServiceManager()

        # Register all services
        manager.register_service(
            name='battery',
            target=run_battery_service,
            args=(config,),
            auto_restart=True
        )

        manager.register_service(
            name='upload',
            target=run_upload_service,
            args=(config,),
            auto_restart=True
        )

        manager.register_service(
            name='weather',
            target=run_weather_service,
            args=(config,),
            auto_restart=True
        )

        manager.register_service(
            name='mqtt',
            target=run_mqtt_service,
            args=(config,),
            auto_restart=True
        )

        # Run all services
        try:
            manager.run()
        except Exception as e:
            logger.error(f"ServiceManager error: {e}", exc_info=True)
            return 1

        return 0

    return 0


if __name__ == '__main__':
    try:
        exit(main())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested")
        exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
