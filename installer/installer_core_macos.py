import sys
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import tempfile
import logging
from pathlib import Path
from typing import Optional

# --- Constants ---
# Define base dir name for unpacked standalone python
STANDALONE_PYTHON_DIR_NAME = "python-standalone"
# Define specific archive filenames
_PBS_VERSION_TAG = "3.12.10+20250409" # Base version + build tag
_PBS_ARCHIVE_TEMPLATE = f"cpython-{_PBS_VERSION_TAG}-{{arch}}-apple-darwin-install_only_stripped.tar.gz"
PBS_ARCHIVE_ARM64 = _PBS_ARCHIVE_TEMPLATE.format(arch="aarch64")
PBS_ARCHIVE_X86_64 = _PBS_ARCHIVE_TEMPLATE.format(arch="x86_64")

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
# SETUP_FLAG_FILE = ".setup_complete" # Handled by main_macos.py

# --- Logging Setup ---
# Assume logger is configured by the main application/caller (e.g., setup_macos.py)
# Get a logger instance specific to this module
logger = logging.getLogger(__name__)

# --- Custom Exception ---
class PipError(RuntimeError):
    """Custom exception for pip command failures."""
    pass

# --- Helper Functions ---

def print_step(message: str):
    """Log a progress step message."""
    logger.info(f"STEP: {message}")
    # Keep print for direct execution feedback if needed for worker communication
    print(f"STEP: {message}", flush=True)

def print_success(message: str):
    """Log a success message."""
    logger.info(f"SUCCESS: {message}")
    print(f"SUCCESS: {message}", flush=True)
    # This script shouldn't exit itself; it should indicate success to the caller.

def print_failure(message: str):
    """Log a failure message and raise an exception."""
    logger.error(f"FAILURE: {message}")
    print(f"FAILURE: {message}", file=sys.stderr, flush=True)
    # Raise an exception for the calling process (e.g., setup worker) to catch
    raise RuntimeError(message)

# --- macOS Specific Resource Finder ---

def _get_bundled_resource_path_macos(relative_path: str) -> Optional[Path]:
    """Find a resource bundled by py2app or relative to the script."""
    resource_file_path = None # Initialize

    if getattr(sys, 'frozen', False):
        # --- Bundled App Mode ---
        try:
            # Resources are expected directly in Contents/Resources
            resources_path = Path(sys.executable).parent.parent / "Resources"
            resource_file_path = resources_path / relative_path
            logger.info(f"Bundled mode: Checking for resource at: {resource_file_path}")
            if resource_file_path.is_file():
                return resource_file_path.resolve() # Return absolute path
            else:
                 logger.error(f"Resource '{relative_path}' not found in bundle Resources directory: {resources_path}")
                 return None
        except Exception as e:
             logger.error(f"Error determining resource path in bundled mode: {e}", exc_info=True)
             return None
    else:
        # --- Development Mode ---
        try:
            installer_dir = Path(__file__).parent.absolute()
            project_root = installer_dir.parent # Assume installer is one level down

            # 1. Check relative to project root (e.g., 'anpe_gui/resources/...')
            path_rel_to_root = project_root / relative_path
            if path_rel_to_root.is_file():
                logger.info(f"Development mode: Found resource relative to project root: {path_rel_to_root}")
                return path_rel_to_root.resolve()
            
            # 2. Check within installer/assets/ (e.g., 'assets/logo.png')
            path_in_assets = installer_dir / "assets" / relative_path
            if path_in_assets.is_file():
                logger.info(f"Development mode: Found resource in installer assets subdir: {path_in_assets}")
                return path_in_assets.resolve()

            # 3. Check directly in installer/ (e.g., 'macos_requirements.txt')
            path_in_installer = installer_dir / relative_path
            if path_in_installer.is_file():
                logger.info(f"Development mode: Found resource directly in installer dir: {path_in_installer}")
                return path_in_installer.resolve()

            # If not found in any common dev location
            logger.error(f"Resource '{relative_path}' not found in development mode (checked relative to root, installer/, and installer/assets/)")
            return None

        except Exception as e:
            logger.error(f"Error determining resource path in development mode: {e}", exc_info=True)
            return None

# --- Core Logic Functions ---

