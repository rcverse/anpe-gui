"""
ANPE GUI Setup Script for py2app
This script configures py2app to build a standalone macOS app bundle (.app)
that contains all necessary files for running ANPE GUI on macOS.
"""

import sys
import glob
from setuptools import setup
import os
import platform

# Verify we're on macOS
if platform.system() != "Darwin":
    raise RuntimeError("This setup script is for macOS only")

# Application name
APP_NAME = "ANPE GUI"
APP_SCRIPT = 'main_macos.py'

# Define required Python archives (match constants in installer_core_macos.py)
_PBS_VERSION_TAG = "3.11.12+20250409"
_PBS_ARCHIVE_TEMPLATE = f"cpython-{_PBS_VERSION_TAG}-{{arch}}-apple-darwin-install_only.tar.gz"
PBS_ARCHIVE_ARM64 = _PBS_ARCHIVE_TEMPLATE.format(arch="aarch64")
PBS_ARCHIVE_X86_64 = _PBS_ARCHIVE_TEMPLATE.format(arch="x86_64")

# Files/directories to include in the Resources folder
# Add the Python archives here
DATA_FILES = [
    ('assets', glob.glob('anpe_gui/resources/assets/*')),
    ('installer/assets', glob.glob('installer/assets/*')),
    ('installer', ['installer/macos_requirements.txt']),
]

# Create options dict for py2app
py2app_options = {
    'argv_emulation': False,
    'strip': True,
    'packages': [
        'PyQt6',
        'installer',
        'anpe_gui',
    ],
    'includes': [
        'sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'jaraco',
        'jaraco.text',
        'pkg_resources',
    ],
    'excludes': [
        'PySide6',
        'pytest',
        'wheel',
        'spacy',
        'benepar',
        'nltk',
        'tensorflow',
        'torch',
        'transformers',
        'anpe',
    ],
    'iconfile': 'installer/assets/app_icon_mac.icns',
    'resources': [
        'installer/assets',
        'installer/macos_requirements.txt'
    ],
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "Analyze Natural Language Processing Evidence",
        'CFBundleIdentifier': "com.yourcompany.anpe-gui",
        'CFBundleVersion': "0.1.0",
        'CFBundleShortVersionString': "0.1",
        'NSHumanReadableCopyright': u"Copyright © 2024, Your Name or Company. All rights reserved.",
        'LSMinimumSystemVersion': '11.0',
        'PyRuntimeLocations': [
             '@executable_path/../Frameworks/Python.framework/Versions/3.12/Python'
        ]
    },
    'no_strip': False,
    'optimize': 2,
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