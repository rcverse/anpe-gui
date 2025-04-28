# Windows Packaging Strategy & Implementation Summary (Reconstruction Guide)

## Introduction

This document summarizes the current state (as of the last known 'main' branch status provided) of the Windows packaging strategy for the ANPE GUI application. It is intended as a guide for reconstructing the build process, detailing the components, key implementation points, required build configurations (`.spec` files), and potential areas for optimization. The goal is to enable another assistant or developer to understand the context and successfully build the installer, launcher, and uninstaller executables.

## Overall Strategy Recap

The core strategy avoids bundling the entire application and its large dependencies (Python, libraries, models) directly into the main user-facing executable (`ANPE.exe`). Instead, it uses a multi-component approach:

1.  **Installer (`ANPE_Installer.exe`):** A user-friendly GUI application (built from `installer/setup_windows.pyw`) responsible for:
    *   Guiding the user through installation path selection.
    *   Unpacking a bundled embeddable Python distribution.
    *   Copying the application source code (`anpe_gui/`).
    *   Copying pre-built `ANPE.exe` (Launcher) and `uninstall.exe`.
    *   Installing dependencies (`pip install -r requirements.txt`) into the embedded Python.
    *   Downloading required spaCy models into the embedded Python.
    *   Creating registry entries for "Apps & features" integration.
    *   Creating Desktop/Start Menu shortcuts.
2.  **Launcher (`ANPE.exe`):** A lightweight executable (built from `launcher.py` - *file currently missing, needs reconstruction*) responsible for:
    *   Locating the embedded `pythonw.exe`.
    *   Executing the main application script (`anpe_gui/run.py`) using the embedded Python.
    *   Monitoring the application process for critical startup errors within the first few seconds.
    *   Displaying an error dialog if a startup crash occurs, capturing stderr.
    *   Deleting its own debug log (`launcher_debug.log`) if startup is successful.
3.  **Uninstaller (`uninstall.exe`):** A simple executable (built from `installer/uninstall.pyw` - *file currently modified/potentially needs review*) responsible for:
    *   Confirming uninstallation with the user.
    *   Removing the application's registry key.
    *   Deleting the entire installation directory.
4.  **Application Code (`anpe_gui/`):** The actual PyQt6 application source code.
5.  **Embeddable Python:** A standard Python zip distribution bundled within the installer.

## Component Implementation Details (Current State)

### 1. Installer (`installer/setup_windows.pyw`)

This is the main GUI installer application. Key features implemented in the provided `setup_windows.pyw`:

*   **GUI Framework:** PyQt6.
*   **Window:** Frameless main window (`Qt.WindowType.FramelessWindowHint`, `WA_TranslucentBackground`) with a custom title bar (`widgets.custom_title_bar.CustomTitleBar`) for minimize/close actions and a consistent look.
*   **Structure:** Uses a `QStackedWidget` to manage different views:
    *   `WelcomeViewWidget`: Initial screen, prompts for installation path.
    *   `ProgressViewWidget`: Displays progress logs and status for environment setup and model setup stages separately. Includes a task list updated by worker signals.
    *   `CompletionViewWidget`: Shows success/failure message, provides options to create shortcuts and launch the application.
*   **Asynchronous Operations:** Uses `QThread` and `QObject` workers (`workers.env_setup_worker.EnvironmentSetupWorker`, `workers.model_setup_worker.ModelSetupWorker`) to perform long-running tasks without freezing the GUI. These workers typically delegate the actual file operations and process execution to `installer_core.py` (see below). Communication relies on signals and slots (`log_update`, `status_update`, `task_status_update`, `finished`).
*   **Installation Steps (Workers):**
    *   **Env Setup:** Validates path, creates directories, extracts Python zip, copies `anpe_gui` source (correctly **excluding `__pycache__`** directories), copies bundled `ANPE.exe` and `uninstall.exe`, runs `pip install -r requirements.txt` using the extracted `python.exe`. (Actual logic resides in `installer_core.py`).
    *   **Model Setup:** Runs `python -m spacy download <model_name>` using the extracted `python.exe`. (Actual logic likely in `installer_core.py` or a dedicated model setup script called by the worker).
*   **Windows Integration:**
    *   **Registry:** Uses the `winreg` module to create an entry under `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\ANPE`. This allows the app to appear in "Apps & features" and points to `uninstall.exe`. Using `HKCU` avoids needing admin privileges for basic install/uninstall.
    *   **Shortcuts:** Uses the `pyshortcuts` library (`make_shortcut`) to create Desktop and Start Menu shortcuts pointing directly to the installed `ANPE.exe` (Launcher). The working directory is set to the installation root.
*   **Resource Handling:** Relies on a utility function (`installer.utils.get_resource_path`) to correctly locate resources (Python zip, binaries, assets) bundled by PyInstaller, whether running from source or as a frozen executable.
*   **Error Handling:** Includes path validation, catches exceptions during file operations, registry writing, and shortcut creation. Provides feedback via `QMessageBox`.
*   **Cancellation:** The `closeEvent` handler prompts the user if setup is running and attempts to terminate worker threads and associated processes gracefully.
*   **Test Mode:** Accepts a `test_install_path` argument to bypass the welcome screen and run the installation process directly for testing.
*   **Styling:** Applies basic styling for background, borders, and rounded corners.

