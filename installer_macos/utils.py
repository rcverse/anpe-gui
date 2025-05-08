import sys
import os
import logging
import time # Added for unique log filename

# --- Debugging Setup ---
log_filename = None
try:
    # Determine the directory where the executable is running
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Running as a script (use CWD or script dir? CWD is simpler)
        exe_dir = os.getcwd()

    # Define the log filename (place it directly in the exe directory)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    # Rename log file to be the formal installation log
    log_filename = os.path.join(exe_dir, f"anpe_install_{timestamp}.log")

    # Basic logging configuration
    logging.basicConfig(filename=log_filename,
                        level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"ANPE GUI Installer logging initialized. Log file: {log_filename}")
except Exception as e:
    # Fallback: print to stderr if logging setup fails
    print(f"Error setting up logging to file '{log_filename if log_filename else 'UNKNOWN'}': {e}", file=sys.stderr)
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s') # Log to console if file fails
    logging.info("Logging to console due to file setup error.")

# --- End Debugging Setup ---

def get_resource_path(relative_path: str) -> str:
    """ Get the absolute path to a resource, works for dev and for PyInstaller.
        Resolves paths relative to the 'installer' directory.
    Args:
        relative_path: The relative path from the installer module directory.

    Returns:
        The absolute path to the resource.
    """
    is_frozen = hasattr(sys, '_MEIPASS')

    try:
        if is_frozen:
            # PyInstaller mode: base_path is the installer dir inside _MEIPASS
            base_path = os.path.join(sys._MEIPASS, 'installer')
            logging.debug(f"Running Frozen. Base path: {base_path}")
        else:
            # Development mode: base_path is the directory containing this script (installer/)
            base_path = os.path.dirname(os.path.abspath(__file__)) # /path/to/project/installer
            logging.debug(f"Running in Dev mode. Base path: {base_path}")

    except Exception as e:
        logging.error(f"Error determining base path: {e}", exc_info=True)
        base_path = os.path.dirname(os.path.abspath(__file__))
        logging.warning(f"Falling back to script directory as base_path: {base_path}")

    # Join the base path (installer dir) with the relative path provided
    resolved_path = os.path.join(base_path, relative_path)
    # Use normpath to handle potential .. segments correctly
    resolved_path = os.path.normpath(resolved_path) 
    logging.debug(f"Resolving relative_path '{relative_path}' to absolute_path '{resolved_path}'")

    # Extra check: Log if the final path doesn't exist
    if not os.path.exists(resolved_path):
        logging.warning(f"Resolved path does not exist: {resolved_path}")

    return resolved_path
