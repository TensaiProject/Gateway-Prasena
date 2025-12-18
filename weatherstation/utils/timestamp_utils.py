"""
Timestamp utilities for RFC 3339 compliant timestamps.

RFC 3339 is an internet timestamp format that includes timezone information.
Format: YYYY-MM-DDTHH:MM:SS.mmm+HH:MM

Example: 2025-12-18T16:59:54.123+07:00
"""

from datetime import datetime
from zoneinfo import ZoneInfo


# Jakarta timezone (WIB - UTC+7)
JAKARTA_TZ = ZoneInfo('Asia/Jakarta')


def now_rfc3339() -> str:
    """
    Get current timestamp in RFC 3339 format with Jakarta timezone.

    Returns:
        str: Timestamp in RFC 3339 format (e.g., "2025-12-18T16:59:54.123+07:00")

    Example:
        >>> now_rfc3339()
        '2025-12-18T16:59:54.123456+07:00'
    """
    return datetime.now(JAKARTA_TZ).isoformat(timespec='milliseconds')


def utc_now_rfc3339() -> str:
    """
    Get current UTC timestamp in RFC 3339 format.

    Returns:
        str: Timestamp in RFC 3339 format (e.g., "2025-12-18T09:59:54.123Z")

    Example:
        >>> utc_now_rfc3339()
        '2025-12-18T09:59:54.123Z'
    """
    return datetime.now(ZoneInfo('UTC')).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def to_rfc3339(dt: datetime) -> str:
    """
    Convert a datetime object to RFC 3339 format string.

    Args:
        dt: datetime object (naive or timezone-aware)

    Returns:
        str: Timestamp in RFC 3339 format

    Example:
        >>> dt = datetime(2025, 12, 18, 16, 59, 54)
        >>> to_rfc3339(dt)
        '2025-12-18T16:59:54.000+07:00'
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in Jakarta timezone
        dt = dt.replace(tzinfo=JAKARTA_TZ)
    return dt.isoformat(timespec='milliseconds')


def parse_rfc3339(timestamp_str: str) -> datetime:
    """
    Parse RFC 3339 timestamp string to datetime object.

    Args:
        timestamp_str: RFC 3339 formatted timestamp string

    Returns:
        datetime: Timezone-aware datetime object

    Example:
        >>> parse_rfc3339('2025-12-18T16:59:54.123+07:00')
        datetime(2025, 12, 18, 16, 59, 54, 123000, tzinfo=...)
    """
    # Handle 'Z' suffix for UTC
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str[:-1] + '+00:00'

    return datetime.fromisoformat(timestamp_str)
