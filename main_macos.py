# main_macos.py
import sys
import os
import logging
import time
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QProcess

# --- VERY EARLY DEBUG LOGGING ---
# Try to write to a known temporary location immediately.
# This helps determine if the script starts at all in the .app bundle.
# Use a unique filename to avoid clashes if multiple attempts are made.
# We'll use a simple text file write, as even 'logging' might not be configured yet.
_EARLY_DEBUG_LOG_FILE = f"/tmp/anpe_gui_launcher_debug_{int(time.time())}.log"
try:
    with open(_EARLY_DEBUG_LOG_FILE, "a") as f_debug:
        f_debug.write(f"--- {time.asctime()}: main_macos.py script started ---\n")
        f_debug.write(f"Python executable: {sys.executable}\n")
        f_debug.write(f"sys.argv: {sys.argv}\n")
        f_debug.write(f"sys.path: {sys.path}\n")
        f_debug.write(f"Current working directory: {os.getcwd()}\n")
        f_debug.write(f"sys.frozen attribute: {getattr(sys, 'frozen', 'Not set')}\n")
        f_debug.write(f"__file__: {__file__}\n")
except Exception as e_debug:
    # If this fails, something is very wrong at a fundamental level.
    # We can't do much more here, but this is a critical data point.
    # In a real app, you might try another location or print to stderr
    # if the .app allows stdout/stderr redirection to a file.
    print(f"CRITICAL: Failed to write to early debug log {_EARLY_DEBUG_LOG_FILE}: {e_debug}", file=sys.stderr)
# --- END VERY EARLY DEBUG LOGGING ---

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
    from installer_macos.installer_core_macos import (
        find_standalone_python_executable_macos,
        _get_bundled_resource_path_macos # May need this for app icon later
    )
    from installer_macos.setup_macos import setup_logging, main as run_setup_wizard # MODIFIED, assuming main exists
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
APP_NAME = "ANPE"
# Standard macOS Application Support path
MACOS_APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
SETUP_FLAG_FILENAME = ".setup_complete"

# --- Logging Setup ---
try:
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
        # --- Running as a Bundle ---
        bundle_dir = Path(sys.executable).parent.parent # Up two levels to Contents/
        resources_lib_dir = bundle_dir / "Resources" / "lib"
        
        # Find the specific pythonX.Y directory created by py2app
        target_python_lib_dir = None
        if resources_lib_dir.is_dir():
            for item in resources_lib_dir.iterdir():
                # Look for a directory starting with 'python' (e.g., python3.12)
                if item.is_dir() and item.name.startswith("python"):
                    target_python_lib_dir = item
                    logger.debug(f"Found py2app lib directory: {target_python_lib_dir}")
                    break # Assume only one such directory exists
        
        if not target_python_lib_dir:
             logger.error(f"Could not find pythonX.Y library directory under {resources_lib_dir}")
             return None

        main_script = target_python_lib_dir / "anpe_gui" / "run.py"
        logger.info(f"Running bundled. Main script expected at: {main_script}")
    else:
        # --- Running from Source ---
        script_dir = Path(__file__).parent
        main_script = script_dir / "anpe_gui" / "run.py"
        logger.info(f"Running from source. Main script expected at: {main_script}")

    # Check existence before returning
    if main_script.exists():
         logger.info(f"Confirmed main script exists at: {main_script}")
         return str(main_script)
    else:
         logger.error(f"Main script not found at calculated path: {main_script}")
         return None

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
        try:
            # Directly call the setup wizard's main function
            logger.info(f"Calling setup wizard with target directory: {base_install_path}")
            # Pass arguments as needed, e.g., a dictionary or specific args
            # Assuming run_setup_wizard can take base_install_path and a debug flag
            debug_mode = os.environ.get("ANPE_DEBUG") == "1"
            setup_exit_code = run_setup_wizard(target_install_dir=str(base_install_path), debug=debug_mode)
            logger.info(f"Setup wizard finished with exit code: {setup_exit_code}")
            
            if setup_exit_code != 0:
                 err_msg = "The setup wizard did not complete successfully. Cannot launch application."
                 logger.critical(err_msg)
                 show_error_dialog("Setup Failed", err_msg + "\nPlease check the setup log for details.")
                 sys.exit(1)
        except Exception as setup_e:
            err_msg = f"An error occurred while running the setup wizard: {setup_e}"
            logger.critical(err_msg, exc_info=True)
            show_error_dialog("Setup Error", err_msg)
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

    # 4. Prepare environment and execute the main application script using os.execve
    logger.info(f"Preparing environment for target Python: {target_python_exe}")
    
    # Create a clean environment for the target python
    target_env = os.environ.copy()
    target_env.pop("PYTHONHOME", None) # Remove potentially interfering PYTHONHOME
    logger.info("Removed PYTHONHOME from target environment.")
    
    # Set PYTHONPATH exclusively to the standalone python's lib dir
    python_exe_path_obj = Path(target_python_exe)
    # Derive version string like "3.11" from executable name python3.11
    python_version_str = "".join(filter(str.isdigit, python_exe_path_obj.name))
    if len(python_version_str) >= 2:
        major, minor = int(python_version_str[0]), int(python_version_str[1:])
        logger.debug(f"Derived version {major}.{minor} for target Python library path.")
    else:
        logger.warning("Could not derive major/minor version from python executable name, assuming 3.11")
        major, minor = 3, 11 # Fallback
        
    standalone_python_lib_dir = python_exe_path_obj.parent.parent / "lib" / f"python{major}.{minor}"
    if standalone_python_lib_dir.is_dir():
         logger.info(f"Setting PYTHONPATH for target process EXCLUSIVELY to: {standalone_python_lib_dir}")
         target_env["PYTHONPATH"] = str(standalone_python_lib_dir)
    else:
         logger.error(f"Could not find standalone Python lib directory at {standalone_python_lib_dir} for execve. Unsetting PYTHONPATH.")
         target_env.pop("PYTHONPATH", None)

    logger.info(f"Executing main application via os.execve: {target_python_exe} {main_app_script}")
    try:
        # Prepare arguments for execve: executable path, list of args (starting with executable name), environment
        args = [target_python_exe, main_app_script] + sys.argv[1:] # Pass along any original args
        os.execve(target_python_exe, args, target_env) # Use execve with cleaned env
    except OSError as e:
        err_msg = f"Failed to execute the main application using os.execve: {e}"
        logger.critical(err_msg, exc_info=True)
        show_error_dialog("Launch Failure", err_msg)
        sys.exit(1)
    except Exception as e:
         # Catch any other potential errors during execve setup
         err_msg = f"An unexpected error occurred trying to launch the main application: {e}"
         logger.critical(err_msg, exc_info=True)
         show_error_dialog("Launch Failure", err_msg)
         sys.exit(1)

    # The code below os.execve will not be reached if execve succeeds
    logger.critical("os.execve finished unexpectedly (this should not happen if launch succeeded).")
    sys.exit(1) 