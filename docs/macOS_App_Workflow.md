# macOS Application Workflow & Packaging for ANPE GUI

This document outlines the structure, runtime logic, packaging process, and debugging workflow for the ANPE GUI macOS application bundle (`.app`). It serves as the primary reference for the macOS version.

## I. Projected `.app` Bundle Structure

The final `ANPE GUI.app` bundle, built using `py2app` via `setup.py`, will have the following key internal structure:

```
ANPE GUI.app/
└── Contents/
    ├── Info.plist          # Application metadata (from setup.py)
    ├── PkgInfo             # Basic package info
    ├── MacOS/
    │   └── anpe-gui        # Main executable + Py2App Python Launcher (Python_Py2App)
    └── Resources/
        ├── anpe_gui/       # Minimal GUI shell code (e.g., app.py, views - *excluding heavy deps*)
        │   └── run.py      # Entry point executed by Python_App
        │   └── ...
        ├── installer/
        │   ├── __init__.py
        │   ├── setup_macos.py     # Setup UI Controller
        │   ├── installer_core_macos.py # Core setup logic (env extraction, pip install)
        │   ├── views/             # Setup UI Views (Qt)
        │   ├── workers/           # Setup background workers (Qt)
        │   │   ├── env_setup_worker_macos.py
        │   │   └── model_setup_worker_macos.py # Delegates to anpe.utils.setup_models
        │   ├── assets/
        │   │   ├── Python-3.12-macOS-support.b7.tar.gz # Archive for Python_App
        │   │   └── app_icon_logo.icns # App Icon
        │   │   └── ...              # Other UI assets
        │   └── macos_requirements.txt # Dependencies installed by setup
        ├── main_macos.py     # Initial launcher script run by Python_Py2App
        ├── PyQt6/            # Bundled PyQt6 framework (for installer UI)
        ├── ...               # Other files included by py2app (minimal stdlib etc.)
        └── lib/              # Bundled Python standard library parts for Python_Py2App
            └── pythonX.Y/
                └── ...
```

**Key Points:**

*   **`Python_Py2App`:** Resides in `Contents/MacOS/`. This is a minimal Python environment bundled by `py2app`. It contains only the code specified in `setup.py`'s `packages` (`PyQt6`, `installer`, `anpe_gui` shell) and the entry script `main_macos.py`. It **does not** contain `spacy`, `benepar`, `anpe`, `torch`, etc.
*   **`Python_App` Archive:** The `Python-*.tar.gz` file containing the full Python distribution intended for running the main application is stored as a resource in `Contents/Resources/installer/assets/`.
*   **`macos_requirements.txt`:** Located in `Contents/Resources/installer/`, this file lists the dependencies (`PyQt6`, `anpe`, `spacy`, `benepar`, etc.) to be installed into `Python_App` during setup.

## II. Application Support Directory Structure

During the first-run setup, the application creates and populates a directory in the standard user Application Support location:

```
~/Library/Application Support/
└── ANPE GUI/
    ├── python-macos/      # Base directory for the extracted Python_App
    │   └── Python.framework/
    │       └── Versions/
    │           └── 3.12/      # Specific Python version extracted
    │               ├── bin/
    │               │   └── python3   # The Python_App executable
    │               │   └── pip3      # Pip for Python_App
    │               │   └── ...
    │               ├── include/
    │               ├── lib/
    │               │   └── python3.12/
    │               │       └── site-packages/ # << Dependencies installed here!
    │               │           ├── anpe/
    │               │           ├── anpe_gui/ # Full package installed here via pip
    │               │           ├── spacy/
    │               │           ├── benepar/
    │               │           ├── torch/
    │               │           ├── PyQt6/
    │               │           └── ...   # All other dependencies from macos_requirements.txt
    │               └── ...
    └── .setup_complete        # Marker file indicating setup finished successfully
```

**Key Points:**

*   **`Python_App` Location:** The full Python environment used to run the actual ANPE logic lives *outside* the `.app` bundle, in the user's `~/Library/Application Support/ANPE GUI/`.
*   **Dependency Installation:** All heavy dependencies listed in `macos_requirements.txt` are installed into the `site-packages` of `Python_App` during the first-run setup using `pip`.
*   **Model Download:** Language models (`spacy`, `benepar`) are downloaded into this environment by the `anpe.utils.setup_models` script, triggered by the setup UI.
*   **Setup Flag:** The presence of `.setup_complete` signals that the `Python_App` environment is ready.

