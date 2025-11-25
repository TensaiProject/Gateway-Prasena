"""
Config Generator for Weather Station Gateway
Auto-generates system_config.yaml with environment detection

Error handling:
- Permission errors → clear message with solution
- Disk errors → check space and path
- Invalid hostname → sanitize to safe chars
- Atomic write → prevents partial/corrupted files
- YAML errors → catch and report
"""

import yaml
import socket
import tempfile
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def sanitize_hostname(hostname: str) -> str:
    """
    Sanitize hostname for use in client_id
    - Only alphanumeric and underscore allowed
    - Max 64 characters
    - Fallback to 'gateway_default' if empty after sanitization

    Args:
        hostname: Raw hostname from system

    Returns:
        Sanitized hostname safe for MQTT client_id
    """
    # Replace invalid chars with underscore
    safe = ''.join(c if c.isalnum() or c == '_' else '_' for c in hostname)

    # Remove consecutive underscores
    while '__' in safe:
        safe = safe.replace('__', '_')

    # Strip leading/trailing underscores
    safe = safe.strip('_')

    # Truncate to 64 chars (MQTT client_id limit)
    safe = safe[:64]

    # Fallback if empty
    return safe or 'gateway_default'


def get_default_config_dict(hostname: str) -> Dict[str, Any]:
    """
    Generate default configuration dictionary

    Args:
        hostname: Sanitized hostname for client_id

    Returns:
        Complete configuration dictionary with auto-detected values
    """
    return {
        'system': {
            'name': f'Weather Station Gateway - {hostname}',
            'location': 'Your Location',
            'timezone': 'Asia/Jakarta'
        },
        'database': {
            'path': './data/weatherstation.db',
            'backup_enabled': True,
            'backup_interval': 86400,
            'auto_cleanup_enabled': True,
            'auto_cleanup_days': 1
        },
        'mqtt': {
            'protocol': 'tcp',
            'broker_url': 'mqtt://emqx.prasenaenergy.com:1883',
            'broker_host': 'emqx.prasenaenergy.com',
            'broker_port': 1883,
            'username': 'prasena',
            'password': 'CHANGE_ME',  # ⚠️ User MUST change this
            'qos': 1,
            'clean_session': True,
            'keepalive': 60,
            'reconnect_delay': 5,
            'client_id': f'gateway_{hostname}',  # Auto-generated from hostname
            'publisher': {
                'poll_interval': 5,
                'batch_size': 10
            },
            'topics': {
                'sensor_data': 'prasena/sensors',
                'weather_data': 'prasena/sensors/weather',
                'battery_data': 'prasena/sensors/battery',
                'system_status': 'prasena/system/status',
                'control': 'prasena/control/#'
            }
        },
        'battery_sensors': {
            'enabled': True,
            'poll_interval': 1,
            'sampling_rate': 1,
            'aggregation_window': 60
        },
        'weather_station': {
            'enabled': True,
            'http_port': 5001,
            'protocol': 'ecowitt'
        },
        'upload': {
            'enabled': True,
            'interval': 60,
            'batch_size': 100,
            'max_retry': 5,
            'retry_interval': 30,
            'main_server_url': 'https://api.prasenaenergy.com/dashboard/readings',
            'api_key': 'CHANGE_ME',  # ⚠️ User MUST change this
            'timeout': 30
        },
        'api': {
            'enabled': True,
            'host': '0.0.0.0',
            'port': 5000,
            'debug': False,
            'cors_enabled': True,
            'cors_origins': ['*']
        },
        'web_admin': {
            'enabled': False,
            'host': '0.0.0.0',
            'port': 8080,
            'debug': False
        },
        'logging': {
            'level': 'INFO',
            'log_to_file': True,
            'log_file': './logs/system.log',
            'weather_log_file': './logs/weather_receiver.log',
            'mqtt_log_file': './logs/mqtt_publisher.log',
            'max_file_size': 10485760,  # 10MB
            'backup_count': 5
        },
        'discovery': {
            'enabled': False,
            'scan_interval': 3600,
            'pzem_address_range': [1, 20]
        }
    }


