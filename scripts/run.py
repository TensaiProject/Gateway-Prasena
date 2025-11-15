#!/usr/bin/env python3
"""
Gateway entry point script
Wrapper for weatherstation.main with proper path handling
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import and run main
from weatherstation.main import main

if __name__ == '__main__':
    sys.exit(main())