## III. Runtime Logic

### A. First Launch

1.  **Initiation:** User double-clicks `ANPE GUI.app`. macOS launches the executable in `Contents/MacOS/anpe-gui`.
2.  **Launcher Execution:** The `py2app` executable wrapper starts `Python_Py2App`, which runs `main_macos.py` (from `Contents/Resources/`).
3.  **Setup Check:** `main_macos.py` calls `check_setup_status()`, which looks for `~/Library/Application Support/ANPE GUI/.setup_complete`. The flag is missing.
4.  **Setup Initiation:** `main_macos.py` calls `run_first_run_setup()`.
5.  **Setup UI:** `run_first_run_setup` executes `installer/setup_macos.py --target-install-dir=~/Library/Application Support/ANPE GUI` (using `Python_Py2App`). The setup window appears (using the `PyQt6` bundled in `Resources`).
6.  **User Action:** User interacts with the UI (e.g., clicks "Prepare").
7.  **Environment Setup Worker:** `setup_macos.py` starts `EnvSetupWorkerMacOS`.
    *   **Extraction:** The worker calls `installer_core_macos.py` functions (still running on `Python_Py2App`) to locate `Python-*.tar.gz` in `Contents/Resources/installer/assets/` and extract `Python_App` to `~/Library/Application Support/ANPE GUI/python-macos/`.
    *   **Dependency Installation:** The worker uses `installer_core_macos.py` functions, which invoke `subprocess` to run the `pip` executable *from the newly extracted* `Python_App` (`.../bin/pip3`) to install packages listed in `installer/macos_requirements.txt` into the `site-packages` directory of `Python_App`.
8.  **Model Setup Worker:** Upon successful environment setup, `setup_macos.py` starts `ModelSetupWorkerMacOS`.
    *   **Model Download:** This worker uses `QProcess` to run the target `Python_App` executable (`.../bin/python3`) with the arguments `-m anpe.utils.setup_models`. The `anpe` script handles the actual download and setup of `spacy` and `benepar` models within the `Python_App` environment. The worker monitors the output via `QProcess` signals.
9.  **Flag Creation:** Upon successful environment and model setup, `main_macos.py` (after `run_first_run_setup` returns successfully) creates the marker file `~/Library/Application Support/ANPE GUI/.setup_complete`.
10. **Setup Completion:** The setup UI closes, `run_first_run_setup()` returns `True`.
11. **App Launch:** `main_macos.py` proceeds to call `launch_main_app()`.
12. **Target Python Discovery:** `launch_main_app()` calls `_get_target_python_executable()`, which finds the path to `Python_App` in `~/Library/Application Support/ANPE GUI/python-macos/.../bin/python3`.
13. **Process Replacement:** `launch_main_app()` uses `os.execv` with the path to `Python_App` and arguments `['-m', 'anpe_gui.run']`. The `main_macos.py` process (running on `Python_Py2App`) is **replaced** by a new process running `anpe_gui.run` using `Python_App`.
14. **Main App Runs:** The main ANPE GUI application starts, now running with `Python_App` which has all the necessary heavy dependencies and models installed.

### B. Subsequent Launches

1.  **Initiation:** User double-clicks `ANPE GUI.app`.
2.  **Launcher Execution:** `Python_Py2App` runs `main_macos.py`.
3.  **Setup Check:** `main_macos.py` calls `check_setup_status()`. The `.setup_complete` flag **is found** in Application Support. The function returns `True`.
4.  **Setup Skipped:** The `if not setup_done:` block in `main_macos.py` is skipped.
5.  **App Launch:** `main_macos.py` proceeds directly to call `launch_main_app()`.
6.  **Target Python Discovery:** `launch_main_app()` finds the path to `Python_App` in Application Support.
7.  **Process Replacement:** `launch_main_app()` uses `os.execv` to replace the launcher process with the main application process, running `anpe_gui.run` using `Python_App`.
8.  **Main App Runs:** The main ANPE GUI application starts using `Python_App`.

## IV. Role of Key Components

