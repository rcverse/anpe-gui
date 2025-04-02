#!/usr/bin/env python3
"""
Run the ANPE GUI application.
"""

import sys
import os

# Ensure the anpe_gui package is in the path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from anpe_gui.app import main

if __name__ == "__main__":
    main() 