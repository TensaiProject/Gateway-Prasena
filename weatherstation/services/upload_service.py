"""
Upload Service
Handles batch upload of data to main server with retry mechanism
"""

import time
import requests
from typing import List, Dict, Any
from datetime import datetime
import yaml

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class UploadService:
    """
    Service to upload data to main server in batches
    """

    def __init__(self, config_path: str = None, config: Dict[str, Any] = None):
        """
        Initialize upload service

        Args:
            config_path: Path to YAML config file
            config: Configuration dictionary
        """
        # Load configuration
        if config_path:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        elif config:
            self.config = config
        else:
            self.config = self._default_config()

        # Setup logging
        log_config = self.config.get('logging', {})
        setup_logging(
            log_level=log_config.get('level', 'INFO'),
            log_file=log_config.get('log_file')
        )

        # Initialize database
        db_path = self.config.get('database', {}).get('path', './data/weatherstation.db')
        self.db = DatabaseManager(db_path)

        # Upload configuration
        upload_config = self.config.get('upload', {})
        self.interval = upload_config.get('interval', 60)
        self.batch_size = upload_config.get('batch_size', 100)
        self.max_retry = upload_config.get('max_retry', 5)
        self.retry_interval = upload_config.get('retry_interval', 30)
        self.server_url = upload_config.get('main_server_url')
        self.api_key = upload_config.get('api_key')
        self.timeout = upload_config.get('timeout', 30)

        # Cleanup configuration
        db_config = self.config.get('database', {})
        self.auto_cleanup_enabled = db_config.get('auto_cleanup_enabled', True)
        self.auto_cleanup_days = db_config.get('auto_cleanup_days', 7)

        self.running = False

        logger.info("Upload Service initialized")
        logger.info(f"Upload interval: {self.interval}s")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Server URL: {self.server_url}")
        logger.info(f"Auto-cleanup: {'enabled' if self.auto_cleanup_enabled else 'disabled'}")
        if self.auto_cleanup_enabled:
            logger.info(f"Cleanup threshold: {self.auto_cleanup_days} days")

    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'database': {
                'path': './data/weatherstation.db'
            },
            'upload': {
                'interval': 60,
                'batch_size': 100,
                'max_retry': 5,
                'retry_interval': 30,
                'main_server_url': 'http://example.com/api/data',
                'api_key': 'your_api_key',
                'timeout': 30
            },
            'logging': {
                'level': 'INFO',
                'log_file': './logs/upload_service.log'
            }
        }

    def upload_sensor_data(self, sensor_type: str) -> bool:
        """
        Upload pending sensor data for specified type

        Args:
            sensor_type: Type of sensor ('battery', 'weather', 'mqtt')

        Returns:
            True if upload successful, False otherwise
        """
        try:
            # Get pending data
            pending = self.db.get_pending_sensor_data(
                sensor_type=sensor_type,
                limit=self.batch_size
            )

            if not pending:
                logger.debug(f"No pending {sensor_type} data to upload")
                return True

            logger.info(f"Uploading {len(pending)} {sensor_type} records...")

            # Build payload
            batch_id = f"{sensor_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            payload = {
                'source': 'raspberry_pi_weather_station',
                'data_type': sensor_type,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'batch_id': batch_id,
                'device_count': len(set(r['sensor_id'] for r in pending)),
                'records': pending
            }

            # Send to server
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            response = requests.post(
                self.server_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            # Check response
            if response.status_code == 200:
                logger.info(f"Upload successful: {len(pending)} records")

                # Mark as uploaded
                record_ids = [r['id'] for r in pending]
                self.db.mark_sensor_data_uploaded(record_ids)

                # Log success
                self.db.log_upload(
                    batch_id=batch_id,
                    data_type=sensor_type,
                    record_count=len(pending),
                    status='success',
                    http_status_code=response.status_code
                )

                return True
            else:
                logger.error(
                    f"Upload failed: HTTP {response.status_code} - {response.text}"
                )

                # Log failure
                self.db.log_upload(
                    batch_id=batch_id,
                    data_type=sensor_type,
                    record_count=len(pending),
                    status='failed',
                    http_status_code=response.status_code,
                    error_message=response.text[:500]
                )

                return False

        except requests.exceptions.Timeout:
            logger.error(f"Upload timeout after {self.timeout}s")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Connection error - server unreachable")
            return False
        except Exception as e:
            logger.error(f"Upload error: {e}", exc_info=True)
            return False

    def run_auto_cleanup(self) -> None:
        """Run automatic cleanup of old uploaded data"""
        if not self.auto_cleanup_enabled:
            return

        try:
            logger.info(f"Running auto-cleanup (data older than {self.auto_cleanup_days} days)...")

            results = self.db.cleanup_all_uploaded_data(
                days_old=self.auto_cleanup_days,
                dry_run=False
            )

            total_deleted = results.get('total_records_deleted', 0)

            if total_deleted > 0:
                logger.info(f"Auto-cleanup: deleted {total_deleted} records")
            else:
                logger.debug("Auto-cleanup: no old records to delete")

        except Exception as e:
            logger.error(f"Auto-cleanup error: {e}", exc_info=True)

    def upload_all_pending(self) -> None:
        """Upload all pending data (battery, weather, mqtt)"""
        logger.info("Starting upload cycle...")

        # Check pending counts
        battery_pending = self.db.get_pending_upload_count('battery')
        weather_pending = self.db.get_pending_upload_count('weather')
        mqtt_pending = self.db.get_pending_upload_count('mqtt')

        logger.info(
            f"Pending: Battery={battery_pending}, "
            f"Weather={weather_pending}, MQTT={mqtt_pending}"
        )

        if battery_pending == 0 and weather_pending == 0 and mqtt_pending == 0:
            logger.info("No pending data to upload")

            # Still run cleanup even if no pending uploads
            self.run_auto_cleanup()
            return

        # Upload data by type
        upload_success = False

        # Battery data
        if battery_pending > 0:
            success = self.upload_sensor_data('battery')
            if success:
                logger.info("Battery data upload complete")
                upload_success = True
            else:
                logger.warning("Battery data upload failed, will retry")

        # Weather data
        if weather_pending > 0:
            success = self.upload_sensor_data('weather')
            if success:
                logger.info("Weather data upload complete")
                upload_success = True
            else:
                logger.warning("Weather data upload failed, will retry")

        # MQTT data
        if mqtt_pending > 0:
            success = self.upload_sensor_data('mqtt')
            if success:
                logger.info("MQTT data upload complete")
                upload_success = True
            else:
                logger.warning("MQTT data upload failed, will retry")

        logger.info("Upload cycle complete")

        # Run auto-cleanup after successful uploads
        if upload_success:
            self.run_auto_cleanup()

    def run(self) -> None:
        """Main service loop"""
        logger.info("=" * 60)
        logger.info("Upload Service starting...")
        logger.info("=" * 60)

        self.running = True

        try:
            while self.running:
                try:
                    self.upload_all_pending()
                except Exception as e:
                    logger.error(f"Error in upload cycle: {e}", exc_info=True)

                # Sleep until next upload
                logger.debug(f"Sleeping for {self.interval}s...")
                time.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the service"""
        logger.info("Upload Service stopping...")
        self.running = False
        logger.info("Upload Service stopped")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Upload Service')
    parser.add_argument(
        '-c', '--config',
        help='Path to config file (YAML)',
        default='./config/system_config.yaml'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run in test mode (single upload)'
    )

    args = parser.parse_args()

    try:
        service = UploadService(config_path=args.config)

        if args.test:
            logger.info("Running in TEST mode (single upload)")
            service.upload_all_pending()
            logger.info("Test complete")
        else:
            service.run()

    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
