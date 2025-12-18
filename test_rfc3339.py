#!/usr/bin/env python3
"""
Test script to verify RFC 3339 timestamp format
"""

import sys
sys.path.insert(0, '.')

from weatherstation.utils.timestamp_utils import now_rfc3339, utc_now_rfc3339, to_rfc3339, parse_rfc3339
from datetime import datetime

print("=" * 60)
print("RFC 3339 Timestamp Format Test")
print("=" * 60)
print()

# Test 1: Jakarta timezone (WIB)
print("1. Jakarta timezone (WIB +07:00):")
jakarta_time = now_rfc3339()
print(f"   {jakarta_time}")
print(f"   Expected format: YYYY-MM-DDTHH:MM:SS.mmm+07:00")
print()

# Test 2: UTC timezone
print("2. UTC timezone (Z):")
utc_time = utc_now_rfc3339()
print(f"   {utc_time}")
print(f"   Expected format: YYYY-MM-DDTHH:MM:SS.mmmZ")
print()

# Test 3: Convert naive datetime
print("3. Convert naive datetime to RFC 3339:")
naive_dt = datetime(2025, 12, 18, 16, 59, 54, 123456)
converted = to_rfc3339(naive_dt)
print(f"   Input:  {naive_dt}")
print(f"   Output: {converted}")
print()

# Test 4: Parse RFC 3339 string
print("4. Parse RFC 3339 string:")
timestamp_str = "2025-12-18T16:59:54.123+07:00"
parsed = parse_rfc3339(timestamp_str)
print(f"   Input:  {timestamp_str}")
print(f"   Output: {parsed}")
print()

# Test 5: Verify timezone offset
print("5. Verify timezone offset:")
jakarta = now_rfc3339()
utc = utc_now_rfc3339()
print(f"   Jakarta: {jakarta}")
print(f"   UTC:     {utc}")
print(f"   Note: Jakarta should be 7 hours ahead of UTC")
print()

print("=" * 60)
print("All tests completed!")
print("=" * 60)