# Replaces unpack_python_macos
def unpack_standalone_python_macos(target_install_path: str) -> str:
    """
    Detects architecture, finds the correct bundled python-build-standalone
    archive, and unpacks it.

    Args:
        target_install_path: The base directory where the python environment
                             (named STANDALONE_PYTHON_DIR_NAME) should be created.

    Returns:
        The absolute path to the created Python environment directory 
        (e.g., /path/to/target/python-standalone).

    Raises:
        RuntimeError: If the OS is not macOS, architecture is unsupported,
                      the archive is not found, or extraction fails.
    """
    logger.debug("Entering unpack_standalone_python_macos function...")
    system = platform.system()
    if system != "Darwin":
        print_failure(f"This function is only for macOS, current OS: {system}")

    # Detect architecture and select appropriate archive
    arch = platform.machine()
    if arch == "arm64":
        python_archive_name = PBS_ARCHIVE_ARM64
        logger.info(f"Detected Apple Silicon (arm64), selecting archive: {python_archive_name}")
    elif arch == "x86_64":
        python_archive_name = PBS_ARCHIVE_X86_64
        logger.info(f"Detected Intel (x86_64), selecting archive: {python_archive_name}")
    else:
        print_failure(f"Unsupported macOS architecture: {arch}")

    # Use the helper to find the archive path (in bundle Resources or installer/assets)
    print_step(f"Locating Python archive: {python_archive_name}...")
    python_archive_path_obj = _get_bundled_resource_path_macos(python_archive_name)

    if not python_archive_path_obj:
        # Error message specific to debug/bundled mode is handled inside the helper
        print_failure(f"Could not find required Python archive: {python_archive_name}")

    python_archive_path = str(python_archive_path_obj)
    logger.info(f"Found Python archive: {python_archive_path}")

    # Define target path for the extracted Python environment
    python_extract_base_path = Path(target_install_path) / STANDALONE_PYTHON_DIR_NAME
    logger.debug(f"Target extraction base path: {python_extract_base_path}")

    # Clean up previous extraction if it exists
    if python_extract_base_path.exists():
        print_step(f"Removing existing directory: {python_extract_base_path}")
        try:
            shutil.rmtree(python_extract_base_path)
            logger.debug("Successfully removed existing directory.")
        except OSError as e:
            print_failure(f"Failed to remove existing Python directory: {python_extract_base_path}. Error: {e}")

    # Extract the archive
    print_step(f"Unpacking Python to {python_extract_base_path}...")
    try:
        python_extract_base_path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(python_archive_path, 'r:gz') as tar:
            tar.extractall(path=python_extract_base_path)
            # Note: The archive likely contains a top-level directory, e.g., 'python'
            # The executable will be inside that, like 'python/install/bin/python3'
            logger.debug("Extraction completed.")
    except tarfile.ReadError:
        print_failure(f"Failed to unpack Python: The file '{python_archive_path}' is not a valid tar.gz file or is corrupted.")
    except Exception as e:
        print_failure(f"Failed to unpack Python archive '{os.path.basename(python_archive_name)}': {e}")

    print_step("Standalone Python unpacked successfully.")
    # Return the path to the base directory where it was extracted
    return str(python_extract_base_path)

# New helper function
def find_standalone_python_executable_macos(python_extract_base_path: str) -> str:
    """
    Finds the python3 executable within the unpacked python-build-standalone structure.
    Expects structure like: <base_path>/python/install/bin/python3

    Args:
        python_extract_base_path: The base directory where the standalone Python
                                  archive was extracted.

    Returns:
        The absolute path to the python3 executable.

    Raises:
        RuntimeError: If the executable cannot be found.
    """
    print_step("Locating python3 executable in unpacked standalone distribution...")
    base_path = Path(python_extract_base_path)
    # Structure seems to be <base_path>/python/bin/python3 based on listing
    possible_paths = [
        base_path / "python" / "bin" / "python3",
        # Keep original checks as fallbacks just in case?
        # base_path / "python" / "install" / "bin" / "python3",
        # base_path / "install" / "bin" / "python3", 
        # base_path / "bin" / "python3"
    ]

    for potential_exe_path in possible_paths:
        logger.debug(f"Checking for executable at: {potential_exe_path}")
        if potential_exe_path.is_file() and os.access(potential_exe_path, os.X_OK):
            abs_path_str = str(potential_exe_path.resolve())
            logger.info(f"Found standalone Python executable: {abs_path_str}")
            return abs_path_str

    # If none found
    print_failure(f"Could not find python3 executable within the expected structure under {base_path}. Checked paths like {possible_paths[0]}")

