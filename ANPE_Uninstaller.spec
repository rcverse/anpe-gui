# -*- mode: python ; coding: utf-8 -*-

import os 

block_cipher = None

# --- Application Configuration ---
APP_NAME = 'uninstall'
# --- SCRIPT PATH: Ensure this points to the Tkinter version --- 
SCRIPT_FILE = 'installer/uninstall.pyw' # Or uninstall_tk.py? Verify filename.
# --- ICON PATH: Update if needed, using app icon for now --- 
ICON_FILE = 'installer/assets/app_icon_logo.ico'
# --- ASSETS: Add logo image for Tkinter UI ---
ASSETS_SOURCE_DIR = 'installer/assets'
# Removed logo file inclusion - it's now base64 embedded
# LOGO_FILE = 'app_icon_logo.png'  # Logo file for display in the UI

# Removed PyQt6 data/binary collection
# pyqt6_datas, pyqt6_binaries = collect_entry_point('PyQt6')

# Removed asset collection for PyQt6 GUI
# asset_data = collect_data_files(ASSETS_SOURCE_DIR, ...)
# asset_data = ...

a = Analysis([
        SCRIPT_FILE
    ],
    pathex=[],
    binaries=[], # No extra binaries needed for Tkinter
    datas=[], # No external data files needed anymore
    hiddenimports=[
        # Removed PIL imports as they are no longer used
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep standard excludes, but ensure tkinter is NOT excluded
        'unittest',
        'email',
        'xml',
        'pydoc_data',
        'sqlite3',
        'PyQt6', # Explicitly exclude PyQt6 and related modules
        'PyQt5',
        'PySide6',
        'PySide2',
        # --- Added more aggressive exclusions ---
        'multiprocessing',
        'xmlrpc',
        'distutils',
        'curses',
        'asyncio',
        'bz2',
        'lzma',
        'tkinter.test',
        'idlelib',
        # Add other specific exclusions if needed
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, 
          cipher=block_cipher,
          optimize=2 # Add Python optimization level 2 (-OO)
          )

exe = EXE(pyz, 
    a.scripts,
    a.binaries,  # Include binaries directly in the EXE
    a.zipfiles,  # Include zipfiles directly in the EXE
    a.datas,     # Include data files directly in the EXE
    [],
    exclude_binaries=False,  # Changed from True to False
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True, # --- Enabled stripping ---
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # --- CONSOLE SETTING --- 
    # Set console=True if Tkinter script uses print for errors/feedback
    # Set console=False if it's purely windowed with message boxes
    console=False, # Defaulting to True for Tkinter script, adjust if needed
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE
)

# Removed COLLECT section for true one-file build
# coll = COLLECT(exe,
#    a.binaries, 
#    a.zipfiles,
#    a.datas,
#    strip=False,
#    upx=True,
#    upx_exclude=[],
#    name=APP_NAME
# ) 