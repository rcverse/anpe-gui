# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_entry_point
import os
import sys
from pathlib import Path

# Add parent directory (containing installer/) to sys.path
# This helps PyInstaller resolve relative imports within the installer package
spec_dir = os.path.abspath('.')
if spec_dir not in sys.path:
    sys.path.insert(0, spec_dir)

block_cipher = None

# --- Configuration ---
APP_NAME = 'ANPE_Installer'
SCRIPT_FILE = 'installer/setup_windows.pyw'
INSTALLER_ICON_FILE = 'installer/assets/app_icon_logo.ico' # Reusing app icon

# --- Paths to items to bundle (Relative to this spec file) ---
PYTHON_ZIP_SOURCE = 'installer/assets/python-3.12.9-embed-amd64.zip'
APP_SOURCE_DIR = 'anpe_gui'
DOCS_SOURCE_DIR = 'docs'
REQUIREMENTS_SOURCE = 'requirements.txt'
INSTALLER_ASSETS_SOURCE = 'installer/assets'
PREBUILT_LAUNCHER_SOURCE = 'dist/ANPE.exe' # Assumes built ANPE.exe is here
PREBUILT_UNINSTALLER_SOURCE = 'dist/uninstall.exe' # Assumes built uninstall.exe is here

# --- Target paths within the bundle ---
# These must match what installer_core.py expects via get_resource_path
PYTHON_ZIP_TARGET = 'assets'
APP_TARGET_DIR = 'assets/anpe_gui' # installer_core copies from assets/anpe_gui
DOCS_TARGET_DIR = 'assets/docs' # installer_core copies from assets/docs
REQUIREMENTS_TARGET = 'assets' # installer_core looks for it in assets
INSTALLER_ASSETS_TARGET = 'assets' # For installer GUI's own assets (logo, etc.)
PREBUILT_LAUNCHER_TARGET = 'assets' # installer_core copies ANPE.exe from assets
PREBUILT_UNINSTALLER_TARGET = 'assets' # installer_core copies uninstall.exe from assets


# --- Collect data files ---
bundled_data = []

# 1. Embeddable Python
bundled_data.append((PYTHON_ZIP_SOURCE, PYTHON_ZIP_TARGET))

# 2. Application Source Code (anpe_gui) - Use direct tuple
# PyInstaller typically excludes __pycache__ automatically with dir copy
bundled_data.append((APP_SOURCE_DIR, APP_TARGET_DIR))
# Old way using collect_data_files removed:
# app_files = collect_data_files(APP_SOURCE_DIR, 
#                                excludes=['**/__pycache__', '**/*.pyc'])
# bundled_data.extend(app_files)

# 3. Documentation (docs) (REMOVED)
# doc_files = collect_data_files(DOCS_SOURCE_DIR, 
#                                destdir=DOCS_TARGET_DIR,
#                                # Only include specific files if needed, e.g., *.md
#                                # includes=['*.md']) 
#                               ) 
# bundled_data.extend(doc_files) 

# 4. Requirements file
bundled_data.append((REQUIREMENTS_SOURCE, REQUIREMENTS_TARGET))

# 5. Installer packages
# This is essential - add the entire installer folder as a module package
# It will include views, widgets, etc. all while preserving package structure
installer_dir = 'installer'
bundled_data.append((installer_dir, 'installer'))

# 6. Installer Assets (icons, etc. needed by setup_windows.pyw GUI itself)
# Remove destdir, manually construct target path
installer_assets_raw = collect_data_files(INSTALLER_ASSETS_SOURCE, 
                                          include_py_files=False)
installer_assets_filtered = []
allowed_files = [
    'app_icon_logo.png', 'success.png', 'error.png', 'LICENSE.installer.txt',
    'app_icon_logo.ico' # Ensure icon is included if needed by GUI directly
    # Add other needed assets here
]
for src, _ in installer_assets_raw: # Original destination path is ignored
    filename = os.path.basename(src)
    if filename in allowed_files:
        # Construct target path: place file directly under INSTALLER_ASSETS_TARGET directory
        target_path = os.path.join(INSTALLER_ASSETS_TARGET, filename).replace('\\', '/') # Use forward slashes
        installer_assets_filtered.append((src, target_path))
