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
APP_NAME = "ANPE"
APP_SCRIPT = 'main_macos.py'

# Define required Python archives (match constants in installer_core_macos.py)
_PBS_VERSION_TAG = "3.11.12+20250409"
# IMPORTANT: If you switch to using the _stripped.tar.gz archives (recommended for smaller bundle size),
# ensure this template is updated to:
# _PBS_ARCHIVE_TEMPLATE = f"cpython-{_PBS_VERSION_TAG}-{{arch}}-apple-darwin-install_only_stripped.tar.gz"
_PBS_ARCHIVE_TEMPLATE = f"cpython-{_PBS_VERSION_TAG}-{{arch}}-apple-darwin-install_only.tar.gz"
PBS_ARCHIVE_ARM64 = _PBS_ARCHIVE_TEMPLATE.format(arch="aarch64")
PBS_ARCHIVE_X86_64 = _PBS_ARCHIVE_TEMPLATE.format(arch="x86_64")

# --- Resource Paths ---
PATH_TO_INSTALLER_ASSETS = 'installer_assets'
PATH_TO_ANPE_GUI_ASSETS = 'anpe_gui/resources/assets'
APP_ICON_FILE = os.path.join(PATH_TO_INSTALLER_ASSETS, 'app_icon_mac.icns')

# --- Files from installer_assets to include in Resources/assets ---
PYTHON_ARCHIVE_ARM64_PATH = os.path.join(PATH_TO_INSTALLER_ASSETS, PBS_ARCHIVE_ARM64)
PYTHON_ARCHIVE_X86_64_PATH = os.path.join(PATH_TO_INSTALLER_ASSETS, PBS_ARCHIVE_X86_64)
MACOS_REQUIREMENTS_PATH = os.path.join(PATH_TO_INSTALLER_ASSETS, 'macos_requirements.txt')

INSTALLER_ASSET_FILES_TO_INCLUDE = [
    os.path.join(PATH_TO_INSTALLER_ASSETS, 'app_icon_logo.png'),
    os.path.join(PATH_TO_INSTALLER_ASSETS, 'error.png'),
    os.path.join(PATH_TO_INSTALLER_ASSETS, 'LICENSE.installer.txt'),
    os.path.join(PATH_TO_INSTALLER_ASSETS, 'success.png'),
    PYTHON_ARCHIVE_ARM64_PATH,
    PYTHON_ARCHIVE_X86_64_PATH,
    MACOS_REQUIREMENTS_PATH,
]

# --- DATA_FILES: For files requiring specific subdirectory placement in Resources ---
DATA_FILES = [
    # ('installer_macos', ['installer_macos/macos_requirements.txt']) # REMOVED - handled by OPTIONS['resources']
]

# --- py2app Options ---
OPTIONS = {
    'argv_emulation': False,
    'iconfile': APP_ICON_FILE,
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': f"{APP_NAME}: The user-friendly way to extract noun phrases!",
        'CFBundleIdentifier': "com.rcverse.anpe-gui",
        'CFBundleVersion': "0.1.0",
        'CFBundleShortVersionString': "0.1.0",
        'NSHumanReadableCopyright': u"Copyright © 2024, Richard Chen. All rights reserved.",
        'LSMinimumSystemVersion': '11.0',
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'LSUIElement': '0'
    },
    'packages': [
        'PyQt6',
        'installer_macos',
        'anpe_gui',
        # Add other top-level packages your app directly uses if not automatically found
    ],
    'includes': [
        # For modules that py2app might miss, especially if dynamically imported
        # e.g., 'sip', 'some_package.some_module'
        'shutil',
        'multiprocessing',
        'http.client', # for benepar
        'ssl', # for benepar, nltk
        'packaging.requirements', # for pip
        'packaging.version',      # for pip
        'pkg_resources',          # some packages might still use it
    ],
    'excludes': [
        'PySide6',
        # PyQt6 modules (keep this list, adjust if you find you need some)
        'PyQt6.QtDesigner', 'PyQt6.QtHelp', 'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets', 'PyQt6.QtNetwork', 'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets',
        'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport', 'PyQt6.QtQml',
        'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets',
        'PyQt6.QtRemoteObjects', 'PyQt6.QtScxml', 'PyQt6.QtSensors',
        'PyQt6.QtSerialPort', 'PyQt6.QtSql', 'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets', 'PyQt6.QtTest', 'PyQt6.QtWebChannel',
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineQuick',
        'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebView', 'PyQt6.QtBluetooth',
        'PyQt6.Qsci', # If you included QScintilla, but usually not by default

        # Exclude large libraries that should be handled by the installer
        'spacy', 'benepar', 'nltk', 'tensorflow', 'torch', 'transformers', 'anpe',

        # Other common large/unneeded libraries
        'numpy.core._dotblas', # Often problematic and large if not used directly
        'scipy', # If not used by the core app GUI
        'pandas', # If not used by the core app GUI
        'matplotlib', # If not used by the core app GUI
        'setuptools', # Installer handles this for its env
        'pip',        # Installer handles this for its env

        # Standard library modules not typically needed for a GUI app
        'unittest', 'test', 'tests', 'pydoc_data', 'distutils', 'lib2to3',
        'ensurepip', ' tkinter', 'tcl', 'tk', 'sqlite3', 'dbm', 'xmlrpc',
        'curses', 'idlelib', 'msilib',
        # Caution with these, ensure no part of your app or minimal PyQt uses them
        # 'email', 'http', 'logging.config', 'concurrent', 'ctypes.test', 'multiprocessing.popen_spawn_posix'
    ],
    'frameworks': [], # e.g., '/path/to/custom.framework'
    'datamodels': [],
    'compressed': True, # True can sometimes make startup slower, False for easier debugging
    'optimize': 2, # 0 for no .pyo files (easier debugging), 1 for .pyo, 2 for .pyo and no .pyc docstrings
    'strip': True,
    'resources': [
        # Copy contents of anpe_gui/resources/assets/* into Resources/assets/ - REMOVED as py2app bundles package contents
        # ('assets', glob.glob(os.path.join(PATH_TO_ANPE_GUI_ASSETS, '*'))),
        # Copy specific files from INSTALLER_ASSET_FILES_TO_INCLUDE into Resources/assets/
        # This will place them like: Contents/Resources/assets/cpython-...tar.gz, Contents/Resources/assets/macos_requirements.txt
        ('assets', INSTALLER_ASSET_FILES_TO_INCLUDE)
    ],
    'emulate_shell_environment': True,
    'no_strip': False # Redundant if 'strip' is True
}

setup_args = dict(
    name=APP_NAME,
    version="1.0.0",
    description=f"{APP_NAME}: The user-friendly way to extract noun phrases.",
    author="Richard Chen",
    author_email="rcverse6@gmail.com",
    url="https://github.com/rcverse/anpe-gui",
    app=[APP_SCRIPT],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app', 'setuptools'],
    # exclude_package_data REMOVED for now
)

if __name__ == '__main__':
    setup(**setup_args)

# Print instructions for building the app
print("""
To build the ANPE GUI app bundle:

1. Install py2app if not already installed:
   pip install py2app

2. Build the app:
   python setup.py py2app

The built app will be in the 'dist' directory.
""") 