"""
Configuration Validator
Validates system_config.yaml with comprehensive error checking

Error handling:
- File not found → clear instructions
- YAML syntax errors → line number and issue
- Missing required sections → list what's missing
- Invalid data types → specify expected type
- Placeholder values → warn about CHANGE_ME
- Invalid values → range/format validation
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


class ConfigValidator:
    """
    Validates configuration file structure and values
    Provides detailed error messages for troubleshooting
    """

    # Required top-level sections
    REQUIRED_SECTIONS = ['system', 'database', 'mqtt', 'upload', 'logging']

    # Required nested keys (section: [required_keys])
    REQUIRED_KEYS = {
        'system': ['name', 'location', 'timezone'],
        'database': ['path'],
        'mqtt': ['broker_host', 'broker_port', 'username', 'password'],
        'upload': ['enabled', 'main_server_url', 'api_key'],
        'logging': ['level', 'log_to_file']
    }

    # Type validation (key_path: expected_type)
    TYPE_VALIDATIONS = {
        'mqtt.broker_port': int,
        'mqtt.qos': int,
        'mqtt.keepalive': int,
        'upload.enabled': bool,
        'upload.interval': (int, float),
        'upload.batch_size': int,
        'upload.timeout': (int, float),
        'battery_sensors.enabled': bool,
        'battery_sensors.poll_interval': (int, float),
        'weather_station.enabled': bool,
        'weather_station.http_port': int,
        'logging.log_to_file': bool,
        'logging.max_file_size': int,
        'logging.backup_count': int
    }

    # Range validations (key_path: (min, max))
    RANGE_VALIDATIONS = {
        'mqtt.broker_port': (1, 65535),
        'mqtt.qos': (0, 2),
        'mqtt.keepalive': (1, 3600),
        'upload.interval': (1, 86400),
        'upload.batch_size': (1, 10000),
        'upload.timeout': (1, 300),
        'weather_station.http_port': (1, 65535),
        'logging.max_file_size': (1024, 1073741824),  # 1KB to 1GB
        'logging.backup_count': (1, 100)
    }

    @staticmethod
    def get_nested_value(config: Dict, key_path: str) -> Any:
        """
        Get value from nested dict using dot notation
        Example: get_nested_value(config, 'mqtt.broker_port')
        """
        keys = key_path.split('.')
        value = config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return None
            else:
                return None
        return value

    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration dictionary

        Args:
            config: Configuration dictionary loaded from YAML

        Returns:
            Tuple of (is_valid, error_messages)
            - is_valid: True if all validations pass
            - error_messages: List of validation errors (empty if valid)
        """
        errors = []

        # 1. Check required sections
        for section in self.REQUIRED_SECTIONS:
            if section not in config:
                errors.append(f"Missing required section: [{section}]")
            elif not isinstance(config[section], dict):
                errors.append(f"Section [{section}] must be a dictionary/object")

        # 2. Check required keys within sections
        for section, required_keys in self.REQUIRED_KEYS.items():
            if section not in config:
                continue  # Already reported as missing section

            section_data = config.get(section, {})
            if not isinstance(section_data, dict):
                continue  # Already reported as wrong type

            for key in required_keys:
                if key not in section_data:
                    errors.append(f"Missing required key: {section}.{key}")
                elif section_data[key] is None:
                    errors.append(f"Required key cannot be null: {section}.{key}")

        # 3. Check for placeholder values (CHANGE_ME)
        warnings = []
        mqtt_password = self.get_nested_value(config, 'mqtt.password')
        if mqtt_password == 'CHANGE_ME':
            errors.append(
                "mqtt.password is still set to 'CHANGE_ME' - "
                "you must change this before deployment"
            )

        upload_api_key = self.get_nested_value(config, 'upload.api_key')
        if upload_api_key == 'CHANGE_ME':
            errors.append(
                "upload.api_key is still set to 'CHANGE_ME' - "
                "you must change this before deployment"
            )

        # 4. Type validations
        for key_path, expected_type in self.TYPE_VALIDATIONS.items():
            value = self.get_nested_value(config, key_path)
            if value is None:
                continue  # Missing keys already reported

            # Handle tuple of allowed types
            if isinstance(expected_type, tuple):
                if not isinstance(value, expected_type):
                    type_names = ' or '.join(t.__name__ for t in expected_type)
                    errors.append(
                        f"Invalid type for {key_path}: "
                        f"expected {type_names}, got {type(value).__name__}"
                    )
            else:
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Invalid type for {key_path}: "
                        f"expected {expected_type.__name__}, got {type(value).__name__}"
                    )

        # 5. Range validations
        for key_path, (min_val, max_val) in self.RANGE_VALIDATIONS.items():
            value = self.get_nested_value(config, key_path)
            if value is None:
                continue  # Missing keys already reported

            # Only validate if it's a number
            if isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    errors.append(
                        f"Value out of range for {key_path}: "
                        f"{value} (valid range: {min_val}-{max_val})"
                    )

        # 6. Format validations
        # URL format for upload endpoint
        upload_url = self.get_nested_value(config, 'upload.main_server_url')
        if upload_url and isinstance(upload_url, str):
            if not (upload_url.startswith('http://') or upload_url.startswith('https://')):
                errors.append(
                    f"Invalid URL format for upload.main_server_url: {upload_url} "
                    f"(must start with http:// or https://)"
                )

        # Log level validation
        log_level = self.get_nested_value(config, 'logging.level')
        if log_level:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if str(log_level).upper() not in valid_levels:
                errors.append(
                    f"Invalid logging.level: {log_level} "
                    f"(valid: {', '.join(valid_levels)})"
                )

        # Timezone validation (basic check)
        timezone = self.get_nested_value(config, 'system.timezone')
        if timezone and isinstance(timezone, str):
            # Basic format check (e.g., Asia/Jakarta, America/New_York)
            if '/' not in timezone:
                warnings.append(
                    f"Suspicious timezone format: {timezone} "
                    f"(expected format: Continent/City, e.g., Asia/Jakarta)"
                )

        return (len(errors) == 0, errors)


