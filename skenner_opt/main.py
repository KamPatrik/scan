#!/usr/bin/env python3
"""
SkennerOpt - Film Scanning Software
Entry point for the application.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner_app.app import run_app

if __name__ == "__main__":
    run_app()
