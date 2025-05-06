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
_PBS_VERSION_TAG = "3.11.12+20250409" # Base version + build tag
# Use the non-stripped version for better standard library compatibility
_PBS_ARCHIVE_TEMPLATE = f"cpython-{_PBS_VERSION_TAG}-{{arch}}-apple-darwin-install_only.tar.gz"
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

def _get_bundled_resource_path_macos(resource_name: str) -> Optional[Path]:
    """
    Find a resource using its base name. Handles bundled (py2app) 
    and development environments.
    
    Assumes installer assets are in 'installer_assets/' (dev) or
    'Resources/assets/' (bundled).
    Also includes a fallback check relative to project root (dev) or Resources/ (bundled).
    """
    # --- Determine if running in bundled mode --- 
    # (Bundle detection logic remains the same)
    is_bundled = False
    bundle_base_path = None
    resources_path = None
    if hasattr(sys, 'executable'):
        try:
            bundle_base_path_check = Path(sys.executable).parent.parent
            resources_path_check = bundle_base_path_check / "Resources"
            if resources_path_check.is_dir():
                is_bundled = True
                bundle_base_path = bundle_base_path_check
                resources_path = resources_path_check
                logger.debug(f"Detected bundled mode via executable: {sys.executable}")
            else:
                logger.debug(f"Not bundled mode (Resources dir not found): {resources_path_check}")
        except Exception as e:
            logger.warning(f"Error checking bundle structure: {e}")

    if not is_bundled and getattr(sys, 'frozen', False):
         logger.warning("Using sys.frozen=True as fallback for bundle detection.")
         is_bundled = True
         try:
             bundle_base_path = Path(sys.executable).parent.parent
             resources_path = bundle_base_path / "Resources"
         except Exception:
              logger.error("Could not determine bundle paths even with sys.frozen=True.")
              return None

    # --- Path Finding Logic ---
    if is_bundled:
        # --- Bundled App Mode --- 
        if not resources_path:
             logger.error("Bundled mode, but resources_path is not set.")
             return None
        try:
            # 1. Primary Check: Look in Resources/assets/ 
            path_in_bundle_assets = resources_path / "assets" / resource_name # MODIFIED
            logger.debug(f"Bundled mode: Checking in Resources/assets/: {path_in_bundle_assets}")
            if path_in_bundle_assets.exists():
                logger.info(f"Found resource in bundle assets: {path_in_bundle_assets}")
                return path_in_bundle_assets.resolve()
                
            # 2. Fallback Check: Look directly in Resources/ (for non-asset files?)
            path_in_resources = resources_path / resource_name
            logger.debug(f"Bundled mode: Checking directly in Resources/ (fallback): {path_in_resources}")
            if path_in_resources.exists():
                logger.info(f"Found resource directly in Resources: {path_in_resources}")
                return path_in_resources.resolve()

            logger.error(f"Resource '{resource_name}' not found in bundle Resources/assets/ or Resources/")
            return None

        except Exception as e:
             logger.error(f"Error finding resource in bundled mode: {e}", exc_info=True)
             return None
    else:
        # --- Development Mode --- 
        try:
            script_dir = Path(__file__).parent.absolute()
            project_root = script_dir.parent.parent 
            logger.debug(f"Development mode: Using project root: {project_root}")

            # 1. Primary Check: Look in top-level installer_assets/ 
            path_in_dev_assets = project_root / "installer_assets" / resource_name # MODIFIED
            logger.debug(f"Development mode: Checking in installer_assets/: {path_in_dev_assets}")
            if path_in_dev_assets.is_file():
                logger.info(f"Development mode: Found resource in installer_assets/: {path_in_dev_assets}")
                return path_in_dev_assets.resolve()
                
            # 2. Fallback Check: Look relative to project root (for non-installer assets?)
            # Allows calls like _get_bundled_resource_path_macos('anpe_gui/resources/assets/logo.png') to still work.
            path_rel_to_root = project_root / resource_name 
            logger.debug(f"Development mode: Checking relative to root (fallback): {path_rel_to_root}")
            if path_rel_to_root.is_file():
                 logger.info(f"Development mode: Found resource relative to project root: {path_rel_to_root}")
                 return path_rel_to_root.resolve()

            logger.error(f"Resource '{resource_name}' not found in development mode (checked installer_assets/ and relative to root)")
            return None

        except Exception as e:
            logger.error(f"Error finding resource in development mode: {e}", exc_info=True)
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

    # Use the helper to find the archive path (in bundle Resources/assets or installer_assets)
    print_step(f"Locating Python archive: {python_archive_name}...")
    # Pass ONLY the filename now
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
    print_step(f"Ensuring pip is available for {python_exe_path}...")

    python_exe_path_obj = Path(python_exe_path)
    # Derive version from the executable name (e.g., python3.11) or know it's 3.11
    # Assuming the executable is named python3.X or python3.XY
    if python_exe_path_obj.name.startswith("python3."):
        try:
            version_str = python_exe_path_obj.name.split('python')[1]
            major, minor = map(int, version_str.split('.')[:2])
            logger.debug(f"Derived version {major}.{minor} from executable name.")
        except Exception:
            logger.warning(f"Could not derive version from {python_exe_path_obj.name}, falling back to hardcoded 3.11")
            major, minor = 3, 11 # Fallback, adjust if needed
    else:
        logger.warning(f"Cannot parse version from {python_exe_path_obj.name}, assuming 3.11")
        major, minor = 3, 11 # Fallback, adjust if needed

    standalone_python_lib_dir = python_exe_path_obj.parent.parent / "lib" / f"python{major}.{minor}"

    # Prepare environment for pip subprocess - CLEANED
    pip_env = os.environ.copy()
    # Remove PYTHONHOME and set exclusive PYTHONPATH
    pip_env.pop("PYTHONHOME", None)
    logger.info("Removed PYTHONHOME from pip bootstrap environment.")

    if standalone_python_lib_dir.is_dir():
        logger.info(f"Setting PYTHONPATH for pip bootstrap EXCLUSIVELY to: {standalone_python_lib_dir}")
        pip_env["PYTHONPATH"] = str(standalone_python_lib_dir) # Set ONLY this path
        logger.debug(f"Effective PYTHONPATH for pip bootstrap: {pip_env['PYTHONPATH']}")
    else:
        logger.error(f"Could not find standalone Python lib directory at {standalone_python_lib_dir}. UNSETTING PYTHONPATH. Pip bootstrap WILL likely fail.")
        pip_env.pop("PYTHONPATH", None)

    # Check if pip module is runnable with the target Python
    print_step("Checking if pip is runnable...")
    try:
        check_command = [python_exe_path, "-m", "pip", "--version"]
        logger.debug(f"Running pip check command: {' '.join(check_command)}")
        # Use the modified CLEAN environment (pip_env)
        result = subprocess.run(
            check_command,
            capture_output=True,
            text=True,
            check=False,
            env=pip_env # USE CLEANED ENV
        )

        if result.returncode == 0:
            logger.info(f"Pip check successful: {result.stdout.strip()}")
            print_success("Pip is already available.")
            return 
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

            bootstrap_command = [python_exe_path, str(get_pip_path), "--no-warn-script-location"]
            logger.debug(f"Running pip bootstrap command: {' '.join(bootstrap_command)}")

            # Use the modified CLEAN environment (pip_env)
            result = subprocess.run(
                bootstrap_command,
                capture_output=True,
                text=True,
                check=False,
                env=pip_env, # USE CLEANED ENV
                cwd=tmpdir
            )

            if result.returncode != 0:
                error_message = (
                    f"get-pip.py script execution failed with return code {result.returncode}.\\n"
                    f"Command: {' '.join(bootstrap_command)}\\n"
                    f"Stdout:\\n{result.stdout}\\n"
                    f"Stderr:\\n{result.stderr}"
                )
                print_failure(error_message)

            logger.info("get-pip.py executed successfully.")
            logger.debug(f"get-pip.py stdout:\\n{result.stdout}")
            if result.stderr:
                logger.warning(f"get-pip.py stderr:\\n{result.stderr}")

        print_step("Verifying pip installation after bootstrap...")
        try:
            check_command = [python_exe_path, "-m", "pip", "--version"]
            logger.debug(f"Running post-bootstrap pip check command: {' '.join(check_command)}")
            # Use the modified CLEAN environment (pip_env)
            result = subprocess.run(
                check_command,
                capture_output=True,
                text=True,
                check=True,
                env=pip_env # USE CLEANED ENV
            )
            logger.info(f"Pip verification successful: {result.stdout.strip()}")
            print_success("Pip bootstrap completed successfully.")
        except FileNotFoundError:
             error_message = f"Command '{python_exe_path}' not found even after bootstrap attempt."
             logger.error(error_message)
             raise PipError(error_message)
        except subprocess.CalledProcessError as e:
             error_message = (
                 f"Verification check 'pip --version' failed after bootstrap (Return Code: {e.returncode}).\\n"
                 f"Command: {' '.join(check_command)}\\n"
                 f"Stdout:\\n{e.stdout}\\n"
                 f"Stderr:\\n{e.stderr}"
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