def load_and_validate_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate configuration file
    Provides detailed error messages for all failure scenarios

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated configuration dictionary

    Raises:
        FileNotFoundError: Config file doesn't exist
        yaml.YAMLError: Config file has YAML syntax errors
        ConfigValidationError: Config validation failed

    Error handling:
    - File not found → instructions to generate config
    - Empty file → clear error message
    - YAML syntax error → line number and description
    - Validation errors → list all issues with solutions
    """
    config_file = Path(config_path).resolve()

    # Check if file exists
    if not config_file.exists():
        error_msg = f"""
Configuration file not found: {config_file}

Solutions:
1. Run installation script:
   bash scripts/install.sh

2. Generate config manually:
   python3 -m weatherstation.config.config_generator {config_file}

3. Copy from example:
   cp weatherstation/config/system_config.yaml.example {config_file}
   nano {config_file}  # Edit mqtt.password and upload.api_key
"""
        raise FileNotFoundError(error_msg)

    # Check if file is readable
    if not config_file.is_file():
        raise ValueError(f"Path is not a file: {config_file}")

    try:
        # Load YAML
        with open(config_file, 'r') as f:
            content = f.read()

        # Check for empty file
        if not content.strip():
            raise ValueError(
                f"Configuration file is empty: {config_file}\n"
                f"Delete it and run: python3 -m weatherstation.config.config_generator"
            )

        # Parse YAML
        config = yaml.safe_load(content)

        # Check if YAML is null/None
        if config is None:
            raise ValueError(
                f"Configuration file parsed as null/empty: {config_file}\n"
                f"Check YAML syntax or regenerate config"
            )

    except yaml.YAMLError as e:
        error_msg = f"""
YAML syntax error in configuration file: {config_file}

Error details:
{e}

Solutions:
1. Fix YAML syntax manually
2. Regenerate config: python3 -m weatherstation.config.config_generator --force
3. Restore from backup if available
"""
        raise yaml.YAMLError(error_msg)

    except Exception as e:
        raise Exception(f"Failed to read config file {config_file}: {e}")

    # Validate configuration
    validator = ConfigValidator()
    is_valid, errors = validator.validate(config)

    if not is_valid:
        error_msg = f"""
Configuration validation failed: {config_file}

Errors found:
"""
        for i, error in enumerate(errors, 1):
            error_msg += f"  {i}. {error}\n"

        error_msg += f"""
Edit configuration file: nano {config_file}

Required changes:
- Set mqtt.password (remove 'CHANGE_ME')
- Set upload.api_key (remove 'CHANGE_ME')
- Fix any type/range errors listed above
"""
        raise ConfigValidationError(error_msg)

    return config


def main():
    """CLI entry point for config validation"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Validate system configuration')
    parser.add_argument(
        'config',
        nargs='?',
        default='./weatherstation/config/system_config.yaml',
        help='Path to config file'
    )

    args = parser.parse_args()

    try:
        config = load_and_validate_config(args.config)
        print(f"✓ Configuration valid: {args.config}")
        print(f"  - {len(config)} sections loaded")
        print(f"  - MQTT client: {config.get('mqtt', {}).get('client_id', 'auto-generated')}")
        print(f"  - Upload endpoint: {config.get('upload', {}).get('main_server_url')}")
        sys.exit(0)
    except (FileNotFoundError, yaml.YAMLError, ConfigValidationError, Exception) as e:
        print(f"✗ Configuration validation failed:\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
