#!/usr/bin/env python3
"""
PZEM-017 Modbus Address Changer
Change the Modbus RTU address of PZEM-017 DC sensor

WARNING: Only one sensor should be connected to the RS485 bus when changing address!

Usage:
    python3 change_pzem_address.py --old 1 --new 5    # Change address from 1 to 5
    python3 change_pzem_address.py --scan             # Scan to find current address
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

try:
    import minimalmodbus
except ImportError:
    print("ERROR: minimalmodbus not installed")
    print("Install: pip3 install minimalmodbus")
    sys.exit(1)


class PZEMAddressChanger:
    """
    PZEM-017 Modbus address changer using pigpio software UART
    """

    # PZEM-017 Modbus registers
    REGISTER_ADDRESS = 0x0002  # Register to change address

    def __init__(self, tx_pin: int = 12, rx_pin: int = 13, baudrate: int = 9600):
        """
        Initialize PZEM address changer

        Args:
            tx_pin: GPIO pin for TX (default 12)
            rx_pin: GPIO pin for RX (default 13)
            baudrate: Baud rate (default 9600)
        """
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        self.baudrate = baudrate
        self.pi = pigpio.pi()

        if not self.pi.connected:
            raise RuntimeError("Cannot connect to pigpiod daemon. Start it with: sudo systemctl start pigpiod")

    def scan_for_sensor(self, start_addr: int = 1, end_addr: int = 20) -> list:
        """
        Scan for sensors on the bus

        Returns:
            list of found addresses
        """
        found = []

        print(f"\nScanning addresses {start_addr}-{end_addr}...")
        print("=" * 60)

        for addr in range(start_addr, end_addr + 1):
            print(f"Testing address {addr:3d}...", end=' ', flush=True)

            try:
                # Try to read voltage register (0x0000)
                if self._test_address(addr):
                    print("✓ FOUND")
                    found.append(addr)
                else:
                    print("✗")
            except Exception as e:
                print(f"✗ ({e})")

            time.sleep(0.1)

        print("=" * 60)
        print(f"Found {len(found)} sensor(s): {found}\n")

        return found

    def _test_address(self, address: int) -> bool:
        """
        Test if sensor responds at given address using BatterySensor class

        Returns:
            True if sensor found
        """
        from weatherstation.sensors.battery_reader import BatterySensor

        sensor = None
        try:
            # Use BatterySensor class which has proven retry mechanism
            sensor = BatterySensor(
                modbus_address=address,
                tx_pin=self.tx_pin,
                rx_pin=self.rx_pin
            )

            # Try to read data
            data = sensor.read_all()

            # Validate voltage is reasonable
            voltage = data.get('voltage', 0)
            if 0 < voltage < 500:
                return True
            return False

        except Exception:
            return False
        finally:
            if sensor:
                try:
                    sensor.close()
                except:
                    pass
            # Small delay to let pigpio settle
            time.sleep(0.2)

    def change_address(self, old_address: int, new_address: int) -> bool:
        """
        Change sensor Modbus address

        Args:
            old_address: Current address (1-247)
            new_address: New address (1-247)

        Returns:
            True if successful
        """
        if not (1 <= old_address <= 247):
            raise ValueError("Old address must be between 1-247")
        if not (1 <= new_address <= 247):
            raise ValueError("New address must be between 1-247")

        print(f"\nChanging address {old_address} → {new_address}")
        print("=" * 60)

        # Step 1: Verify old address exists
        print(f"Step 1: Verifying sensor at address {old_address}...", end=' ', flush=True)
        if not self._test_address(old_address):
            print("✗ FAILED")
            print(f"\nERROR: No sensor found at address {old_address}")
            return False
        print("✓ OK")

        # Step 2: Write new address to register 0x0002
        print(f"Step 2: Writing new address {new_address}...", end=' ', flush=True)
        try:
            self._write_register(old_address, self.REGISTER_ADDRESS, new_address)
            print("✓ OK")
        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Step 3: Wait for sensor to apply change
        print("Step 3: Waiting for sensor to apply change...", end=' ', flush=True)
        time.sleep(1)
        print("✓ OK")

        # Step 4: Verify new address
        print(f"Step 4: Verifying sensor at new address {new_address}...", end=' ', flush=True)
        if not self._test_address(new_address):
            print("✗ FAILED")
            print(f"\nERROR: Sensor not responding at new address {new_address}")
            return False
        print("✓ OK")

        print("=" * 60)
        print(f"✓ SUCCESS: Address changed from {old_address} to {new_address}")
        print("=" * 60)
        print("\nIMPORTANT: Power cycle the sensor to ensure change is permanent!")
        print()

        return True

    def _write_register(self, address: int, register: int, value: int):
        """
        Write value to Modbus register (function code 0x06)
        """
        try:
            # Close any existing serial read (ignore errors)
            try:
                self.pi.bb_serial_read_close(self.rx_pin)
            except:
                pass

            # Open serial
            self.pi.bb_serial_read_open(self.rx_pin, self.baudrate, 8)

            # Build Modbus RTU request (Preset Single Register - 0x06)
            request = bytes([
                address,                    # Slave address
                0x06,                       # Function code: Preset Single Register
                (register >> 8) & 0xFF,     # Register address high byte
                register & 0xFF,            # Register address low byte
                (value >> 8) & 0xFF,        # Value high byte
                value & 0xFF                # Value low byte
            ])

            # Calculate CRC16
            crc = self._calculate_crc16(request)
            request = request + crc.to_bytes(2, 'little')

            # Send request
            self.pi.wave_clear()
            self.pi.wave_add_serial(self.tx_pin, self.baudrate, request, 0, 8, 2)
            wave_id = self.pi.wave_create()
            self.pi.wave_send_once(wave_id)

            # Wait for transmission
            while self.pi.wave_tx_busy():
                time.sleep(0.001)

            # Wait for response (longer delay for write operation)
            time.sleep(0.3)

            # Read response
            count, data = self.pi.bb_serial_read(self.rx_pin)

            # Cleanup
            self.pi.wave_delete(wave_id)
            self.pi.bb_serial_read_close(self.rx_pin)

            # Verify response
            if count < 8:
                raise IOError(f"Invalid response: expected 8 bytes, got {count}")

        except Exception as e:
            # Ensure cleanup even on error
            try:
                self.pi.bb_serial_read_close(self.rx_pin)
            except:
                pass
            raise e

    def _calculate_crc16(self, data: bytes) -> int:
        """
        Calculate Modbus RTU CRC16
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def close(self):
        """Close pigpio connection"""
        if self.pi:
            self.pi.stop()


