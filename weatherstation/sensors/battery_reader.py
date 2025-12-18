#!/usr/bin/env python3
"""
Battery Sensor Reader via RS485 Modbus RTU
Uses pigpio bit-banged serial (software serial) on GPIO 12/13

Protocol: Modbus RTU @ 9600 baud, 8N2
Communication: RS485 via MAX485 module
Sensors: PZEM-017 DC or compatible Modbus power meters
"""

import time
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import deque

try:
    import pigpio
except ImportError:
    pigpio = None

from weatherstation.database.db_manager import DatabaseManager
from weatherstation.utils.logger import get_logger
from weatherstation.utils.timestamp_utils import now_rfc3339
from weatherstation.sensors.error_codes import classify_battery_error, get_error_description

logger = get_logger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_null_reading(error_message: str, error_code: int = 1) -> Dict[str, Any]:
    """
    Create null reading for failed sensor read

    Args:
        error_message: Description of error
        error_code: Error classification
            1 = Communication timeout
            2 = CRC validation failed
            3 = Device not responding
            4 = General IO error

    Returns:
        Null reading with error metadata
    """
    return {
        "voltage": None,
        "current": None,
        "power": None,
        "energy": None,
        "alarm_high_voltage": None,
        "alarm_low_voltage": None,
        "timestamp": now_rfc3339(),
        "error": True,
        "error_code": error_code,
        "error_message": error_message,
        "error_description": get_error_description(error_code)
    }


# =============================================================================
# MODBUS CRC-16
# =============================================================================

