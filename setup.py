"""
ANPE GUI Setup Script for py2app
This script configures py2app to build a standalone macOS app bundle (.app)
that contains all necessary files for running ANPE GUI on macOS.
"""

import sys
from setuptools import setup
import os
import glob
import platform

# Verify we're on macOS
if platform.system() != "Darwin":
    raise RuntimeError("This setup script is for macOS only")

# Application name
APP_NAME = "ANPE GUI"
APP_SCRIPT = 'main_macos.py'

# Define required Python archives (match constants in installer_core_macos.py)
_PBS_VERSION_TAG = "3.12.10+20250409"
_PBS_ARCHIVE_TEMPLATE = f"cpython-{_PBS_VERSION_TAG}-{{arch}}-apple-darwin-install_only_stripped.tar.gz"
PBS_ARCHIVE_ARM64 = _PBS_ARCHIVE_TEMPLATE.format(arch="aarch64")
PBS_ARCHIVE_X86_64 = _PBS_ARCHIVE_TEMPLATE.format(arch="x86_64")

# Files/directories to include in the Resources folder
# Add the Python archives here
DATA_FILES = [
    'installer/assets/app_icon.icns', 
    'installer/assets/success_icon.png',
    'installer/assets/error_icon.png',
    f'installer/assets/{PBS_ARCHIVE_ARM64}', # ARM64 Python archive
    f'installer/assets/{PBS_ARCHIVE_X86_64}', # x86_64 Python archive
    'installer/macos_requirements.txt', # Requirements for the setup process
]

# Create options dict for py2app
py2app_options = {
    'argv_emulation': True,
    'strip': True,
    'packages': [
        'PyQt6',      # Needed for Installer UI and main app UI shell
        'installer',  # First-run setup logic and UI views
        # REMOVED: 'spacy', 'benepar', 'anpe' - these are installed by the setup wizard
    ],
    'includes': [
        'sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    'excludes': [
        # Exclude packages installed by the setup wizard
        'spacy',
        'benepar',
        'anpe',
        'torch', # Explicitly exclude torch and its variants
        'torchvision',
        'torchaudio',
        
        # General exclusions
        'tkinter',
        'matplotlib',
        'numpy', # Exclude numpy if it's only needed by spacy/torch/etc.
        'scipy',
        'pandas',
        'PyQt5',
        'PySide2',
        'PySide6',
        'pytest',
    ],
    'iconfile': 'installer/assets/app_icon.icns',  # Ensure this .icns file exists
    'resources': [
        'installer/assets',  # Copy contents of installer/assets to Resources dir
        'installer/macos_requirements.txt' # Explicitly copy the requirements file to Resources root
    ],
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "Analyze Natural Language Processing Evidence",
        'CFBundleIdentifier': "com.yourcompany.anpe-gui", # CHANGE THIS to your bundle identifier
        'CFBundleVersion': "0.1.0", # CHANGE THIS to your app version
        'CFBundleShortVersionString': "0.1", # CHANGE THIS
        'NSHumanReadableCopyright': u"Copyright © 2024, Your Name or Company. All rights reserved.", # CHANGE THIS
        'LSMinimumSystemVersion': '11.0' # Require macOS Big Sur or later (adjust if needed)
    },
}

setup(
    name=APP_NAME,
    app=[APP_SCRIPT],
    data_files=DATA_FILES,
    options={
        'py2app': py2app_options
    },
    setup_requires=['py2app'],
)

# Print instructions for building the app
print("""
To build the ANPE GUI app bundle:

1. Install py2app if not already installed:
   pip install py2app

2. Build the app:
   python setup.py py2app

The built app will be in the 'dist' directory.
""") 