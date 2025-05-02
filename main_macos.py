# main_macos.py
import sys
import os
import logging
import time
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QProcess

# --- Add project root to sys.path for dev/debug --- 
# This helps find the installer package when run directly
if not getattr(sys, 'frozen', False):
    script_dir = Path(__file__).parent
    project_root = script_dir # If main_macos.py is in root
    # If main_macos.py is moved elsewhere, adjust project_root accordingly
    if str(project_root) not in sys.path:
         sys.path.insert(0, str(project_root))

# Now import from installer package
try:
    # Use the correct macOS-specific function finder
    from installer.installer_core_macos import ( 
        find_standalone_python_executable_macos,
        _get_bundled_resource_path_macos # May need this for app icon later
    )
    # Removed get_app_support_dir as it doesn't exist in utils.py
    # from installer.utils import get_app_support_dir 
    from installer.setup_macos import setup_logging # Use the same setup logging
except ImportError as e:
    # Fallback basic logging if imports fail
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.critical(f"Failed to import installer components: {e}")
    # Attempt to show a message box even if imports fail
    try:
        app = QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("ANPE GUI Launch Error")
        msg.setText("A critical error occurred during launch.\nCould not load required installation components.")
        msg.setDetailedText(f"ImportError: {e}")
        msg.exec()
    except Exception as qt_e:
         print(f"CRITICAL: Could not display error dialog: {qt_e}", file=sys.stderr)
    sys.exit(1)

# --- Constants ---
APP_NAME = "ANPE GUI"
# Standard macOS Application Support path
MACOS_APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
SETUP_FLAG_FILENAME = ".setup_complete"

# --- Logging Setup ---
try:
    # Use the setup_logging function from installer.setup_macos
    logger = setup_logging() 
except Exception as log_e:
     # Basic console logging as fallback
     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
     logger = logging.getLogger()
     logger.error(f"Failed to initialize file logging via setup_logging: {log_e}")

# --- Helper Functions ---

def _get_base_install_path() -> Path:
    """Determines the base installation path.
    
    Uses ANPE_INSTALL_PATH env var if set (for debug/simulation).
    Otherwise, uses the standard macOS Application Support directory.
    """
    simulated_path_str = os.environ.get("ANPE_INSTALL_PATH")
    if simulated_path_str:
        logger.info(f"Debug/Simulated mode: Using base path from ANPE_INSTALL_PATH: {simulated_path_str}")
        return Path(simulated_path_str)
    else:
        logger.info(f"Standard mode: Using base path: {MACOS_APP_SUPPORT_DIR}")
        return MACOS_APP_SUPPORT_DIR

def _get_main_script_path_macos() -> str | None:
    """Gets the path to the main anpe_gui application script (`anpe_gui/run.py`).
    Handles running from source and bundled app scenarios.
    """
    if getattr(sys, 'frozen', False):
        # Running as a bundle
        # In py2app, sys.executable is Contents/MacOS/AppName
        # Resources are typically in Contents/Resources/
        bundle_dir = Path(sys.executable).parent.parent # Up two levels to Contents/
        main_script = bundle_dir / "Resources" / "anpe_gui" / "run.py"
        logger.info(f"Running bundled. Main script expected at: {main_script}")
    else:
        # Running from source (relative to this script's location)
        script_dir = Path(__file__).parent
        main_script = script_dir / "anpe_gui" / "run.py"
        logger.info(f"Running from source. Main script expected at: {main_script}")
        
    return str(main_script) if main_script.exists() else None

def show_error_dialog(title, message, detailed_text=""):
    """Displays a simple error message box using PyQt6."""
    # Need a QApplication instance to show a dialog
    # Check if one already exists, otherwise create a temporary one
    app = QApplication.instance()
    if not app:
        logger.info("Creating temporary QApplication instance for error dialog.")
        app = QApplication(sys.argv)
        created_app = True
    else:
        created_app = False
        
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    if detailed_text:
        msg.setDetailedText(str(detailed_text))
    msg.exec()
    
    # Avoid issues if we created a temporary app instance
    # if created_app:
    #     app.quit() # This might interfere if called from within an existing event loop

# --- Main Execution Logic ---

