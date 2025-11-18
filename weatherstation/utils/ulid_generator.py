"""
ULID (Universally Unique Lexicographically Sortable Identifier) Generator

Generates ULID-compatible IDs without external dependencies.
Format: 26 characters (timestamp + randomness)
Example: 01K9RSSBEVE5X1CV7ZGTB46MZP
"""

import time
import random
import string


# Crockford's Base32 alphabet (excludes I, L, O, U to avoid confusion)
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """
    Generate a ULID-compatible identifier

    Format:
    - First 10 chars: Timestamp (milliseconds since epoch)
    - Last 16 chars: Random component

    Returns:
        26-character ULID string
    """
    # Get current timestamp in milliseconds
    timestamp_ms = int(time.time() * 1000)

    # Encode timestamp (10 characters)
    timestamp_part = _encode_timestamp(timestamp_ms, 10)

    # Generate random component (16 characters)
    random_part = _encode_random(16)

    return timestamp_part + random_part


def _encode_timestamp(timestamp_ms: int, length: int) -> str:
    """
    Encode timestamp to base32 string

    Args:
        timestamp_ms: Timestamp in milliseconds
        length: Length of encoded string

    Returns:
        Base32 encoded timestamp
    """
    result = []
    for _ in range(length):
        result.append(ALPHABET[timestamp_ms % 32])
        timestamp_ms //= 32

    return ''.join(reversed(result))


def _encode_random(length: int) -> str:
    """
    Generate random base32 string

    Args:
        length: Length of random string

    Returns:
        Random base32 string
    """
    return ''.join(random.choices(ALPHABET, k=length))


if __name__ == '__main__':
    # Test ULID generation
    print("Generated ULIDs:")
    for _ in range(5):
        ulid = generate_ulid()
        print(f"  {ulid}")

    # Test uniqueness
    ulids = set()
    for _ in range(1000):
        ulids.add(generate_ulid())

    print(f"\nGenerated {len(ulids)} unique ULIDs (expected 1000)")
    print(f"Format: {len(generate_ulid())} characters")