def generate_default_config(output_path: str, force: bool = False) -> bool:
    """
    Generate default configuration file with auto-detected values
    Uses atomic write to prevent corruption

    Args:
        output_path: Path where config file should be written
        force: If True, overwrite existing file (default: False)

    Returns:
        True if successful, False otherwise

    Raises:
        FileExistsError: Config already exists and force=False
        PermissionError: No write permission on directory
        OSError: Disk full or path issues
        ImportError: YAML module not available

    Error handling:
    - Checks write permission before attempting
    - Atomic write via tempfile (no partial files)
    - Validates YAML output before committing
    - Cleans up temp file on any error
    """
    output = Path(output_path).resolve()

    # Check if file exists
    if output.exists() and not force:
        print(f"Config already exists: {output}")
        print("Use force=True to overwrite")
        raise FileExistsError(f"Config exists: {output}")

    try:
        # Check write permission on parent directory
        output.parent.mkdir(parents=True, exist_ok=True)

        # Test write permission
        test_file = output.parent / '.write_test'
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            print(f"ERROR: No write permission on directory: {output.parent}")
            print(f"Solution: Run with sudo or fix permissions:")
            print(f"  sudo chown -R $USER {output.parent}")
            raise

        # Auto-detect hostname
        try:
            raw_hostname = socket.gethostname()
            hostname = sanitize_hostname(raw_hostname)
            print(f"Detected hostname: {raw_hostname} → {hostname}")
        except Exception as e:
            print(f"WARNING: Cannot detect hostname: {e}")
            print("Using fallback: gateway_default")
            hostname = 'gateway_default'

        # Generate config dict
        config = get_default_config_dict(hostname)

        # Atomic write: write to temp file first
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=output.parent,
                prefix='.config_',
                suffix='.tmp',
                delete=False
            ) as tmp:
                # Write YAML
                yaml.dump(
                    config,
                    tmp,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                    width=100
                )
                tmp_path = tmp.name

            # Validate written YAML
            with open(tmp_path, 'r') as f:
                test_load = yaml.safe_load(f)
                if not test_load:
                    raise ValueError("Generated YAML is empty")

            # Atomic rename (replaces existing if force=True)
            shutil.move(tmp_path, output)
            tmp_path = None  # Moved successfully

            print(f"✓ Config generated: {output}")
            print("")
            print("⚠️  IMPORTANT: Edit these values before starting:")
            print(f"   1. mqtt.password (currently: CHANGE_ME)")
            print(f"   2. upload.api_key (currently: CHANGE_ME)")
            print(f"   3. system.location (optional)")
            print("")
            print(f"Edit with: nano {output}")

            return True

        finally:
            # Cleanup temp file if still exists
            if tmp_path and Path(tmp_path).exists():
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass  # Best effort cleanup

    except PermissionError as e:
        print(f"ERROR: Permission denied: {e}")
        print(f"Cannot write to: {output}")
        raise

    except OSError as e:
        print(f"ERROR: OS error: {e}")
        print(f"Possible causes:")
        print(f"  - Disk full")
        print(f"  - Invalid path: {output}")
        print(f"  - Network mount issue")
        raise

    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print(f"Install PyYAML: pip install pyyaml")
        raise

    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        print(f"Please report this issue")
        raise


def main():
    """CLI entry point for config generation"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate default system_config.yaml'
    )
    parser.add_argument(
        'output',
        nargs='?',
        default='./weatherstation/config/system_config.yaml',
        help='Output path for config file'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing config'
    )

    args = parser.parse_args()

    try:
        success = generate_default_config(args.output, force=args.force)
        sys.exit(0 if success else 1)
    except FileExistsError:
        print("Use --force to overwrite")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to generate config: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