if __name__ == "__main__":
    logger.info("--- ANPE GUI macOS Launcher Started ---")
    logger.info(f"Launcher Python: {sys.executable}")
    logger.info(f"Launcher working directory: {os.getcwd()}")

    # 1. Determine the base installation path
    base_install_path = _get_base_install_path()

    # 2. Check if setup has been completed
    setup_complete_flag = base_install_path / SETUP_FLAG_FILENAME
    logger.info(f"Checking for setup flag: {setup_complete_flag}")

    # Allow forcing setup via environment variable (for debug/testing)
    force_setup = os.environ.get("ANPE_FORCE_SETUP") == "1"

    if not setup_complete_flag.exists() or force_setup:
        if force_setup:
             logger.warning("ANPE_FORCE_SETUP=1 detected. Forcing setup wizard execution.")
        else:
             logger.info("Setup flag not found. Setup required.")
        
        # --- Run the Setup Wizard --- 
        logger.info("Launching setup wizard...")
        setup_script = _get_bundled_resource_path_macos("installer/setup_macos.py") 
        
        if not setup_script or not setup_script.exists():
             err_msg = "Cannot start setup: setup_macos.py not found."
             logger.critical(err_msg)
             show_error_dialog("Setup Error", err_msg)
             sys.exit(1)
             
        setup_command = [
            sys.executable, # Use the *current* python (launcher) to run setup
            str(setup_script),
            "--target-install-dir",
            str(base_install_path)
        ]
        # Add --debug if the launcher itself is in debug mode
        if os.environ.get("ANPE_DEBUG") == "1": 
             setup_command.append("--debug")
        
        logger.info(f"Running setup command: {' '.join(setup_command)}")
        setup_process = QProcess()
        setup_process.start(setup_command[0], setup_command[1:])
        if not setup_process.waitForStarted():
             err_msg = f"Failed to start setup wizard process: {setup_process.errorString()}"
             logger.critical(err_msg)
             show_error_dialog("Setup Error", err_msg)
             sys.exit(1)
        
        # Wait for the setup process to finish
        setup_process.waitForFinished(-1) 
        exit_code = setup_process.exitCode()
        logger.info(f"Setup wizard finished with exit code: {exit_code}")
        
        if exit_code != 0:
             err_msg = "The setup wizard did not complete successfully. Cannot launch application."
             logger.critical(err_msg)
             # Error details might be in the setup log ~/Library/Logs/ANPE GUI/
             show_error_dialog("Setup Failed", err_msg + "\nPlease check the setup log for details.")
             sys.exit(1)
        
        # Re-check for the flag after setup finishes
        if not setup_complete_flag.exists():
             err_msg = "Setup completed, but the completion flag is missing. Cannot launch application."
             logger.critical(err_msg)
             show_error_dialog("Launch Error", err_msg)
             sys.exit(1)
        # --- End Setup Wizard --- 
        
    # 3. Launch the main application using the standalone Python
    logger.info("Setup flag found. Proceeding to launch application.")
    logger.info("Attempting to launch main application...")

    # Find the standalone python executable using the CORRECT helper
    # Pass the *parent* of the 'python-standalone' directory if that's base_install_path
    python_env_base = base_install_path / "python-standalone"
    logger.info(f"Looking for target Python environment in: {python_env_base}")
    target_python_exe = find_standalone_python_executable_macos(str(python_env_base))

    if not target_python_exe:
        err_msg = ("The main application cannot be launched because the required "
                   "standalone Python environment was not found or is corrupted.")
        logger.error(f"Could not find python3 executable within the expected structure under {python_env_base}. Checked paths like {python_env_base}/python/install/bin/python3")
        logger.critical(f"Launch Error: {err_msg}\n\nPlease try running the application again. If the problem persists, consider reinstalling.")
        show_error_dialog("Launch Error", err_msg, detailed_text="Please ensure the application setup completed correctly.")
        sys.exit(1)

    # Get the path to the application's main script (anpe_gui/run.py)
    main_app_script = _get_main_script_path_macos()
    if not main_app_script:
        err_msg = "Cannot launch application: Main script (anpe_gui/run.py) not found."
        logger.critical(err_msg)
        show_error_dialog("Launch Error", err_msg)
        sys.exit(1)
        
    logger.info(f"Found target Python: {target_python_exe}")
    logger.info(f"Found main application script: {main_app_script}")

    # 4. Execute the main application script using os.execv
    logger.info(f"Executing main application via os.execv: {target_python_exe} {main_app_script}")
    try:
        # Prepare arguments for execv: executable path, then list of args starting with executable name
        args = [target_python_exe, main_app_script] + sys.argv[1:] # Pass along any original args
        os.execv(target_python_exe, args)
    except OSError as e:
        err_msg = f"Failed to execute the main application using os.execv: {e}"
        logger.critical(err_msg, exc_info=True)
        show_error_dialog("Launch Failure", err_msg)
        sys.exit(1)
    except Exception as e:
         # Catch any other potential errors during execv setup
         err_msg = f"An unexpected error occurred trying to launch the main application: {e}"
         logger.critical(err_msg, exc_info=True)
         show_error_dialog("Launch Failure", err_msg)
         sys.exit(1)

    # The code below os.execv will not be reached if execv succeeds
    logger.critical("os.execv finished unexpectedly (this should not happen if launch succeeded).")
    sys.exit(1) 