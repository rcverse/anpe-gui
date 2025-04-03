#!/usr/bin/env python3
"""
Entry point for the ANPE GUI application when run as a module.
"""

import sys
import os

# Add the parent directory to sys.path to allow importing anpe_gui as a package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can import from anpe_gui
from anpe_gui.app import main

if __name__ == "__main__":
    main() 