bundled_data.extend(installer_assets_filtered)
# Old way using collect_data_files with destdir removed:
# installer_assets = collect_data_files(INSTALLER_ASSETS_SOURCE, 
#                                       destdir=INSTALLER_ASSETS_TARGET,
#                                       include_py_files=False) 
# installer_assets = [(s, d) for s, d in installer_assets if os.path.basename(s) in [
#     'app_icon_logo.png', 'success.svg', 'error.svg', 'LICENSE.installer.txt' 
# ]]
# bundled_data.extend(installer_assets)


# 7. Pre-built Launcher (ANPE.exe)
bundled_data.append((PREBUILT_LAUNCHER_SOURCE, PREBUILT_LAUNCHER_TARGET))

# 8. Pre-built Uninstaller (uninstall.exe)
bundled_data.append((PREBUILT_UNINSTALLER_SOURCE, PREBUILT_UNINSTALLER_TARGET))

# --- Collect PyQt6 ---
pyqt6_datas, pyqt6_binaries = collect_entry_point('PyQt6')

# --- Analysis ---
a = Analysis([SCRIPT_FILE],
             pathex=[],
             binaries=pyqt6_binaries,
             datas=bundled_data + pyqt6_datas, # Combine all bundled data
             hiddenimports=[
                 # Imports needed by setup_windows.pyw and its dependencies
                 'PyQt6.sip', 
                 'PyQt6.QtGui', 
                 'PyQt6.QtWidgets', 
                 'PyQt6.QtCore',
                 'installer',  # Add the whole installer package
                 'installer.widgets',
                 'installer.widgets.custom_title_bar',
                 'installer.views',
                 'installer.views.welcome_view', 
                 'installer.views.progress_view',
                 'installer.views.completion_view', 
                 'installer.workers',
                 'installer.workers.env_setup_worker',
                 'installer.workers.model_setup_worker',
                 'installer.installer_core', # Core logic
                 'installer.utils',
                 'winreg', # For registry operations
                 'pyshortcuts', # For creating shortcuts
                 'pathlib',
                 # Add other indirect imports if build fails
             ],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[
                 'tkinter',
                 'unittest',
                 'xml',
                 'pydoc_data',
                 'sqlite3',
                 # Exclude potentially unused PyQt6 modules (TEST CAREFULLY)
                 'PyQt6.QtWebEngineWidgets',
                 'PyQt6.QtWebEngineCore',
                 'PyQt6.QtWebChannel',
                 'PyQt6.QtMultimedia',
                 'PyQt6.QtSql',
                 'PyQt6.QtNetwork', # Keep? Often needed indirectly.
                 'PyQt6.QtTest',
                 # Add other specific exclusions if needed
             ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

# --- PYZ ---
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- EXE ---
exe = EXE(pyz,
          a.scripts,
          a.binaries,  # Include binaries directly in the EXE
          a.zipfiles,  # Include zipfiles directly in the EXE
          a.datas,     # Include data files directly in the EXE
          [],
          exclude_binaries=False,  # Changed from implicit True
          name=APP_NAME,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False, # Installer is a GUI application
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon=INSTALLER_ICON_FILE)

# Removed COLLECT section for true one-file build
# --- COLLECT ---
# coll = COLLECT(exe,
#                a.binaries,
#                a.zipfiles,
#                a.datas,
#                strip=False,
#                upx=True,
#                upx_exclude=[],
#                name=APP_NAME)

print(f"--- {APP_NAME}.spec Configuration ---")
print(f"SCRIPT: {SCRIPT_FILE}")
print(f"ICON: {INSTALLER_ICON_FILE}")
print(f"CONSOLE: False")
print(f"Bundling Python from: {PYTHON_ZIP_SOURCE}")
print(f"Bundling App Code from: {APP_SOURCE_DIR}")
print(f"Bundling Docs from: {DOCS_SOURCE_DIR}")
print(f"Bundling Requirements from: {REQUIREMENTS_SOURCE}")
print(f"Bundling Launcher from: {PREBUILT_LAUNCHER_SOURCE}")
print(f"Bundling Uninstaller from: {PREBUILT_UNINSTALLER_SOURCE}")
print(f"Total data items collected for bundling: {len(bundled_data)}")
print(f"Hidden Imports: {a.hiddenimports}")
print("--- End Spec Configuration ---") 