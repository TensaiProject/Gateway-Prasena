#!/usr/bin/env python3
"""
Weather Station & Energy Monitor System
Main entry point for starting all services
"""

import sys
import subprocess
import argparse
from pathlib import Path

from weatherstation.utils.logger import get_logger, setup_logging

setup_logging(log_level='INFO', log_file='./logs/main.log')
logger = get_logger(__name__)


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
  %(prog)s --service api            # Run web API server
  %(prog)s --service cleanup        # Run data cleanup service
  %(prog)s --service all            # Run all services (testing only)
  %(prog)s --init-db                # Initialize database
  %(prog)s --register-device        # Register new device (interactive)
        """
    )

    parser.add_argument(
        '--service',
        choices=['battery', 'upload', 'weather', 'api', 'cleanup', 'all'],
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
        from weatherstation.sensors.weather_station import main as weather_main
        sys.argv = ['weather_station', '-c', config]
        return weather_main()

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
        logger.warning("Running all services in one process (testing only!)")
        logger.warning("For production, use systemd services")

        # This is just for testing - not recommended for production
        import threading

        services = ['battery', 'upload', 'weather']

        threads = []
        for svc in services:
            thread = threading.Thread(
                target=run_service,
                args=(svc, config, False),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            logger.info(f"Started {svc} service in thread")

        logger.info("All services started. Press Ctrl+C to stop.")

        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            logger.info("Stopping all services...")

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
