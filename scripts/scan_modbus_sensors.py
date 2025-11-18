#!/usr/bin/env python3
"""
Modbus RS485 Sensor Scanner
Scan for available PZEM-017 or compatible Modbus RTU devices

Usage:
    python3 scan_modbus_sensors.py              # Scan addresses 1-20
    python3 scan_modbus_sensors.py --start 1 --end 10  # Scan addresses 1-10
    python3 scan_modbus_sensors.py --address 5  # Test single address
"""

import sys
import time
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pigpio
except ImportError:
    print("ERROR: pigpio not installed")
    print("Install: sudo apt install pigpio python3-pigpio")
    print("Start daemon: sudo systemctl start pigpiod")
    sys.exit(1)

from weatherstation.sensors.battery_reader import BatterySensor


def scan_modbus_address(address: int, tx_pin: int = 12, rx_pin: int = 13) -> dict:
    """
    Test if a Modbus sensor exists at given address

    Args:
        address: Modbus address to test (1-247)
        tx_pin: GPIO TX pin (default 12)
        rx_pin: GPIO RX pin (default 13)

    Returns:
        dict with 'found' (bool) and 'data' (dict if found)
    """
    sensor = None
    try:
        # Create sensor instance
        sensor = BatterySensor(modbus_address=address, tx_pin=tx_pin, rx_pin=rx_pin)

        # Try to read data (with timeout)
        data = sensor.read_all()

        # Validate data (voltage should be reasonable)
        voltage = data.get('voltage', 0)
        if voltage < 0 or voltage > 500:  # Sanity check
            return {'found': False, 'data': None, 'error': 'Invalid voltage reading'}

        return {'found': True, 'data': data, 'error': None}

    except TimeoutError:
        return {'found': False, 'data': None, 'error': 'Timeout (no response)'}
    except IOError as e:
        return {'found': False, 'data': None, 'error': f'IO Error: {e}'}
    except Exception as e:
        return {'found': False, 'data': None, 'error': f'Error: {e}'}
    finally:
        if sensor:
            try:
                sensor.close()
            except:
                pass


def print_separator(char='=', length=80):
    """Print separator line"""
    print(char * length)


def print_sensor_data(address: int, data: dict):
    """Pretty print sensor data"""
    print(f"\n{'='*80}")
    print(f"  SENSOR FOUND AT ADDRESS {address}")
    print(f"{'='*80}")
    print(f"  Voltage:        {data['voltage']:.2f} V")
    print(f"  Current:        {data['current']:.3f} A")
    print(f"  Power:          {data['power']:.2f} W")
    print(f"  Energy:         {data['energy']:.4f} kWh")
    print(f"  Alarm High:     {data['alarm_high_voltage']}")
    print(f"  Alarm Low:      {data['alarm_low_voltage']}")
    print(f"  Timestamp:      {data['timestamp']}")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Scan for Modbus RTU sensors on RS485 bus',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                        # Scan addresses 1-20
  %(prog)s --start 1 --end 10     # Scan addresses 1-10
  %(prog)s --address 5            # Test single address 5
  %(prog)s --tx 14 --rx 15        # Use custom GPIO pins
        """
    )

    parser.add_argument(
        '--start',
        type=int,
        default=1,
        help='Start address (default: 1)'
    )
    parser.add_argument(
        '--end',
        type=int,
        default=20,
        help='End address (default: 20)'
    )
    parser.add_argument(
        '--address',
        type=int,
        help='Test single address only'
    )
    parser.add_argument(
        '--tx',
        type=int,
        default=12,
        help='TX GPIO pin (default: 12)'
    )
    parser.add_argument(
        '--rx',
        type=int,
        default=13,
        help='RX GPIO pin (default: 13)'
    )
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Fast scan mode (skip detailed validation)'
    )

    args = parser.parse_args()

    # Check pigpiod daemon
    pi_test = pigpio.pi()
    if not pi_test.connected:
        print("\n" + "="*80)
        print("ERROR: Cannot connect to pigpiod daemon")
        print("="*80)
        print("\nPlease start the daemon first:")
        print("  sudo systemctl start pigpiod")
        print("\nOr enable it permanently:")
        print("  sudo systemctl enable pigpiod")
        print("  sudo systemctl start pigpiod")
        print("\n" + "="*80 + "\n")
        sys.exit(1)
    pi_test.stop()

    # Determine scan range
    if args.address:
        addresses = [args.address]
        scan_mode = f"single address {args.address}"
    else:
        addresses = range(args.start, args.end + 1)
        scan_mode = f"addresses {args.start}-{args.end}"

    # Print header
    print_separator('=')
    print(f"  MODBUS RTU SENSOR SCANNER")
    print_separator('=')
    print(f"  Scan mode:      {scan_mode}")
    print(f"  GPIO TX pin:    {args.tx}")
    print(f"  GPIO RX pin:    {args.rx}")
    print(f"  Baudrate:       9600")
    print(f"  Protocol:       Modbus RTU (8N2)")
    print_separator('=')
    print()

    # Scan
    found_sensors = []

    for addr in addresses:
        print(f"Scanning address {addr:3d}...", end=' ', flush=True)

        result = scan_modbus_address(addr, tx_pin=args.tx, rx_pin=args.rx)

        if result['found']:
            print("✓ FOUND")
            found_sensors.append({'address': addr, 'data': result['data']})
            if not args.fast:
                print_sensor_data(addr, result['data'])
        else:
            print(f"✗ {result['error']}")

        # Small delay between scans to avoid bus conflicts
        if not args.fast:
            time.sleep(0.05)

    # Summary
    print_separator('=')
    print(f"  SCAN COMPLETE")
    print_separator('=')
    print(f"  Total scanned:  {len(addresses)}")
    print(f"  Sensors found:  {len(found_sensors)}")
    print_separator('=')

    if found_sensors:
        print("\n" + "="*80)
        print("  FOUND SENSORS SUMMARY")
        print("="*80)
        for sensor in found_sensors:
            addr = sensor['address']
            data = sensor['data']
            print(f"  Address {addr:3d}: {data['voltage']:.1f}V, {data['current']:.2f}A, {data['power']:.1f}W")
        print("="*80)

        print("\n" + "="*80)
        print("  NEXT STEPS")
        print("="*80)
        print("  1. Register sensors in database:")
        print("     python3 -m weatherstation.main --register-device")
        print()
        print("  2. When registering, use these Modbus addresses:")
        for sensor in found_sensors:
            print(f"     - Address {sensor['address']}")
        print()
        print("  3. Start the battery reader service:")
        print("     python3 -m weatherstation.main --service battery")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("  NO SENSORS FOUND")
        print("="*80)
        print("  Troubleshooting:")
        print("  1. Check RS485 wiring:")
        print("     - MAX485 DI  → GPIO 12 (TX)")
        print("     - MAX485 RO  → GPIO 13 (RX)")
        print("     - MAX485 A   → RS485 A/+")
        print("     - MAX485 B   → RS485 B/-")
        print()
        print("  2. Check sensor power supply (12-24V DC)")
        print("  3. Verify sensor Modbus address configuration")
        print("  4. Check baudrate (should be 9600, 8N2)")
        print("  5. Try different address range (some sensors use 1-10)")
        print("="*80 + "\n")

    return 0 if found_sensors else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
