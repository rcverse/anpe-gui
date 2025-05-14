# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# --- Application Configuration ---
APP_NAME = 'anpe'
SCRIPT_FILE = 'launcher.py'
# --- ICON PATH: Update this path if your icon is located elsewhere ---
ICON_FILE = 'installer/assets/app_icon_logo.ico' 

a = Analysis([
        SCRIPT_FILE
    ],
    pathex=[],
    binaries=[],
    datas=[], # Launcher doesn't typically need data files
    hiddenimports=[
        # Add any hidden imports launcher.py might need, although it's usually simple
        # 'ctypes' is usually handled automatically
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'xml',
        'pydoc_data',
        'sqlite3',
        # Add other specific exclusions if needed
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz, 
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Set to False for a windowed app (no console flash)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE # Specify the application icon
)

# Removed COLLECT section for true one-file build
# coll = COLLECT(exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name=APP_NAME
# ) 