def main():
    parser = argparse.ArgumentParser(
        description='Change PZEM-017 Modbus address',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan                    # Scan to find current address
  %(prog)s --old 1 --new 5           # Change address from 1 to 5
  %(prog)s --old 1 --new 5 --tx 14 --rx 15  # Use custom GPIO pins

WARNING:
  Only connect ONE sensor to the RS485 bus when changing address!
  Otherwise, multiple sensors with the same address will conflict.
        """
    )

    parser.add_argument('--old', type=int, help='Current Modbus address')
    parser.add_argument('--new', type=int, help='New Modbus address')
    parser.add_argument('--scan', action='store_true', help='Scan for sensors')
    parser.add_argument('--tx', type=int, default=12, help='TX GPIO pin (default: 12)')
    parser.add_argument('--rx', type=int, default=13, help='RX GPIO pin (default: 13)')

    args = parser.parse_args()

    # Check pigpiod daemon
    pi_test = pigpio.pi()
    if not pi_test.connected:
        print("\n" + "="*60)
        print("ERROR: Cannot connect to pigpiod daemon")
        print("="*60)
        print("\nPlease start the daemon first:")
        print("  sudo systemctl start pigpiod")
        print("\n" + "="*60 + "\n")
        sys.exit(1)
    pi_test.stop()

    # Print header
    print("\n" + "="*60)
    print("  PZEM-017 MODBUS ADDRESS CHANGER")
    print("="*60)
    print(f"  GPIO TX pin:    {args.tx}")
    print(f"  GPIO RX pin:    {args.rx}")
    print(f"  Baudrate:       9600")
    print("="*60)

    changer = None
    try:
        changer = PZEMAddressChanger(tx_pin=args.tx, rx_pin=args.rx)

        if args.scan:
            # Scan mode
            found = changer.scan_for_sensor()
            if not found:
                print("\n⚠  No sensors found. Check wiring and power supply.")
                return 1
            return 0

        elif args.old and args.new:
            # Change address mode
            print("\n⚠  WARNING: Only ONE sensor should be connected!")
            print("   Multiple sensors with same address will conflict.\n")

            response = input("Continue? [y/N]: ")
            if response.lower() != 'y':
                print("Aborted.")
                return 0

            success = changer.change_address(args.old, args.new)
            return 0 if success else 1

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nAborted by user (Ctrl+C)")
        return 130
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if changer:
            changer.close()


if __name__ == '__main__':
    sys.exit(main())
