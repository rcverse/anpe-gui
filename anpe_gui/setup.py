"""
Setup script for packaging the ANPE GUI application.
"""

import sys
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": ["anpe", "PyQt6", "os", "sys", "traceback", "logging"],
    "excludes": ["tkinter", "matplotlib", "notebook", "scipy", "pandas"],
    "include_files": [],
    "optimize": 2,
}

# Base for the executable
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Use this to hide the console on Windows

setup(
    name="ANPE GUI",
    version="0.1.0",
    description="Graphical User Interface for Another Noun Phrase Extractor",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "app.py",
            base=base,
            target_name="anpe_gui.exe" if sys.platform == "win32" else "anpe_gui",
            icon=None,  # Add an icon if available
        )
    ],
) 