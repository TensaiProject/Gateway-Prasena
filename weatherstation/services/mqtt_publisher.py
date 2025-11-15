#!/usr/bin/env python3
"""
MQTT Publisher Service
Publishes sensor data to MQTT broker in real-time
"""

import time
import json
import argparse
import yaml
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class MQTTPublisher:
    """
    MQTT Publisher for sensor data
    Polls database for new data and publishes to MQTT broker
    """

    def __init__(self, config: Dict[str, Any], db_path: str = './data/weatherstation.db'):
        """
        Initialize MQTT publisher

        Args:
            config: Configuration dictionary
            db_path: Path to SQLite database
        """
        if mqtt is None:
            raise RuntimeError("paho-mqtt not installed. Install: pip install paho-mqtt")

        self.config = config
        self.db = DatabaseManager(db_path)
        self.running = False
        self.connected = False
        self.client: Optional[mqtt.Client] = None

        # MQTT config
        mqtt_config = config.get('mqtt', {})
        self.broker_host = mqtt_config.get('broker_host', 'localhost')
        self.broker_port = mqtt_config.get('broker_port', 1883)
        self.protocol = mqtt_config.get('protocol', 'tcp')
        self.username = mqtt_config.get('username')
        self.password = mqtt_config.get('password')
        self.qos = mqtt_config.get('qos', 1)
        self.keepalive = mqtt_config.get('keepalive', 60)
        self.reconnect_delay = mqtt_config.get('reconnect_delay', 5)

        # Topics
        self.topics = mqtt_config.get('topics', {})
        self.base_topic = self.topics.get('sensor_data', 'prasena/sensors')

        # Polling config
        self.poll_interval = 5  # Poll database every 5 seconds
        self.last_published_id = {'battery': 0, 'weather': 0}

        logger.info("MQTT Publisher initialized")
        logger.info(f"Broker: {self.protocol}://{self.broker_host}:{self.broker_port}")
        logger.info(f"Base topic: {self.base_topic}")

    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
        else:
            self.connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            logger.error(f"MQTT connection failed: {error_messages.get(rc, f'Unknown error ({rc})')}")

    def on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection (rc={rc}), will reconnect...")
        else:
            logger.info("Disconnected from MQTT broker")

    def on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published (mid={mid})")

    def connect_mqtt(self) -> bool:
        """
        Connect to MQTT broker

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create client
            client_id = f"gateway_{int(time.time())}"

            if self.protocol == 'wss':
                # WebSocket Secure
                self.client = mqtt.Client(
                    client_id=client_id,
                    transport='websockets'
                )
                self.client.tls_set()  # Enable TLS
            elif self.protocol == 'ws':
                # WebSocket
                self.client = mqtt.Client(
                    client_id=client_id,
                    transport='websockets'
                )
            else:
                # TCP
                self.client = mqtt.Client(client_id=client_id)

            # Set callbacks
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_publish = self.on_publish

            # Set credentials if provided
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            # Connect
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(
                self.broker_host,
                self.broker_port,
                self.keepalive
            )

            # Start network loop in background
            self.client.loop_start()

            # Wait for connection
            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if self.connected:
                logger.info("MQTT connection established")
                return True
            else:
                logger.error("MQTT connection timeout")
                return False

        except Exception as e:
            logger.error(f"MQTT connection error: {e}", exc_info=True)
            return False

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Publish message to MQTT broker

        Args:
            topic: MQTT topic
            payload: Data to publish (will be converted to JSON)

        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            logger.warning("Cannot publish: not connected to MQTT broker")
            return False

        try:
            payload_json = json.dumps(payload)
            result = self.client.publish(topic, payload_json, qos=self.qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {len(payload_json)} bytes")
                return True
            else:
                logger.error(f"Publish failed: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Publish error: {e}", exc_info=True)
            return False

    def poll_and_publish(self):
        """
        Poll database for new sensor data and publish to MQTT
        Uses optimized query to fetch only records after last published ID
        """
        try:
            # Poll battery data (optimized: only fetch records > last_published_id)
            battery_data = self.db.get_pending_sensor_data_after_id(
                sensor_type='battery',
                after_id=self.last_published_id['battery'],
                limit=10
            )

            for record in battery_data:
                topic = f"{self.base_topic}/battery/{record['sensor_id']}"

                payload = {
                    'sensor_id': record['sensor_id'],
                    'sensor_type': 'battery',
                    'data': record['data'],
                    'timestamp': record['timestamp'],
                    'read_quality': record.get('read_quality', 100)
                }

                if self.publish(topic, payload):
                    self.last_published_id['battery'] = record['id']
                    logger.info(f"Published battery data: {record['sensor_id']} (ID: {record['id']})")

            # Poll weather data (optimized: only fetch records > last_published_id)
            weather_data = self.db.get_pending_sensor_data_after_id(
                sensor_type='weather',
                after_id=self.last_published_id['weather'],
                limit=10
            )

            for record in weather_data:
                topic = f"{self.base_topic}/weather/{record['sensor_id']}"

                payload = {
                    'sensor_id': record['sensor_id'],
                    'sensor_type': 'weather',
                    'data': record['data'],
                    'timestamp': record['timestamp'],
                    'read_quality': record.get('read_quality', 100)
                }

                if self.publish(topic, payload):
                    self.last_published_id['weather'] = record['id']
                    logger.info(f"Published weather data: {record['sensor_id']} (ID: {record['id']})")

        except Exception as e:
            logger.error(f"Poll/publish error: {e}", exc_info=True)

    def run(self):
        """Main service loop"""
        logger.info("=" * 60)
        logger.info("MQTT Publisher Service starting...")
        logger.info("=" * 60)

        # Connect to MQTT
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker, exiting...")
            return 1

        self.running = True

        try:
            while self.running:
                if self.connected:
                    self.poll_and_publish()
                else:
                    # Try to reconnect
                    logger.warning("Not connected, attempting reconnect...")
                    self.connect_mqtt()

                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
        finally:
            self.stop()

        return 0

    def stop(self):
        """Stop the service"""
        logger.info("MQTT Publisher Service stopping...")
        self.running = False

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

        logger.info("MQTT Publisher Service stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='MQTT Publisher Service')
    parser.add_argument(
        '-c', '--config',
        default='./weatherstation/config/system_config.yaml',
        help='Path to config file'
    )

    args = parser.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Setup logging
    log_config = config.get('logging', {})
    setup_logging(
        log_level=log_config.get('level', 'INFO'),
        log_file=log_config.get('mqtt_log_file', './logs/mqtt_publisher.log')
    )

    # Check if MQTT is enabled
    mqtt_config = config.get('mqtt', {})
    if not mqtt_config:
        logger.error("MQTT configuration not found in config file")
        return 1

    # Initialize database
    db_path = config.get('database', {}).get('path', './data/weatherstation.db')

    try:
        publisher = MQTTPublisher(config, db_path)
        return publisher.run()

    except Exception as e:
        logger.error(f"Failed to start MQTT publisher: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
