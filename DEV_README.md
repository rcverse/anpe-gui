# ANPE Studio - Developer Documentation

This document provides guidance for developers interested in contributing to the ANPE Studio project, building it from source, or understanding its internal structure.

---

## Table of Contents

*   [Project Overview](#project-overview)
*   [Getting Started](#getting-started)
*   [Project Structure](#project-structure)
*   [Key Modules](#key-modules)
*   [Dependencies](#dependencies)
*   [Building the Application](#building-the-application)
    *   [Windows](#windows)
    *   [macOS (Experimental)](#macos-experimental)
*   [Code Style and Conventions](#code-style-and-conventions)
*   [Testing](#testing)
*   [Contributing](#contributing)

---

## Project Overview

ANPE Studio is a Python application built with PyQt6 that provides a graphical user interface for the [ANPE core library](https://github.com/rcverse/another-noun-phrase-extractor). It allows users to extract noun phrases from text or files without needing programming knowledge.

Due to the large size of dependencies (spaCy, Benepar, NLTK, which can include PyTorch), creating a fully self-contained bundled application with tools like PyInstaller or py2app results in an excessively large distributable. To address this, ANPE Studio employs a custom installer-based approach for both Windows and macOS. These installers are themselves Python applications (built with PyInstaller for Windows, and likely using a similar approach for the macOS `.app` wrapper around `main_macos.py`) that:
1.  Deploy a standalone, embedded Python environment.
2.  Install the `anpe-studio` application and its dependencies (`requirements.txt`) into this environment.
3.  Create necessary launchers/shortcuts.

This project includes:
*   The main GUI application source code (`anpe_studio/`).
*   Source code for the Windows installer GUI (`installer/`).
*   Source code for the macOS installer GUI and setup logic (`installer_macos/`).
*   A launcher script for the installed Windows version (`launcher.py`).
*   A launcher/setup script for the macOS `.app` bundle (`main_macos.py`).
*   Build configurations using PyInstaller (`.spec` files for the application, Windows installer, and Windows uninstaller).
*   Scripts and configurations for creating a macOS `.dmg` package.

---

## Getting Started


1.  **Clone:** `git clone https://github.com/rcverse/anpe-studio.git && cd anpe-studio`
2.  **Create & Activate Virtual Environment:**
    *   `venv`: `python -m venv .venv && .\.venv\Scripts\activate` (Win) or `source .venv/bin/activate` (Mac/Linux)
    *   `conda`: `conda create -n anpe-studio python=3.x && conda activate anpe-studio`
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    # Optional: for building
    pip install pyinstaller
    ```
4.  **Run:**
    ```bash
    python -m anpe_studio
    # or
    python anpe_studio/run.py
    ```

---

## Project Structure

```
.anpe-studio/
├── anpe_studio/        # Main GUI application source code
│   ├── resources/      # Static assets (icons, etc.)
│   ├── widgets/        # Reusable custom UI widgets
│   ├── workers/        # Background QThread workers
│   ├── __init__.py
│   ├── __main__.py     # Allows running with 'python -m anpe_studio'
│   ├── app.py          # QApplication setup, splash screen, main window launch
│   ├── main_window.py  # Core application logic and UI structure
│   ├── resource_manager.py # Asset handling
│   ├── run.py          # Simple script to run app.main()
│   ├── splash_screen.py # Initial loading/checking screen
│   ├── theme.py        # Styling and themes
│   └── version.py      # Application version
├── installer/          # Windows installer GUI source code and related scripts
│   ├── assets/         # Assets specific to the Windows installer
│   ├── views/          # UI views for the Windows installer
│   ├── widgets/        # Custom widgets for the Windows installer
│   ├── workers/        # Background workers for Windows install tasks
│   ├── __init__.py
│   ├── setup_windows.pyw # Main entry point for the Windows installer GUI
│   ├── installer_core.py # Core logic for Windows installation (env setup, pkg install)
│   ├── uninstall.pyw   # Script for Windows uninstaller GUI and logic
│   └── utils.py        # Utility functions for the Windows installer
├── installer_macos/    # macOS installer GUI source code and setup logic
│   ├── views/          # UI views for the macOS installer
│   ├── widgets/        # Custom widgets for the macOS installer
│   ├── workers/        # Background workers for macOS setup tasks
│   ├── __init__.py
│   ├── setup_macos.py  # Main entry point for the macOS setup wizard GUI
│   ├── installer_core_macos.py # Core logic for macOS installation (env setup, pkg install)
│   └── utils.py        # Utility functions for the macOS installer
├── docs/               # Documentation files (including this one)
├── scripts/            # Utility/helper scripts (e.g., convert_icon.py)
├── tests/              # Unit/integration tests (placeholder)
├── .git/               # Git repository data
├── .venv/              # Virtual environment (if created here)
├── build/              # PyInstaller build cache
├── dist/               # PyInstaller output directory (executables, installers)
├── .gitignore          # Files/directories ignored by Git
├── ANPE_Studio_app.spec       # PyInstaller spec file for the main application (used by installers)
├── ANPE_Installer.spec # PyInstaller spec file for the Windows installer executable
├── ANPE_Uninstaller.spec # PyInstaller spec file for the Windows uninstaller executable
├── launcher.py         # Wrapper script launched by the final Windows executable after installation. Sets up env and runs the app.
├── LICENSE             # Project license file
├── main_macos.py       # Entry point for the macOS .app bundle. Manages first-run setup (calling installer_macos.setup_macos) and subsequent app launches.
├── README.md           # User-facing README
├── requirements.txt    # Python package dependencies for the ANPE Studio application itself
└── setup.py            # Python package metadata (used for `pip install .` within the deployed env)
```

---

## Key Modules

*   **`anpe_studio/app.py`:** Initializes the `QApplication`, sets the theme, manages the splash screen, and launches the `MainWindow`.
*   **`anpe_studio/main_window.py`:** The heart of the application. Defines the main UI structure (tabs, widgets), handles user interactions, manages configuration, orchestrates background processing via workers, and displays results.
*   **`anpe_studio/workers/`:** Contains `QObject` subclasses designed to run in separate `QThreads` for long-running tasks.
*   **`anpe_studio/widgets/`:** Houses custom, reusable UI components.
*   **`anpe_studio/theme.py`:** Centralizes application styling.
*   **`anpe_studio/splash_screen.py`:** Provides initial feedback to the user during startup.
*   **`installer/setup_windows.pyw`:** The main entry point for the Windows installation wizard (a PyQt GUI). It guides users, handles environment deployment (using a bundled Python embeddable zip) and package installation via `installer/installer_core.py`.
*   **`installer/installer_core.py`**: Contains the logic for setting up the Python environment, installing packages from `requirements.txt` using `pip`, and placing application files for Windows.
*   **`installer/uninstall.pyw`**: Provides the GUI and logic for uninstalling the application on Windows, removing the created environment and files.
*   **`installer_macos/setup_macos.py`:** The main entry point for the macOS setup wizard (a PyQt GUI, typically run on first launch of the `.app`). It handles environment deployment (e.g., using pre-built Python from python-build-standalone) and package installation via `installer_macos/installer_core_macos.py`.
*   **`installer_macos/installer_core_macos.py`**: Contains the logic for setting up the Python environment and installing packages on macOS.
*   **`launcher.py` (Windows):** A simple Python script, compiled by PyInstaller into the final `.exe` that users click *after* installation. Its main job is to locate the embedded Python interpreter within the installation directory, activate its environment, and execute the main application script (`anpe_studio/run.py`) with the correct environment and working directory.
*   **`main_macos.py` (macOS):** This script is the `CFBundleExecutable` for the macOS `.app` bundle. On first launch, it triggers the setup wizard (`installer_macos/setup_macos.py`). On subsequent launches, it locates the installed standalone Python environment and runs the `anpe_studio/run.py` script.
*   **`.spec` Files:** Define how PyInstaller should bundle various executables:
    *   `ANPE_Studio_app.spec`: Bundles the core `anpe_studio` application files. This is *not* for direct distribution but its output is used by the installers.
    *   `ANPE_Installer.spec`: Bundles the `installer/setup_windows.pyw` GUI, the embedded Python, the core app files (output from step 1), the `requirements.txt` file, the pre-built `launcher.py` executable (see `launcher.py`'s own build process if it has a separate spec, or it's included directly), and the pre-built uninstaller executable (output from step 3).
    *   `ANPE_Uninstaller.spec`: Bundles the `installer/uninstall.pyw` GUI and logic into a Windows uninstaller executable.
*   **`setup.py`**: Standard Python package setup file. Used by the installers to install the `anpe_studio` package (and its dependencies from `requirements.txt`) into the deployed Python environment using `pip install .`.

---

## Dependencies

Runtime dependencies for the ANPE Studio application are in `requirements.txt`. The installers have their own dependencies (e.g., PyQt6 for the installer GUI) which are handled during their respective build processes.

For building the installers and launchers: `pip install pyinstaller`
For creating the macOS DMG: `create-dmg` (shell utility)

---

## Building the Application

This section details the process of building the ANPE Studio application for distribution. Due to the large size and complexity of its dependencies (like spaCy, Benepar, and their associated language models which can rely on PyTorch), creating a traditional, fully self-contained application bundle with tools like PyInstaller or py2app would result in an excessively large file (potentially several gigabytes). This would be impractical for distribution and user download.

To address this, ANPE Studio employs a **custom installer-based approach**. Instead of bundling everything into one massive executable, the project builds installers for Windows and a guided setup process within the macOS `.app` bundle. These installers/setup wizards are responsible for:
1.  Deploying a dedicated, standalone Python environment on the user's system.
2.  Installing the ANPE Studio application and its specific Python dependencies (from `requirements.txt`) into this isolated environment.
3.  Creating convenient launchers for the user.

This ensures that ANPE Studio runs in a controlled environment without interfering with any existing Python installations on the user's machine and makes the initial download much smaller.

### Windows

The Windows distribution involves building three main PyInstaller-generated executables: a core application bundle (for internal use by the installer), the installer itself, and an uninstaller.

**1. Core Application Bundle (`ANPE_Studio_app.spec`):**
   *   This spec is NOT for creating a directly distributable executable.
   *   **Purpose:** To gather all the `anpe_studio` Python source code, resources (icons, etc.), and assets into a structured directory.
   *   **Output:** A folder (e.g., `dist/anpe_studio_core_files`) containing the application's raw materials.
   *   This output is then bundled *inside* the main installer.

**2. Uninstaller (`ANPE_Uninstaller.spec`):**
   *   **Purpose:** To create `uninstall.exe`.
   *   This executable contains the logic to remove the ANPE Studio installation, including the deployed Python environment, application files, and shortcuts.
   *   **Output:** `dist/uninstall.exe`. This is also bundled into the main installer and placed in the application directory upon installation.

**3. Installer (`ANPE_Installer.spec`):**
   *   **Purpose:** To create the main setup executable (e.g., `dist/ANPE_Studio_Setup.exe`). This is what the user downloads and runs.
   *   **Bundled Components within `ANPE_Studio_Setup.exe`:**
      *   The Windows installer GUI application (`installer/setup_windows.pyw` and its related modules).
      *   A pre-compiled `launcher.exe` (built from `launcher.py` via PyInstaller, possibly using its own simple spec or defined within this spec).
      *   The `uninstall.exe` (from step 2).
      *   An embeddable Python distribution (e.g., `python-3.12.x-embed-amd64.zip`, specified in `ANPE_Installer.spec`).
      *   The output of the Core Application Bundle (from step 1).
      *   The `requirements.txt` file for ANPE Studio.
      *   Other assets needed by the installer GUI (icons, license text).

**User-Side Installation Logic (when `ANPE_Studio_Setup.exe` is run):**
   1.  **Installer GUI Launch:** The `installer.setup_windows.pyw` GUI starts.
   2.  **User Interaction:**
      *   Displays a welcome screen, license agreement.
      *   Prompts the user to select an installation directory (e.g., `C:\Program Files\ANPE Studio`).
   3.  **Installation Process (managed by `installer.installer_core.py`):
      *   **Directory Creation:** Creates the chosen installation directory.
      *   **Python Deployment:** Extracts the embedded Python .zip file into a subdirectory (e.g., `InstallationPath\PythonRuntime`). This forms the isolated Python environment.
      *   **Application Code Deployment:** Extracts the Core Application Bundle contents into a source subdirectory (e.g., `InstallationPath\app_src`).
      *   **Dependency Installation:** Executes a command similar to: `InstallationPath\PythonRuntime\python.exe -m pip install -r InstallationPath\app_src\requirements.txt --no-cache-dir`. This installs ANPE, PyQt6, spaCy, etc., into the deployed Python environment.
      *   **ANPE Studio Installation:** Installs the ANPE Studio application itself as a package into the deployed Python environment using a command like: `InstallationPath\PythonRuntime\python.exe -m pip install InstallationPath\app_src`.
      *   **Launcher Placement:** Copies the bundled `launcher.exe` to the root of the installation path (`InstallationPath\ANPE_Studio.exe`).
      *   **Uninstaller Placement:** Copies the bundled `uninstall.exe` to the installation path (`InstallationPath\uninstall.exe`).
      *   **Shortcut Creation:** Creates Start Menu and/or Desktop shortcuts pointing to `InstallationPath\ANPE_Studio.exe` using `pyshortcuts`.
   4.  **Completion:** The GUI shows a success message.

**Application Launch Logic (`launcher.py` compiled as `ANPE_Studio.exe`):**
   1.  User clicks the `ANPE_Studio.exe` shortcut.
   2.  The `launcher.py` script (as `ANPE_Studio.exe`) starts.
   3.  **Environment Discovery:** It determines its own location, which is the root of the installation directory.
   4.  **Python Interpreter Path:** It constructs the path to the deployed Python interpreter (e.g., `InstallationPath\PythonRuntime\python.exe`).
   5.  **Working Directory:** Sets the working directory to the application source or installation root as appropriate.
   6.  **Execution:** It launches the main ANPE Studio application script (`app_src\anpe_studio\run.py`) using the deployed Python interpreter. This effectively runs `InstallationPath\PythonRuntime\python.exe app_src\anpe_studio\run.py` with the correct environment so that all installed packages are found.

**Build Steps Summary (from project root, with virtual environment activated):**

```bash
# 1. Build the core application bundle (output used by ANPE_Installer.spec)
#    (This might be implicitly handled if ANPE_Installer.spec directly bundles the anpe_studio directory)
# pyinstaller ANPE_Studio_app.spec 

# 2. Build the uninstaller (output used by ANPE_Installer.spec)
pyinstaller ANPE_Uninstaller.spec

# 3. Build the launcher (if it has a separate spec, output e.g., dist/anpe.exe, used by ANPE_Installer.spec)
# pyinstaller launcher.spec # Assuming launcher.py is built to anpe.exe

# 4. Build the final Windows installer package
pyinstaller ANPE_Installer.spec
```
*   Ensure paths within the `.spec` files correctly reference each other's outputs or source directories.
*   The final `ANPE_Studio_Setup.exe` will be in the `dist/` directory.

### macOS

The macOS distribution uses a `.app` bundle, which acts as both a first-time setup wizard and a subsequent application launcher. The `.dmg` file is created for easy distribution.

**1. Core Components within the `.app` bundle:**
   *   **`main_macos.py`:** This is the main executable (`CFBundleExecutable`) of the `ANPE Studio.app`. It orchestrates the initial setup and subsequent launches.
   *   **`installer_macos/` directory:** Contains the Python code for the macOS setup wizard GUI (`setup_macos.py`) and the installation logic (`installer_core_macos.py`).
   *   **`anpe_studio/` directory:** The full source code of the ANPE Studio application.
   *   **`requirements.txt`:** Lists the Python dependencies for ANPE Studio.
   *   **Standalone Python Archive (Optional but Recommended):** A pre-built, relocatable Python environment (e.g., from `python-build-standalone`) can be bundled within the `.app/Contents/Resources/`. If not bundled, the setup wizard might attempt to download it, which is less ideal.
   *   Other assets (icons, etc.).

**2. Building the `.app` Bundle:**
   *   Tools like `py2app` or PyInstaller (with a macOS-specific `.spec` file) are used.
   *   The build process packages `main_macos.py` as the entry point, and includes the `installer_macos/`, `anpe_studio/` directories, `requirements.txt`, and the standalone Python archive (if bundled) into the `.app` structure (typically under `Contents/Resources/`).

**3. Creating the `.dmg` Disk Image:**
   *   The `create-dmg` command-line tool is used to package the generated `ANPE Studio.app` into a distributable `.dmg` file. This provides a familiar drag-and-drop installation experience for macOS users (though in this case, dragging to Applications mainly just places the `.app` launcher).

**User-Side Logic & Application Lifecycle:**

**A. First-Time Launch of `ANPE Studio.app` (Setup Process):**
   1.  User opens `ANPE Studio.app`.
   2.  `main_macos.py` executes.
   3.  **Setup Check:** `main_macos.py` checks for a setup completion flag (e.g., at `~/Library/Application Support/ANPE Studio/.setup_complete`). If the flag is missing or `ANPE_FORCE_SETUP=1` is set:
      *   `main_macos.py` calls the `main()` function of `installer_macos.setup_macos.py`.
   4.  **Setup Wizard GUI (`installer_macos.setup_macos.py`):
      *   Displays a welcome screen.
      *   Determines the installation location (defaults to `~/Library/Application Support/ANPE Studio/`). Creates it if it doesn't exist.
   5.  **Installation Process (`installer_macos.installer_core_macos.py`):
      *   **Python Deployment:** Extracts/copies the bundled standalone Python archive to the determined installation location (e.g., `~/Library/Application Support/ANPE Studio/python-standalone/`).
      *   **Dependency Installation:** Uses the deployed standalone Python's `pip` to install dependencies listed in the bundled `requirements.txt` into this new Python environment.
      *   **ANPE Studio Installation:** Installs the `anpe_studio` package (source is available from the `.app` bundle) into the new Python environment.
      *   **Flag Creation:** Creates the `.setup_complete` flag in the installation directory to signify successful setup.
   6.  The setup wizard GUI shows completion. `main_macos.py` might then proceed to launch the application or instruct the user to relaunch.

**B. Subsequent Launches of `ANPE Studio.app`:**
   1.  User opens `ANPE Studio.app`.
   2.  `main_macos.py` executes.
   3.  **Setup Check:** Finds the `.setup_complete` flag, so it skips the setup wizard.
   4.  **Environment Discovery:** Locates the standalone Python interpreter within the installation directory (e.g., `~/Library/Application Support/ANPE Studio/python-standalone/bin/python3`).
   5.  **Execution:** `main_macos.py` uses `os.execve` (or a similar mechanism) to replace its own process with the standalone Python interpreter, instructing it to run the main ANPE Studio script (e.g., effectively `.../python-standalone/bin/python3 -m anpe_studio.run` or by directly invoking the `run.py` script that is now part of the installed package in the standalone environment's `site-packages`).

**Conceptual macOS Build Steps:**

```bash
# 1. Ensure a standalone Python archive for macOS is available (e.g., downloaded from python-build-standalone).
# This archive should be placed where the .app bundling process can pick it up.

# 2. Bundle main_macos.py, installer_macos/, anpe_studio/ source, requirements.txt, and the Python archive into an .app.
# This typically involves a setup.py for py2app or a PyInstaller .spec file configured for macOS.
# Example using py2app (requires a setup_macos_py2app.py file):
# python setup_macos_py2app.py py2app
# Or using PyInstaller (requires a macos_app.spec file):
# pyinstaller macos_app.spec

# 3. Create the .dmg from the generated .app bundle (e.g., output in dist/ANPE Studio.app).
# create-dmg --volname "ANPE Studio" \
#   --window-pos 200 120 \
#   --window-size 800 400 \
#   --icon-size 100 \
#   --icon "ANPE Studio.app" 200 190 \
#   --hide-extension "ANPE Studio.app" \
#   --app-drop-link 600 185 \
#   "dist/ANPE_Studio_Installer.dmg" \
#   "dist/ANPE Studio.app"
```
*   The specifics of the `.app` bundling (step 2) heavily depend on the chosen tool (`py2app` or PyInstaller) and its configuration file.
*   The `create-dmg` command creates a professional-looking disk image for distribution.

---

## Code Style and Conventions

*   **PEP 8:** Please adhere to the [PEP 8 Style Guide](https://www.python.org/dev/peps/pep-0008/). Tools like `flake8` or `black` can help.
*   **Type Hinting:** Use type hints (`typing` module) for function signatures and variables where practical to improve code clarity and enable static analysis.
*   **Docstrings:** Write clear docstrings for modules, classes, and functions explaining their purpose, arguments, and return values.
*   **Meaningful Names:** Use descriptive names for variables, functions, and classes.
*   **Imports:** Organize imports according to PEP 8 (standard library, third-party, local application).
*   **Logging:** Use the `logging` module for application events, warnings, and errors. Avoid excessive use of `print()` for debugging information in committed code.

---

## Testing

*(Placeholder)* No formal test suite exists currently. Contributions adding tests (e.g., `pytest`, `pytest-qt`) are welcome.

---

## Contributing

Contributions are welcome!

1.  **Bugs & Enhancements:** Check existing [Issues](https://github.com/rcverse/anpe-studio/issues) or create a new one with clear details.
2.  **Pull Requests:**
    *   Fork the repo, create a feature branch.
    *   Make your changes, adhering to code style.
    *   Commit with clear messages.
    *   Push to your fork and open a PR against the main repository branch (`main` or `develop`).
    *   Clearly describe your changes in the PR. 