*   **`setup.py`:** Configures `py2app`. Defines the app entry point (`main_macos.py`), packages included in `Python_Py2App` (`PyQt6`, `installer`, `anpe_gui` shell), packages explicitly excluded (`spacy`, `benepar`, `anpe`, `torch`, etc.), and resources to bundle (`installer/assets/*`, `installer/macos_requirements.txt`).
*   **`main_macos.py`:** The initial script run by `Python_Py2App`. Acts as the central dispatcher: checks if setup is done, runs the setup UI if needed (passing the target Application Support path), creates the `.setup_complete` flag *after* successful setup, and finally uses `os.execv` to hand off control to `Python_App` to run the main application logic (`anpe_gui.run`).
*   **`installer/setup_macos.py`:** Python script (run by `Python_Py2App`) that controls the setup UI using `PyQt6`. Receives the target install path via `--target-install-dir`. Manages the setup workers (`EnvSetupWorkerMacOS`, `ModelSetupWorkerMacOS`).
*   **`installer/installer_core_macos.py`:** Contains platform-specific core logic for *environment* setup (run by `Python_Py2App`). Finds and extracts the `Python_App` archive, uses `subprocess` to invoke the extracted `Python_App`'s `pip` to install dependencies from `macos_requirements.txt`. **Does not** create the `.setup_complete` flag anymore.
*   **`installer/workers/env_setup_worker_macos.py`:** Background worker (run by `Python_Py2App`) that orchestrates environment extraction and dependency installation by calling functions in `installer_core_macos.py`.
*   **`installer/workers/model_setup_worker_macos.py`:** Background worker (run by `Python_Py2App`) that uses `QProcess` to execute `anpe.utils.setup_models` using the target `Python_App` executable. Parses output for status updates.
*   **`installer/macos_requirements.txt`:** Lists Python package dependencies (`PyQt6`, `anpe`, `spacy`, `benepar`, etc.) to be installed into `Python_App` by `pip`. Bundled inside the `.app`.
*   **`installer/assets/Python-*.tar.gz`:** The compressed archive containing the full Python distribution (`Python_App`) intended for the final application execution environment. Bundled inside the `.app`.
*   **`anpe_gui/run.py`:** The designated entry point module for the main application logic. This script is executed by `Python_App` (found in Application Support) via `python -m anpe_gui.run` invoked by `main_macos.py`'s `os.execv` call.
*   **`anpe/utils/setup_models.py`:** Script within the `anpe` package (installed into `Python_App`) responsible for downloading and validating the necessary `spacy` and `benepar` models.
*   **`debug_macos_setup.sh`:** *Development/Debug Only.* A shell script wrapper that uses **System Python** to initiate the setup process defined in `installer/setup_macos.py --debug --target-install-dir=./debug_install`. Its main purpose is to create the `Python_Debug` environment (equivalent to `Python_App`) in a local directory (e.g., `./debug_install/`) by running the *real* extraction, dependency installation, and model setup logic. Creates `.setup_complete` in the *debug* install directory upon completion.
*   **`debug_macos_app_launch.sh`:** *Development/Debug Only.* A shell script that simulates the behavior of launching the `.app`. It finds `Python_Debug` (created by `debug_macos_setup.sh`) and uses *it* to run `main_macos.py`, setting `ANPE_SIMULATE_APP_BUNDLE=1` and `ANPE_INSTALL_PATH=./debug_install` to trigger the correct logic paths within `main_macos.py`. This allows testing the setup check and `os.execv` hand-off without building the full `.app`.

## V. Packaging & Distribution

### Prerequisites

*   macOS 11 (Big Sur) or newer recommended for building (due to Python/PyQt6 compatibility).
*   Python 3.9+ installed on the build machine (System Python or via Homebrew/pyenv).
*   pip package manager.

### Required Python Packages for Building

Install the following packages into the Python environment you'll use for building:

```bash
pip install py2app setuptools wheel PyQt6
```

### Build Process

1.  **Prepare:** Ensure all source code is up-to-date. Verify required assets (`Python-*.tar.gz`, icons) are in `installer/assets/`. Ensure `installer/macos_requirements.txt` lists the correct dependencies and versions.
2.  **Configure:** Review `setup.py`. Ensure `APP_NAME`, `APP_VERSION`, packages, excludes, and resources are correct.
3.  **Build:** Run `py2app` from the project root directory:
    ```bash
    python setup.py py2app
    ```
    This creates the `ANPE GUI.app` bundle in the `dist/` directory.