# Updated bootstrap_pip_macos
def bootstrap_pip_macos(python_exe_path: str):
    """
    Ensures pip is available for the specified Python executable, downloading
    and running get-pip.py if necessary.

    Args:
        python_exe_path: The absolute path to the standalone Python executable.

    Raises:
        RuntimeError: If pip bootstrapping fails.
        PipError: If running pip check fails after bootstrapping.
    """
    # No longer needs python_extract_path or env vars
    print_step(f"Ensuring pip is available for {python_exe_path}...")

    # Prepare environment (just use default system env)
    current_env = os.environ.copy()

    # Check if pip module is runnable with the target Python
    print_step("Checking if pip is runnable...")
    try:
        check_command = [python_exe_path, "-m", "pip", "--version"]
        logger.debug(f"Running pip check command: {' '.join(check_command)}")
        result = subprocess.run(
            check_command,
            capture_output=True,
            text=True,
            check=False, # Check return code manually
            env=current_env # Use default env
        )

        if result.returncode == 0:
            logger.info(f"Pip check successful: {result.stdout.strip()}")
            print_success("Pip is already available.")
            return # Pip already installed
        else:
            logger.warning(f"Pip check failed (Return Code: {result.returncode}). Stdout: {result.stdout.strip()}. Stderr: {result.stderr.strip()}. Proceeding with bootstrap.")

    except FileNotFoundError:
        logger.warning(f"Command '{python_exe_path}' not found. Cannot check pip. Proceeding with bootstrap attempt.")
    except Exception as e:
        logger.warning(f"Error checking for pip: {e}. Proceeding with bootstrap.")

    # Attempt bootstrap using get-pip.py
    print_step("Bootstrapping pip using get-pip.py...")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            get_pip_path = Path(tmpdir) / "get-pip.py"
            print_step(f"Downloading get-pip.py from {GET_PIP_URL}...")
            try:
                with urllib.request.urlopen(GET_PIP_URL) as response, open(get_pip_path, 'wb') as out_file:
                    if response.status != 200:
                         raise RuntimeError(f"Failed to download get-pip.py (HTTP Status: {response.status})")
                    shutil.copyfileobj(response, out_file)
                logger.info(f"Downloaded get-pip.py to {get_pip_path}")
            except Exception as e:
                print_failure(f"Failed to download get-pip.py: {e}")

            # Run get-pip.py using the target standalone Python
            bootstrap_command = [python_exe_path, str(get_pip_path), "--no-warn-script-location"]
            logger.debug(f"Running pip bootstrap command: {' '.join(bootstrap_command)}")

            result = subprocess.run(
                bootstrap_command,
                capture_output=True,
                text=True,
                check=False, # Check return code manually
                env=current_env,
                cwd=tmpdir
            )

            if result.returncode != 0:
                # Updated error message formatting
                error_message = (
                    f"get-pip.py script execution failed with return code {result.returncode}.\n"
                    f"Command: {' '.join(bootstrap_command)}\n"
                    f"Stdout:\n{result.stdout}\n"
                    f"Stderr:\n{result.stderr}"
                )
                print_failure(error_message)

            logger.info("get-pip.py executed successfully.")
            logger.debug(f"get-pip.py stdout:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"get-pip.py stderr:\n{result.stderr}")

        # Verify pip installation again after bootstrap
        print_step("Verifying pip installation after bootstrap...")
        try:
            check_command = [python_exe_path, "-m", "pip", "--version"]
            logger.debug(f"Running post-bootstrap pip check command: {' '.join(check_command)}")
            result = subprocess.run(
                check_command,
                capture_output=True,
                text=True,
                check=True, # Check=True now
                env=current_env
            )
            logger.info(f"Pip verification successful: {result.stdout.strip()}")
            print_success("Pip bootstrap completed successfully.")
        except FileNotFoundError:
             error_message = f"Command '{python_exe_path}' not found even after bootstrap attempt."
             logger.error(error_message)
             raise PipError(error_message)
        except subprocess.CalledProcessError as e:
            # Updated error message formatting
             error_message = (
                 f"Verification check 'pip --version' failed after bootstrap (Return Code: {e.returncode}).\n"
                 f"Command: {' '.join(check_command)}\n"
                 f"Stdout:\n{e.stdout}\n"
                 f"Stderr:\n{e.stderr}"
             )
             logger.error(error_message)
             raise PipError(error_message)
        except Exception as e:
             error_message = f"An unexpected error occurred during pip verification: {e}"
             logger.error(error_message, exc_info=True)
             raise PipError(error_message)

    except Exception as e:
        if isinstance(e, (RuntimeError, PipError)):
             raise
        error_message = f"An unexpected error occurred during pip bootstrap process: {e}"
        print_failure(error_message)

# --- Main Function (Example/Testing Only) ---
def main_macos(install_path: str):
    """
    Performs the core macOS environment setup using standalone Python.
    1. Unpacks Standalone Python.
    2. Finds executable.
    3. Bootstraps pip.
    4. Installs dependencies via pip.

    Args:
        install_path: The root directory for the installation.
    """
    logger.info(f"Starting macOS setup process in: {install_path}")
    python_env_base_dir = Path(install_path).resolve()
    python_env_base_dir.mkdir(parents=True, exist_ok=True)

    python_extract_base_path = None
    try:
        # 1. Unpack Standalone Python Environment
        python_extract_base_path = unpack_standalone_python_macos(str(python_env_base_dir))
        logger.info(f"Standalone Python unpacked to: {python_extract_base_path}")

        # 2. Find Python Executable
        python_exe = find_standalone_python_executable_macos(python_extract_base_path)
        logger.info(f"Standalone Python executable found at: {python_exe}")

        # 3. Bootstrap Pip (using the standalone Python)
        bootstrap_pip_macos(python_exe)

        # --- Find Requirements File ---
        print_step("Locating requirements file...")
        requirements_file = "macos_requirements.txt"
        requirements_path_obj = _get_bundled_resource_path_macos(requirements_file)
        if not requirements_path_obj:
            print_failure(f"Could not find requirements file: {requirements_file}")

        requirements_path = str(requirements_path_obj)
        logger.info(f"Found requirements file: {requirements_path}")

        # 4. Install Dependencies using pip (using standalone python)
        # The actual pip install logic is now handled within the EnvironmentSetupWorkerMacOS
        # using QProcess. This function call is removed from the example.
        # stdout, stderr = run_pip_install_macos(python_exe, f"-r {requirements_path}")
        # if stdout:
        #     logger.info(f"Pip install stdout:\\n{stdout}\")
        # if stderr:
        #     logger.warning(f"Pip install stderr:\\n{stderr}\")

        print_success("Core environment setup completed successfully.")

    except (RuntimeError, PipError) as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        # Perform cleanup: Remove the partially created environment directory
        if python_extract_base_path and Path(python_extract_base_path).exists():
            logger.warning(f"Attempting to clean up failed installation directory: {python_extract_base_path}")
            try:
                shutil.rmtree(python_extract_base_path)
                logger.info("Cleanup successful.")
            except Exception as cleanup_err:
                logger.error(f"Cleanup failed for {python_extract_base_path}: {cleanup_err}", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred during setup: {e}", exc_info=True)
        if python_extract_base_path and Path(python_extract_base_path).exists():
            logger.warning(f"Attempting to clean up failed installation directory: {python_extract_base_path}")
            try:
                shutil.rmtree(python_extract_base_path)
                logger.info("Cleanup successful.")
            except Exception as cleanup_err:
                logger.error(f"Cleanup failed for {python_extract_base_path}: {cleanup_err}", exc_info=True)
        raise RuntimeError(f"Critical setup error: {e}")

# --- Standalone Execution Guard ---
# Allows running this script directly for isolated testing
if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1]:
        # Use logger for consistency, then print usage and exit
        logging.error("Usage: python installer_core_macos.py <target_install_path>")
        sys.exit(f"Usage: {sys.argv[0]} <target_install_path>")

    target_install_path_arg = sys.argv[1]
    try:
        print(f"--- Running {os.path.basename(__file__)} in standalone mode ---")
        print(f"Target install path: {target_install_path_arg}")
        # Setup basic logging for standalone run if not already configured
        if not logging.getLogger().hasHandlers():
             logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        main_macos(target_install_path_arg)
        print(f"--- Standalone execution of {os.path.basename(__file__)} finished ---")
    except Exception as e:
        # Catch any exception that bubbles up, log, print failure, and exit
        logger.critical(f"An unexpected error occurred during standalone setup: {e}", exc_info=True)
        print(f"FAILURE: An unexpected error occurred during setup: {e}", file=sys.stderr, flush=True)
        sys.exit(1) # Exit with error code