### 2. Core Logic (`installer/installer_core.py`)

This script contains the backend logic executed by the installer's worker threads. It's designed to be callable potentially by different installer frontends (like `setup_windows.pyw` or `setup_macos.pyw`). Its primary responsibilities include:

*   **Platform-Specific Operations:** Handles differences in file paths, Python distribution types (.zip vs .tar.gz, though macOS part is TODO), and process execution details.
*   **Asset Finding:** Locates bundled assets (like the Python distribution zip) using `utils.get_resource_path`, accommodating both development and frozen (`_MEIPASS`) environments.
*   **Python Unpacking:** Extracts the embeddable Python distribution to the target installation directory.
*   **Python Configuration:** Modifies the `._pth` file within the embeddable Python distribution to uncomment `import site`, enabling the use of installed packages (`site-packages`).
*   **Pip Bootstrapping:** Downloads `get-pip.py` and executes it using the unpacked Python to install `pip`.
*   **Dependency Installation:** Runs `pip install` commands (including upgrading pip itself and installing packages from a list or `requirements.txt`). Captures and logs output/errors.
*   **File Copying:**
    *   Copies the application source code (`anpe_gui/`) from its source location (relative in dev, bundled in frozen state) to the installation directory, **explicitly ignoring `__pycache__` directories** using `shutil.copytree` with an ignore function.
    *   Copies documentation files (e.g., `docs/gui_help.md`) to the installation directory.
*   **Utility Functions:** Provides helper functions for printing standardized step/success/failure messages and finding the Python executable.
*   **Error Handling:** Includes checks for path validity, writability, file existence, and catches errors during unpacking, downloading, command execution, and file operations, reporting failures via `print_failure`.

### 3. Launcher (`launcher.py` - *To Be Reconstructed*)

Based on previous discussions, this script should:

*   Import necessary modules (`subprocess`, `os`, `sys`, `time`, `pathlib`, `ctypes`, `logging`).
*   Determine its own location and the expected installation directory structure.
*   Locate `<install_dir>/python/pythonw.exe`.
*   Locate `<install_dir>/anpe_gui/run.py`.
*   Set up basic logging to `<install_dir>/launcher_debug.log`.
*   Launch `pythonw.exe run.py` using `subprocess.Popen`, setting the `cwd` to `<install_dir>` and capturing `stderr`.
*   Monitor the process for ~5 seconds (`process.poll()`).
*   If the process exits non-zero within the timeout:
    *   Read stderr.
    *   Log the error.
    *   Display a Windows message box (`ctypes.windll.user32.MessageBoxW`) showing the error.
    *   Exit the launcher with a non-zero code.
*   If the process is still running after the timeout:
    *   Log success.
    *   Close the log file (`logging.shutdown()`).
    *   Attempt to delete `launcher_debug.log`.
    *   Exit the launcher with code 0.
*   Handle `FileNotFoundError` if Python or the script isn't found.

### 4. Uninstaller (`installer/uninstall.pyw` - *Review Recommended*)

This script typically needs to:

*   Import necessary modules (`os`, `sys`, `shutil`, `winreg`, potentially `tkinter` or `PyQt6` for a simple confirmation dialog).
*   (Optional) Display a confirmation dialog asking the user if they want to proceed.
*   Determine the installation location (e.g., by reading the registry key it's about to delete, or by assuming its own location is the install dir).
*   Attempt to delete the registry key `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\ANPE`.
*   Attempt to delete the entire installation directory using `shutil.rmtree`. Handle potential errors (e.g., files in use).
*   Provide feedback (e.g., print messages to console, or show a final message box). *Note: The current `.pyw` extension suggests it might be intended as windowed, requiring GUI elements for feedback.*

## PyInstaller `.spec` Files (Required Configuration)

Three separate `.spec` files are needed to build the executables:

1.  **`ANPE_Installer.spec` (for `setup_windows.pyw`)**
    *   **Mode:** `onefile = True`
    *   **Console:** `windowed = True` (or `console = False`) - Essential for a GUI application.
    *   **`datas`:** This is CRITICAL. It must bundle all necessary components for the installation process:
        *   The embeddable Python zip distribution (e.g., `('path/to/python-XYZ-embed-amd64.zip', 'assets')`). The target path should match what `find_asset` in `installer_core.py` expects (likely within an 'assets' folder).
        *   The pre-built `ANPE.exe` (Launcher) (e.g., `('dist/ANPE.exe', 'assets')`).
        *   The pre-built `uninstall.exe` (e.g., `('dist/uninstall.exe', 'assets')`).
        *   The **entire application source directory** (`anpe_gui/`) (e.g., `('src/anpe_gui', 'assets/anpe_gui')`). The target path must align with how `copy_app_code` finds it within the bundled assets.
        *   Installer assets like icons (e.g., `('installer/assets/installer_icon.ico', 'assets')`).
        *   The `requirements.txt` file if used directly by `installer_core.py` (e.g., `('requirements.txt', 'assets')`). (Alternatively, dependencies are hardcoded in `installer_core.py`).
        *   The `docs` directory containing `gui_help.md` (e.g., `('docs', 'assets/docs')`).
    *   **`hiddenimports`:** May be needed for libraries used indirectly by the installer or its core logic (e.g., `winreg`, `pyshortcuts`, certain PyQt6 plugins, worker dependencies).
    *   **`icon`:** Specify the installer's `.ico` file.
    *   **`name`:** `ANPE_Installer`

2.  **`ANPE.spec` (for `launcher.py`)**
    *   **Mode:** `onefile = True`
    *   **Console:** `windowed = True` (or `console = False`) - To avoid a console flash during normal launch.
    *   **`datas`:** Generally *none*, as it only launches the installed components.
    *   **`hiddenimports`:** Less likely needed, but possible depending on imports (`ctypes` usually fine).
    *   **`icon`:** Specify the main application's `.ico` file (`app_icon_logo.ico`).
    *   **`name`:** `ANPE`

3.  **`uninstall.spec` (for `installer/uninstall.pyw`)**
    *   **Mode:** `onefile = True`
    *   **Console:** `windowed = False` (or `console = True`) is often preferred for uninstallers so users can see progress/error messages if run manually, unless it has its own GUI confirmation/feedback. If it uses PyQt6 for dialogs, use `windowed = True`.
    *   **`datas`:** Typically *none*.
    *   **`hiddenimports`:** Potentially needed if using GUI elements (e.g., PyQt6).
    *   **`icon`:** Can use a specific uninstall icon or the main app icon.
    *   **`name`:** `uninstall`

## Potential Optimizations & Refinements (Suggestions)

1.  **Configuration:** Centralize configuration values used in `setup_windows.pyw` (like `display_name`, `display_version`, `publisher`, maybe `PYTHON_DIR_NAME`) into `installer_core.py` or a dedicated config file/module to avoid hardcoding them in multiple places.
2.  **Uninstaller GUI:** If `uninstall.pyw` is meant to be windowed, ensure it has robust GUI elements (using PyQt6/Tkinter) for confirmation and feedback, rather than just being a `.pyw` file with `print` statements. If no GUI is needed, rename to `.py` and build with `console=True`.
3.  **Error Reporting:** Enhance error reporting during `pip install` or `spacy download`. The current `subprocess.run` calls in `installer_core.py` capture stdout/stderr, but the GUI worker (`env_setup_worker.py`) needs to relay this detailed info back to the GUI's log view on failure.
4.  **Resource Bundling:** Double-check that `utils.get_resource_path` and the paths used in `installer_core.py` correctly handle all bundled assets and directories, especially when running as a `--onefile` executable. The `datas` in `ANPE_Installer.spec` must place files exactly where `installer_core.py` expects to find them (e.g., inside an 'assets' subdirectory within the bundle).
5.  **Dependencies:** Ensure `requirements.txt` (if used) or the package list in `installer_core.py` is accurate and includes all necessary packages for `anpe_gui`. Verify if `pyshortcuts` and potentially `PyQt6` need to be installed by `installer_core.py` *or* if they are only needed by the installer/uninstaller executables themselves (and thus included via their respective `.spec` files).

## Instructions for Target AI/Developer

1.  **Gather/Reconstruct Files:**
    *   Ensure you have the complete `installer` directory structure (including `setup_windows.pyw`, `installer_core.py`, `utils.py`, `widgets/`, `workers/`, `views/`, `assets/`).
    *   Reconstruct `launcher.py` based on the description in section "Component Implementation Details".
    *   Review/Finalize `installer/uninstall.pyw` based on its requirements (GUI vs. Console, error handling).
    *   Ensure the `anpe_gui/` application source code is available.
    *   Obtain the correct embeddable Python zip distribution.
    *   Obtain the application `requirements.txt` (if used by `installer_core.py`).
    *   Obtain required icons (`.ico` files).
    *   Obtain the `docs/gui_help.md` file.
2.  **Create `.spec` Files:** Create the three `.spec` files (`ANPE_Installer.spec`, `ANPE.spec`, `uninstall.spec`) based on the configurations described above. Pay close attention to the **`datas` section in `ANPE_Installer.spec`**, ensuring all paths (source and destination within the bundle) are correct.
3.  **Build Binaries:**
    *   Build `ANPE.exe` using PyInstaller and `ANPE.spec`.
    *   Build `uninstall.exe` using PyInstaller and `uninstall.spec`.
    *   **Crucially:** Place the built `ANPE.exe` and `uninstall.exe` where the `ANPE_Installer.spec` file expects to find them (e.g., in a `./dist` folder relative to the spec file).
4.  **Build Installer:** Build `ANPE_Installer.exe` using PyInstaller and `ANPE_Installer.spec`. This will bundle the previously built binaries, Python zip, source code, etc.
5.  **Test:** Thoroughly test the generated `ANPE_Installer.exe`. Verify installation, registry entries, shortcuts, application launch (including the error monitoring by `ANPE.exe`), and uninstallation. Test the cancellation process.

This summary should provide the necessary context and steps to reconstruct and build the Windows installer package. 