4.  **Test:** Navigate to `dist/` and double-click `ANPE GUI.app`. Verify the first-run setup (environment creation, dependency install, model download) and subsequent launches.

### Creating a DMG Installer (Recommended)

For easier distribution, create a DMG disk image:

1.  **Install `create-dmg`:**
    ```bash
    brew install create-dmg
    ```
2.  **Create DMG:** Run this command from the project root *after* building the `.app`:
    ```bash
    create-dmg \\
      --volname "ANPE GUI Installer" \\
      --volicon "installer/assets/app_icon_logo.icns" \\
      --window-pos 200 120 \\
      --window-size 800 400 \\
      --icon-size 100 \\
      --icon "ANPE GUI.app" 200 190 \\
      --hide-extension "ANPE GUI.app" \\
      --app-drop-link 600 185 \\
      "ANPE GUI Installer.dmg" \\
      "dist/" # Point to the directory containing the .app
    ```
    *(Adjust paths and layout parameters as needed)*

### Notarization (Optional but Highly Recommended)

For distribution outside the Mac App Store, notarizing your application is essential for user trust and bypassing Gatekeeper warnings:

1.  **Requirements:** An Apple Developer account, Xcode command-line tools (`xcode-select --install`).
2.  **Create App-Specific Password:** Generate one at [appleid.apple.com](https://appleid.apple.com) under Security -> App-Specific Passwords.
3.  **Code Sign (if not done by py2app/setup):** Ensure your `.app` is code-signed with your Developer ID certificate. `py2app` might handle this if configured, otherwise use `codesign`.
4.  **Notarize DMG:**
    ```bash
    xcrun altool --notarize-app \\
      --primary-bundle-id "com.yourdomain.anpe-gui" \\ # Replace with your actual bundle ID
      --username "your.apple.id@example.com" \\
      --password "xxxx-xxxx-xxxx-xxxx" \\ # Use the App-Specific Password
      --asc-provider "YourTeamID" \\ # Optional, if in multiple teams
      --file "ANPE GUI Installer.dmg"
    ```
    (This command uploads the DMG. Note the RequestUUID.)
5.  **Check Status:** Periodically check the status using the RequestUUID:
    ```bash
    xcrun altool --notarization-info <RequestUUID> -u "your.apple.id@example.com" -p "xxxx-..."
    ```
6.  **Staple Ticket:** Once notarization succeeds, staple the notarization ticket to the DMG:
    ```bash
    xcrun stapler staple "ANPE GUI Installer.dmg"
    ```
    Distribute the stapled DMG file.

## VI. Debugging Workflow

This workflow uses the dedicated debug scripts to test the setup and launch logic without building the `.app`.

**Goal:** Verify the first-run setup and subsequent launches work correctly, ensuring the right Python environments are used and the hand-off via `os.execv` succeeds.

**Location:** Run these commands from the project root directory.

**Step 1: Prepare Debug Environment (Simulates full first-run setup)**

*   **Command:** `bash ./debug_macos_setup.sh --reset`
    *   Use `--install-path=./my_test_dir` to specify a custom location instead of `./debug_install`.
*   **Action:**
    1.  Uses **System Python** to run `installer/setup_macos.py --debug --target-install-dir=./debug_install`.
    2.  The Python code (`installer_core_macos.py` via `EnvSetupWorkerMacOS`) extracts `Python_Debug` from `installer/assets/*.tar.gz` into `./debug_install/python-macos`.
    3.  The Python code uses `subprocess` to invoke `./debug_install/.../bin/pip3` to install dependencies from `installer/macos_requirements.txt` into `Python_Debug`.
    4.  The Python code (`ModelSetupWorkerMacOS`) invokes `./debug_install/.../bin/python3 -m anpe.utils.setup_models` to download models into `Python_Debug`.
    5.  Upon successful completion of all setup steps, `main_macos.py` (which would normally be called *after* setup in the real flow, but is simulated here by the script completing) creates `./debug_install/.setup_complete`.
*   **Rationale:** Creates the target application environment (`Python_Debug` + dependencies + models) in a predictable local directory, mirroring the state of `~/Library/Application Support/ANPE GUI/` after a real successful first run. Creates the flag file in the *debug install directory*.
*   **Verify:** Check console for errors. Ensure `./debug_install/python-macos` exists and contains a Python framework with installed site-packages. Check `./debug_install/.setup_complete` exists.

**Step 2: Simulate App Launch - First Time (Setup Needed Check)**

*   **Command:** `bash ./debug_macos_app_launch.sh --force-setup`
    *   Use `--install-path=./my_test_dir` if you used it in Step 1.
*   **Action:**
    1.  Removes `./debug_install/.setup_complete`.
    2.  Finds `Python_Debug` inside `./debug_install/`.
    3.  Exports `ANPE_INSTALL_PATH=./debug_install` and `ANPE_SIMULATE_APP_BUNDLE=1`.
    4.  Executes `main_macos.py` using `Python_Debug`.
    5.  `main_macos.py` (running on `Python_Debug`) checks flag -> missing.
    6.  `main_macos.py` runs `installer/setup_macos.py --target-install-dir=./debug_install` (using `Python_Debug`).
    7.  Setup code runs (environment/dependencies/models should already exist, so it should be fast), completes.
    8.  `main_macos.py` creates flag `./debug_install/.setup_complete`.
    9.  `main_macos.py` calls `launch_main_app()`.
    10. `launch_main_app` finds `Python_Debug` (via `ANPE_INSTALL_PATH`).
    11. `launch_main_app` calls `os.execv` to run `anpe_gui.run` using `Python_Debug`.
*   **Rationale:** Tests the logic flow within `main_macos.py` for a first launch *when simulating the app bundle*: setup check failure, setup re-triggering (which should find existing components), flag creation, and the final `os.execv` hand-off to the correct Python environment (`Python_Debug`).
*   **Verify:** Check console logs and `~/Library/Logs/ANPE GUI/anpe_gui_main_launch.log`. Ensure setup UI briefly appears or setup runs non-interactively. Verify the main application UI launches. Check `./debug_install/.setup_complete` is recreated.

**Step 3: Simulate App Launch - Subsequent Times (Setup Complete Check)**

*   **Command:** `bash ./debug_macos_app_launch.sh`
    *   Use `--install-path=./my_test_dir` if you used it previously.
*   **Action:**
    1.  Finds `Python_Debug` inside `./debug_install/`.
    2.  Exports `ANPE_INSTALL_PATH=./debug_install` and `ANPE_SIMULATE_APP_BUNDLE=1`.
    3.  Executes `main_macos.py` using `Python_Debug`.
    4.  `main_macos.py` (running on `Python_Debug`) checks flag -> finds it in `./debug_install/`.
    5.  Setup is skipped.
    6.  `main_macos.py` calls `launch_main_app()`.
    7.  `launch_main_app` finds `Python_Debug`.
    8.  `launch_main_app` calls `os.execv` to run `anpe_gui.run` using `Python_Debug`.
*   **Rationale:** Tests the logic flow within `main_macos.py` for subsequent launches: setup check success, setup skip, and direct `os.execv` hand-off to `Python_Debug`.
*   **Verify:** Check console logs and the log file. Ensure setup is skipped. Verify the main application UI launches quickly.

## VII. Uninstallation

Uninstalling the application requires two steps:

1.  **Delete the `.app` bundle:** Drag `ANPE GUI.app` from the `Applications` folder (or wherever it was placed) to the Trash.
2.  **Delete Application Support Data:** Manually navigate to `~/Library/Application Support/` (In Finder, use Go -> Go to Folder... and enter `~/Library/Application Support/`) and delete the `ANPE GUI` directory. This removes the downloaded Python environment, dependencies, and models.

*(Note: Standard macOS applications do not typically have dedicated uninstallers; users are expected to delete the .app and potentially clean up Application Support data manually).* 


create-dmg --volname "ANPE Studio Installer" --volicon "/Volumes/Mac Data/anpe_gui/anpe-gui/installer_assets/VolumeIcon.icns" --background "/Volumes/Mac Data/anpe_gui/anpe-gui/installer_assets/background.png" --window-pos 200 120 --window-size 600 400 --icon-size 100 --text-size 12 --icon "ANPE Studio.app" 150 180 --hide-extension "ANPE Studio.app" --app-drop-link 450 180 --icon "Extras" 100 500 "ANPE_Studio_Installer.dmg" "dmg_staging/"