def modbus_crc(data: bytes) -> int:
    """Calculate Modbus CRC-16"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(data: bytes) -> bytes:
    """Append CRC to Modbus frame"""
    crc = modbus_crc(data)
    return data + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def check_crc(frame: bytes) -> bool:
    """Validate CRC of Modbus frame"""
    if len(frame) < 4:
        return False
    body = frame[:-2]
    rx_crc_lo, rx_crc_hi = frame[-2], frame[-1]
    calc = modbus_crc(body)
    return (rx_crc_lo == (calc & 0xFF)) and (rx_crc_hi == ((calc >> 8) & 0xFF))


# =============================================================================
# BATTERY SENSOR DRIVER (Software Serial via pigpio)
# =============================================================================

class BatterySensor:
    """
    Battery sensor reader using software serial (pigpio)
    Supports Modbus RTU devices like PZEM-017 DC
    """

    def __init__(
        self,
        modbus_address: int = 1,
        tx_pin: int = 12,
        rx_pin: int = 13,
        baudrate: int = 9600,
        use_de_re: bool = False,
        de_re_pin: int = 4
    ):
        """
        Initialize battery sensor reader

        Args:
            modbus_address: Modbus slave address (1-247)
            tx_pin: GPIO pin for TX (BCM numbering)
            rx_pin: GPIO pin for RX (BCM numbering)
            baudrate: Serial baudrate (default 9600)
            use_de_re: Enable DE/RE control for RS485 transceiver
            de_re_pin: GPIO pin for DE/RE control
        """
        if pigpio is None:
            raise RuntimeError("pigpio not installed. Install: sudo apt install pigpio python3-pigpio")

        self.modbus_address = modbus_address
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        self.baudrate = baudrate
        self.use_de_re = use_de_re
        self.de_re_pin = de_re_pin

        # Connect to pigpiod
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Cannot connect to pigpiod. Start daemon: sudo systemctl start pigpiod")

        # Setup RX
        self.pi.set_mode(self.rx_pin, pigpio.INPUT)

        # Try to close any existing serial read (ignore if none exists)
        try:
            self.pi.bb_serial_read_close(self.rx_pin)
        except:
            pass  # No serial read was open, that's fine

        rc = self.pi.bb_serial_read_open(self.rx_pin, self.baudrate, 8)
        if rc != 0:
            raise RuntimeError(f"bb_serial_read_open failed (rc={rc})")

        # Setup TX (idle HIGH for UART)
        self.pi.set_mode(self.tx_pin, pigpio.OUTPUT)
        self.pi.write(self.tx_pin, 1)

        # Optional DE/RE control
        if self.use_de_re:
            self.pi.set_mode(self.de_re_pin, pigpio.OUTPUT)
            self.pi.write(self.de_re_pin, 0)  # LOW = RX mode

        # Clear wave
        self.pi.wave_clear()

        logger.info(f"Battery sensor initialized: address={modbus_address}, TX={tx_pin}, RX={rx_pin}")

    def _set_tx_mode(self, enable: bool):
        """Control DE/RE pin for RS485 direction"""
        if self.use_de_re:
            if enable:
                self.pi.write(self.de_re_pin, 1)
                time.sleep(0.0008)
            else:
                time.sleep(0.0008)
                self.pi.write(self.de_re_pin, 0)

    def _tx_bytes(self, payload: bytes):
        """Transmit bytes via software serial (8N2 format)"""
        self.pi.wave_clear()
        self.pi.wave_add_serial(self.tx_pin, self.baudrate, payload, bb_bits=8, bb_stop=2)
        wid = self.pi.wave_create()
        if wid < 0:
            raise RuntimeError(f"wave_create failed (rc={wid})")

        self.pi.wave_send_once(wid)

        # Wait for transmission complete
        while self.pi.wave_tx_busy():
            time.sleep(0.0005)

        self.pi.wave_delete(wid)

    def _rx_read_all(self) -> bytes:
        """Read all available data from RX buffer"""
        count, data = self.pi.bb_serial_read(self.rx_pin)
        return data if count > 0 else b""

    def _rx_read_until_timeout(self, timeout_s: float) -> bytes:
        """Read RX buffer until timeout"""
        start = time.time()
        buf = bytearray()
        while (time.time() - start) < timeout_s:
            n, chunk = self.pi.bb_serial_read(self.rx_pin)
            if n > 0:
                buf.extend(chunk)
            else:
                time.sleep(0.001)
        return bytes(buf)

    def _modbus_exchange(self, adu_tx: bytes, expect_min_len: int, timeout: float = 0.2) -> bytes:
        """Send Modbus request and receive response"""
        # Clear RX buffer
        _ = self._rx_read_all()

        # Transmit
        self._set_tx_mode(True)
        self._tx_bytes(adu_tx)
        self._set_tx_mode(False)

        # Inter-frame delay
        time.sleep(0.005)

        # Receive
        rx = self._rx_read_until_timeout(timeout)
        rx += self._rx_read_until_timeout(0.01)  # Extra read for late bytes

        if len(rx) < expect_min_len:
            raise TimeoutError(f"RX too short ({len(rx)}B < {expect_min_len}B)")

        return rx

    def read_input_registers(self, start_addr: int, count: int, max_retries: int = 2) -> bytes:
        """
        Read Modbus input registers (Function 0x04)

        Args:
            start_addr: Starting register address
            count: Number of registers to read
            max_retries: Maximum retry attempts

        Returns:
            Full Modbus response frame
        """
        # Build Modbus frame
        pdu = bytes([
            self.modbus_address,
            0x04,  # Read Input Registers
            (start_addr >> 8) & 0xFF,
            start_addr & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF
        ])
        adu = append_crc(pdu)

        expect_min = 5 + count * 2

        # Retry logic
        for attempt in range(max_retries + 1):
            try:
                rx = self._modbus_exchange(adu, expect_min)

                # Validate CRC
                if not check_crc(rx):
                    if attempt < max_retries:
                        time.sleep(0.01 * (attempt + 1))
                        continue
                    raise IOError(f"CRC validation failed: {rx.hex(' ')}")

                # Validate address
                if rx[0] != self.modbus_address:
                    raise IOError(f"Address mismatch: expected {self.modbus_address:02X}, got {rx[0]:02X}")

                # Check for Modbus exception
                if rx[1] != 0x04:
                    if (rx[1] & 0x80) and len(rx) >= 5:
                        exc = rx[2]
                        raise IOError(f"Modbus exception 0x{exc:02X}")
                    raise IOError(f"Function code mismatch: {rx[1]:02X}")

                return rx

            except (TimeoutError, IOError) as e:
                if attempt >= max_retries:
                    raise
                logger.warning(f"Read attempt {attempt + 1} failed: {e}")
                time.sleep(0.01 * (attempt + 1))

        raise IOError("Max retries exceeded")

    def read_all(self) -> Dict[str, Any]:
        """
        Read all battery sensor data

        Returns:
            Dictionary with voltage, current, power, energy, alarms
        """
        # Read registers 0x0000-0x0007 (8 registers)
        rx = self.read_input_registers(0x0000, 8)

        # Extract data bytes (skip header and CRC)
        data = rx[3:3+16]

        # Parse registers (big-endian)
        regs = []
        for i in range(0, len(data), 2):
            regs.append((data[i] << 8) | data[i+1])

        # Apply scaling factors
        voltage = (regs[0] & 0xFFFF) * 0.01  # V
        current = (regs[1] & 0xFFFF) * 0.01  # A

        # 32-bit power (high word in regs[3], low word in regs[2])
        power_raw = ((regs[3] & 0xFFFF) << 16) | (regs[2] & 0xFFFF)
        power = power_raw * 0.1  # W

        # 32-bit energy (high word in regs[5], low word in regs[4])
        energy_raw_wh = ((regs[5] & 0xFFFF) << 16) | (regs[4] & 0xFFFF)
        energy = energy_raw_wh / 1000.0  # kWh

        # Alarms
        alarm_high = (regs[6] & 0xFFFF) == 0xFFFF
        alarm_low = (regs[7] & 0xFFFF) == 0xFFFF

        # Sanity check: power should be close to V×I
        power_calc = voltage * current
        if power_calc >= 0.0 and power > 10 * max(1.0, power_calc):
            power = power_calc

        return {
            "voltage": round(voltage, 2),
            "current": round(current, 3),
            "power": round(power, 2),
            "energy": round(energy, 4),
            "alarm_high_voltage": alarm_high,
            "alarm_low_voltage": alarm_low,
            "timestamp": now_rfc3339()
        }

    def close(self):
        """Cleanup resources"""
        if hasattr(self, 'pi') and self.pi.connected:
            self.pi.bb_serial_read_close(self.rx_pin)
            self.pi.stop()
            logger.info("Battery sensor closed")


# =============================================================================
# AGGREGATION BUFFER
# =============================================================================

class AggregationBuffer:
    """
    Buffer for aggregating sensor samples before database insert

    Strategy:
    - Collect samples at high frequency (e.g., 1Hz)
    - Aggregate every N seconds (e.g., 5 minutes)
    - Store aggregated data (avg, min, max, last)
    """

    def __init__(self, window_seconds: int = 300):
        """
        Args:
            window_seconds: Aggregation window in seconds (default 300 = 5 minutes)
        """
        self.window_seconds = window_seconds
        self.samples: deque = deque()
        self.start_time = time.time()

    def add_sample(self, reading: Dict[str, Any]) -> None:
        """Add reading to buffer"""
        reading['_sample_time'] = time.time()
        self.samples.append(reading)

    def should_aggregate(self) -> bool:
        """Check if aggregation window has elapsed"""
        return (time.time() - self.start_time) >= self.window_seconds

    def aggregate(self) -> Optional[Dict[str, Any]]:
        """
        Aggregate buffered samples
        Handles null values from failed sensor reads

        Returns:
            Aggregated data dictionary or None if no samples
        """
        if not self.samples:
            return None

        # Separate valid and error samples
        valid_samples = [s for s in self.samples if not s.get('error', False)]
        error_samples = [s for s in self.samples if s.get('error', False)]

        total_samples = len(self.samples)
        valid_count = len(valid_samples)
        error_count = len(error_samples)

        # Calculate read quality (percentage of successful reads)
        read_quality = int((valid_count / total_samples) * 100) if total_samples > 0 else 0

        # If ALL samples are errors, return null aggregated data
        if valid_count == 0:
            last_error = error_samples[-1] if error_samples else {}
            aggregated = {
                "voltage_avg": None,
                "voltage_min": None,
                "voltage_max": None,
                "current_avg": None,
                "current_min": None,
                "current_max": None,
                "power_avg": None,
                "power_min": None,
                "power_max": None,
                "energy": None,
                "sample_count": total_samples,
                "valid_sample_count": 0,
                "error_count": error_count,
                "read_quality": 0,
                "error_code": last_error.get('error_code', 4),
                "error_message": last_error.get('error_message', 'All samples failed'),
                "error_description": last_error.get('error_description', 'Unknown error'),
                "timestamp": now_rfc3339()
            }
        else:
            # Aggregate ONLY valid samples
            voltages = [s['voltage'] for s in valid_samples if s['voltage'] is not None]
            currents = [s['current'] for s in valid_samples if s['current'] is not None]
            powers = [s['power'] for s in valid_samples if s['power'] is not None]

            # Last valid sample for energy (cumulative)
            last_valid = valid_samples[-1]

            aggregated = {
                "voltage_avg": round(sum(voltages) / len(voltages), 2) if voltages else None,
                "voltage_min": round(min(voltages), 2) if voltages else None,
                "voltage_max": round(max(voltages), 2) if voltages else None,
                "current_avg": round(sum(currents) / len(currents), 3) if currents else None,
                "current_min": round(min(currents), 3) if currents else None,
                "current_max": round(max(currents), 3) if currents else None,
                "power_avg": round(sum(powers) / len(powers), 2) if powers else None,
                "power_min": round(min(powers), 2) if powers else None,
                "power_max": round(max(powers), 2) if powers else None,
                "energy": last_valid.get('energy'),  # Cumulative, use last value
                "sample_count": total_samples,
                "valid_sample_count": valid_count,
                "error_count": error_count,
                "read_quality": read_quality,
                "timestamp": now_rfc3339()
            }

            # Add error metadata if there were some errors
            if error_count > 0:
                last_error = error_samples[-1]
                aggregated["last_error_code"] = last_error.get('error_code')
                aggregated["last_error_message"] = last_error.get('error_message')
                aggregated["last_error_description"] = last_error.get('error_description')

        # Clear buffer and reset timer
        self.samples.clear()
        self.start_time = time.time()

        return aggregated


# =============================================================================
# BATTERY READER SERVICE
# =============================================================================

class BatteryReaderService:
    """
    Service to continuously read battery sensors and store data
    """

    def __init__(self, config: Dict[str, Any], db_path: str = './data/weatherstation.db'):
        """
        Initialize battery reader service

        Args:
            config: Configuration dictionary
            db_path: Path to SQLite database
        """
        self.config = config
        self.db = DatabaseManager(db_path)
        self.running = False
        self.sensors: List[BatterySensor] = []
        self.buffers: Dict[int, AggregationBuffer] = {}

        # Load config
        battery_config = config.get('battery_sensors', {})
        self.enabled = battery_config.get('enabled', True)
        self.poll_interval = battery_config.get('poll_interval', 10)
        self.sampling_rate = battery_config.get('sampling_rate', 1)
        self.aggregation_window = battery_config.get('aggregation_window', 300)

        logger.info("Battery Reader Service initialized")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(f"Sampling rate: {self.sampling_rate}s")
        logger.info(f"Aggregation window: {self.aggregation_window}s")

    def setup_sensors(self):
        """Initialize sensors from database device registry"""
        devices = self.db.get_enabled_devices('battery')

        for device in devices:
            try:
                modbus_addr = device.get('modbus_address')
                if modbus_addr is None:
                    logger.warning(f"Device {device['sensor_id']} has no modbus_address, skipping")
                    continue

                sensor = BatterySensor(modbus_address=modbus_addr)
                self.sensors.append(sensor)
                self.buffers[device['id']] = AggregationBuffer(self.aggregation_window)

                logger.info(f"Sensor initialized: {device['sensor_name']} (address {modbus_addr})")

            except Exception as e:
                logger.error(f"Failed to initialize sensor {device.get('sensor_id')}: {e}")

        if not self.sensors:
            logger.warning("No battery sensors configured!")

    def run(self):
        """Main service loop"""
        if not self.enabled:
            logger.info("Battery sensors disabled in config")
            return

        self.setup_sensors()
        self.running = True

        logger.info("=" * 60)
        logger.info("Battery Reader Service starting...")
        logger.info("=" * 60)

        try:
            while self.running:
                # Poll all sensors
                for idx, sensor in enumerate(self.sensors):
                    # Get device info OUTSIDE try block to ensure we can still log errors
                    devices = self.db.get_enabled_devices('battery')
                    if idx >= len(devices):
                        continue

                    device_internal_id = devices[idx]['id']
                    sensor_id = devices[idx]['sensor_id']
                    reading = None
                    read_quality = 100
                    error_code = 0

                    try:
                        # Try to read sensor
                        reading = sensor.read_all()
                        read_quality = 100  # Success
                        error_code = 0

                    except Exception as e:
                        # Classify error and create null reading
                        error_code = classify_battery_error(e)
                        error_description = get_error_description(error_code)

                        logger.warning(
                            f"Sensor {sensor_id} (idx={idx}) read failed: {error_description} - {e}"
                        )

                        # Create null reading with error metadata
                        reading = create_null_reading(str(e), error_code)
                        read_quality = 0

                    # ALWAYS add to buffer (even if null/error)
                    if reading:
                        self.buffers[device_internal_id].add_sample(reading)

                        # Check if should aggregate
                        if self.buffers[device_internal_id].should_aggregate():
                            aggregated = self.buffers[device_internal_id].aggregate()
                            if aggregated:
                                # Store aggregated data to database with quality metadata
                                success = self.db.insert_sensor_data(
                                    sensor_id=sensor_id,
                                    data=aggregated,
                                    read_quality=aggregated.get('read_quality', 100),
                                    error_code=aggregated.get('error_code', 0)
                                )
                                if success:
                                    quality = aggregated.get('read_quality', 100)
                                    if quality == 100:
                                        logger.info(f"Stored aggregated data for {sensor_id} (quality: {quality}%)")
                                    elif quality > 0:
                                        logger.warning(f"Stored degraded data for {sensor_id} (quality: {quality}%)")
                                    else:
                                        logger.error(f"Stored ERROR data for {sensor_id} (quality: 0%, all samples failed)")
                                else:
                                    logger.error(f"Failed to store data for {sensor_id}")

                # Sleep
                time.sleep(self.sampling_rate)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
        finally:
            self.stop()

    def stop(self):
        """Stop service and cleanup"""
        logger.info("Battery Reader Service stopping...")
        self.running = False

        for sensor in self.sensors:
            try:
                sensor.close()
            except:
                pass

        logger.info("Battery Reader Service stopped")


def main():
    """Main entry point"""
    import yaml

    parser = argparse.ArgumentParser(description='Battery Sensor Reader')
    parser.add_argument(
        '-c', '--config',
        default='./weatherstation/config/system_config.yaml',
        help='Path to config file'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode (read all registered sensors)'
    )

    args = parser.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    if args.test:
        # Test mode: read ALL registered battery sensors from database
        logger.info("Test mode: reading all registered battery sensors")

        # Get database path
        db_path = config.get('database', {}).get('path', './data/weatherstation.db')
        db = DatabaseManager(db_path)

        # Get all enabled battery sensors
        devices = db.get_enabled_devices(sensor_type='battery')
        if not devices:
            logger.error("No battery sensors registered in database")
            print("ERROR: No battery sensors found. Please register a device first:")
            print("  python3 -m weatherstation.main --register-device")
            return 1

        print("=" * 70)
        print(f"BATTERY SENSOR TEST - Testing {len(devices)} sensor(s)")
        print("=" * 70)
        print()

        # Test results tracking
        results = []

        # Test each sensor
        for idx, device in enumerate(devices, 1):
            sensor_id = device['sensor_id']
            modbus_addr = device['modbus_address']
            sensor_name = device.get('sensor_name', sensor_id)

            print(f"[{idx}/{len(devices)}] Testing: {sensor_name} (ID: {sensor_id})")
            print(f"        Modbus Address: {modbus_addr}")

            logger.info(f"Testing sensor: {sensor_id} @ Modbus address {modbus_addr}")

            sensor = None
            try:
                sensor = BatterySensor(modbus_address=modbus_addr)
                reading = sensor.read_all()
                reading['sensor_id'] = sensor_id

                # Success
                print(f"        Status: ✓ PASS")
                print(f"        Data: V={reading['voltage']}V, I={reading['current']}A, P={reading['power']}W")
                print()

                results.append({
                    'sensor_id': sensor_id,
                    'sensor_name': sensor_name,
                    'modbus_address': modbus_addr,
                    'status': 'PASS',
                    'data': reading
                })

            except Exception as e:
                # Failure
                print(f"        Status: ✗ FAIL")
                print(f"        Error: {str(e)}")
                print()

                logger.error(f"Failed to read sensor {sensor_id}: {e}")

                results.append({
                    'sensor_id': sensor_id,
                    'sensor_name': sensor_name,
                    'modbus_address': modbus_addr,
                    'status': 'FAIL',
                    'error': str(e)
                })

            finally:
                if sensor:
                    sensor.close()

        # Print summary
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for r in results if r['status'] == 'PASS')
        failed = sum(1 for r in results if r['status'] == 'FAIL')

        print(f"Total sensors: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print()

        if failed > 0:
            print("Failed sensors:")
            for r in results:
                if r['status'] == 'FAIL':
                    print(f"  - {r['sensor_name']} (addr {r['modbus_address']}): {r['error']}")
            print()

        print("Detailed results (JSON):")
        print(json.dumps(results, indent=2))
        print()

        # Return exit code based on results
        return 0 if failed == 0 else 1
    else:
        # Run service
        service = BatteryReaderService(config)
        service.run()


if __name__ == '__main__':
    main()
