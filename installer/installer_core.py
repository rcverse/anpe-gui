import sys
import os
import platform
import shutil
import subprocess
import zipfile
import tarfile
import urllib.request
import tempfile
import logging
from pathlib import Path

# --- Use unified resource path finder --- 
# Assumes utils.py provides get_resource_path that handles _MEIPASS/installer base
try:
    # Use absolute import path consistent with project structure
    from installer.utils import get_resource_path 
except ImportError:
    # Fallback if installer_core is tested standalone
    print("WARNING: Could not import get_resource_path from installer.utils. Using basic relative path resolution.", file=sys.stderr)
    def get_resource_path(relative_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # If run standalone, assume assets are relative to this script's dir?
        # Or maybe relative to parent? This fallback is tricky.
        # For simplicity, assume relative to script dir here.
        return os.path.join(script_dir, relative_path)
# --- End resource path setup ---

# --- Constants ---
PYTHON_DIR_NAME = "python"
APP_CODE_DIR_NAME = "anpe_gui" # Target directory name in install location
# Source path for anpe_gui relative to _MEIPASS root
APP_SOURCE_FOLDER_NAME = "../assets/anpe_gui"  # Changed to match actual MEIPASS structure where files are in assets/
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
# Add constant for docs directory
DOCS_DIR_NAME = "docs"

# --- Logging Setup (basic if run standalone) ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    # Assume logger is configured by the main application (setup_windows.pyw -> utils.py)
    logger = logging.getLogger() # Get root logger

# --- Helper Functions (using logging) ---

def print_step(message: str):
    """Log a progress step message."""
    logger.info(f"STEP: {message}")
    # Keep print for direct execution feedback if needed, but primary is logging
    print(f"STEP: {message}", flush=True)

def print_success(message: str):
    """Log a success message and exit."""
    logger.info(f"SUCCESS: {message}")
    print(f"SUCCESS: {message}", flush=True)
    sys.exit(0)

def print_failure(message: str):
    """Log a failure message and exit."""
    logger.error(f"FAILURE: {message}")
    print(f"FAILURE: {message}", file=sys.stderr, flush=True)
    sys.exit(1)

def print_python_path(path: str):
    """Log the detected Python executable path."""
    logger.info(f"Python executable found: {path}")
    # CRITICAL: Print this to stdout for the worker process to capture
    print(f"Python executable found: {path}", flush=True)

def find_and_get_resource_path(relative_path_from_installer_dir: str) -> str:
    """Wrapper around get_resource_path that includes existence check and logging."""
    # The relative path should be relative to the installer directory base
    # used by get_resource_path.
    print_step(f"Locating bundled resource relative to installer dir: {relative_path_from_installer_dir}...")
    try:
        abs_path = get_resource_path(relative_path_from_installer_dir)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Resource not found at expected path: {abs_path}")
        logger.info(f"Found resource: {abs_path}")
        print_step(f"Found resource: {os.path.basename(relative_path_from_installer_dir)}")
        return abs_path
    except Exception as e:
        print_failure(f"Could not find or access resource '{relative_path_from_installer_dir}': {e}")

def unpack_python(target_install_path: str):
    """Unpack the bundled Python distribution."""
    logger.debug("Entering unpack_python function...")
    system = platform.system()
    archive_type = ""
    # Relative path within the bundle's top-level assets dir
    python_archive_relative_path_in_bundle = 'assets/python-3.12.9-embed-amd64.zip'

    if system == "Windows":
        # Path relative to the installer directory (need to go up one level)
        python_archive_relative_path = f'../{python_archive_relative_path_in_bundle}'
        archive_type = "zip"
    else:
        print_failure(f"Unsupported operating system: {system}")

    # Use the unified function to get the absolute path
    python_archive_path = find_and_get_resource_path(python_archive_relative_path)

    logger.debug(f"Found Python archive: {python_archive_path}")
    python_extract_path = Path(target_install_path) / PYTHON_DIR_NAME
    logger.debug(f"Target extraction path: {python_extract_path}")

    if python_extract_path.exists():
        print_step(f"Removing existing directory: {python_extract_path}")
        try:
            shutil.rmtree(python_extract_path)
            logger.debug("shutil.rmtree completed.")
        except OSError as e:
            print_failure(f"Failed to remove existing Python directory: {python_extract_path}. Error: {e}")

    print_step(f"Unpacking Python to {python_extract_path}...")
    try:
        if archive_type == "zip":
            logger.debug(f"Opening zip file: {python_archive_path}")
            with zipfile.ZipFile(python_archive_path, 'r') as zip_ref:
                logger.debug("Zip file opened. Starting extraction...")
                zip_ref.extractall(python_extract_path)
                logger.debug("Extraction completed.")
    except zipfile.BadZipFile:
        print_failure(f"Failed to unpack Python: The file '{python_archive_path}' is not a valid zip file or is corrupted.")
    except Exception as e:
        print_failure(f"Failed to unpack Python archive '{os.path.basename(python_archive_path)}': {e}")

    print_step("Python unpacked successfully.")
    return str(python_extract_path) # Return as string

def find_python_executable(python_extract_path: str) -> str:
    """Find the python executable within the unpacked directory."""
    print_step("Locating Python executable...")
    system = platform.system()
    expected_path = ""
    if system == "Windows":
        expected_path = Path(python_extract_path) / "python.exe"
    else:
         print_failure(f"Cannot determine Python executable path for OS: {system}")

    if not expected_path.is_file():
        logger.error(f"Searched for Python executable at: {expected_path}")
        if expected_path.parent.is_dir():
            logger.error(f"Contents of {expected_path.parent}: {os.listdir(expected_path.parent)}")
        else:
             logger.error(f"Parent directory {expected_path.parent} does not exist.")
        print_failure(f"Python executable not found after unpacking.")

    abs_path_str = str(expected_path.resolve())
    print_python_path(abs_path_str) # CRITICAL: Print path for the GUI worker
    return abs_path_str

def enable_site_packages(python_extract_path: str):
    """Find the ._pth file and uncomment 'import site' to enable site-packages."""
    print_step("Enabling site-packages in Python environment...")
    pth_file_path = None
    python_extract_path_obj = Path(python_extract_path)
    try:
        # Use glob to find the ._pth file
        pth_files = list(python_extract_path_obj.glob("python*._pth"))
        if not pth_files:
             print_failure(f"Could not find the python*._pth file in {python_extract_path}")
        if len(pth_files) > 1:
             logger.warning(f"Found multiple ._pth files: {pth_files}. Using the first one: {pth_files[0]}")
        pth_file_path = pth_files[0]

    except Exception as e:
        print_failure(f"Error searching for ._pth file in {python_extract_path}: {e}")

    print_step(f"Found ._pth file: {pth_file_path.name}")
    updated_lines = []
    modified = False
    try:
        lines = pth_file_path.read_text(encoding='utf-8').splitlines()
        
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == "#import site":
                updated_lines.append("import site") # Uncomment the line
                modified = True
                print_step("Uncommented 'import site' in ._pth file.")
            elif stripped_line == "import site":
                 updated_lines.append(line) # Already uncommented
                 print_step("'import site' already uncommented in ._pth file.")
                 modified = False # No need to write if it was already correct
                 break # Assume only one import site line
            else:
                updated_lines.append(line)
        
        if modified:
            print_step(f"Writing updated ._pth file: {pth_file_path}")
            # Add newline characters back
            pth_file_path.write_text('\n'.join(updated_lines) + '\n', encoding='utf-8')
            print_step("._pth file updated successfully.")
        
    except Exception as e:
        print_failure(f"Error reading or writing ._pth file {pth_file_path}: {e}")

def bootstrap_pip(python_exe: str):
    """Download and run get-pip.py to install pip."""
    print_step("Bootstrapping pip installation...")
    get_pip_path = ""
    try:
        print_step(f"Downloading get-pip.py from {GET_PIP_URL}...")
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=".py") as tmp_file:
            with urllib.request.urlopen(GET_PIP_URL) as response:
                if response.status != 200:
                    print_failure(f"Failed to download get-pip.py. Status code: {response.status}")
                tmp_file.write(response.read())
                get_pip_path = tmp_file.name
        logger.info(f"Downloaded get-pip.py to: {get_pip_path}")

        print_step(f"Running get-pip.py using {python_exe}...")
        command = [python_exe, get_pip_path]
        creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=creationflags)
        logger.debug(f"get-pip.py STDOUT:\n{result.stdout}") # Use logger
        if result.stderr:
            logger.warning(f"get-pip.py STDERR:\n{result.stderr}") # Use logger
        print_step("pip bootstrapped successfully.")

    except urllib.error.URLError as e:
        print_failure(f"Network error downloading get-pip.py: {e}")
    except subprocess.CalledProcessError as e:
        error_message = f"Failed command: {' '.join(e.cmd)}\nExit Code: {e.returncode}\n"
        error_message += f"STDOUT:\n{e.stdout}\n"
        error_message += f"STDERR:\n{e.stderr}"
        logger.error(f"get-pip.py execution failed:\n{error_message}") # Use logger
        print_failure(f"Failed to execute get-pip.py. Check logs for details.")
    except Exception as e:
        print_failure(f"An unexpected error occurred during pip bootstrapping: {e}")
    finally:
        if get_pip_path and os.path.exists(get_pip_path):
            try:
                os.remove(get_pip_path)
                logger.info(f"Removed temporary get-pip.py file: {get_pip_path}")
            except OSError as e:
                 logger.warning(f"Failed to remove temporary file {get_pip_path}: {e}")

def run_pip_install(python_exe: str, package: str):
    """Run pip install for a given package using the specified Python executable."""
    if package == "--upgrade pip":
        print_step(f"Upgrading pip...")
        command = [python_exe, "-m", "pip", "install", "--upgrade", "pip"]
    elif package.startswith("--"):
        print_failure(f"Unsupported pip argument style encountered: {package}")
    else:
        print_step(f"Installing {package}...")
        command = [python_exe, "-m", "pip", "install", package]
    
    logger.info(f"Executing pip command: {' '.join(command)}")
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=creationflags)
        logger.debug(f"PIP STDOUT for {package}:\n{result.stdout}") # Use logger
        if result.stderr:
            logger.warning(f"PIP STDERR for {package}:\n{result.stderr}") # Use logger
        print_step(f"Successfully processed {package}.")
    except subprocess.CalledProcessError as e:
        error_message = f"Failed command: {' '.join(e.cmd)}\nExit Code: {e.returncode}\n"
        error_message += f"PIP STDOUT:\n{e.stdout}\n"
        error_message += f"PIP STDERR:\n{e.stderr}"
        logger.error(f"pip install for {package} failed:\n{error_message}") # Use logger
        print_failure(f"Failed to process {package}. Check logs for details.")
    except FileNotFoundError:
        print_failure(f"Failed to run pip. Command '{command[0]}' not found. Is Python correctly unpacked at '{python_exe}'?")
    except Exception as e:
         print_failure(f"An unexpected error occurred while running pip for {package}: {e}")

def install_required_packages(python_exe: str, install_base_path: str):
    """Reads requirements.txt and installs all specified packages."""
    print_step("Installing required packages from requirements file...")
    requirements_filename = "windows_requirements.txt"
    required_packages = []
    try:
        # find_and_get_resource_path expects the path relative to the installer dir.
        # If this script (installer_core.py) is in the installer dir,
        # then windows_requirements.txt should also be in the installer dir
        # or a subdirectory accessible via a relative path from it.
        # Assuming windows_requirements.txt is located alongside installer_core.py or in a known relative path.
        requirements_path_str = find_and_get_resource_path(requirements_filename) # Path relative to installer module
        requirements_path = Path(requirements_path_str)
        
        logger.info(f"Reading requirements from {requirements_path}...")
        lines = requirements_path.read_text(encoding='utf-8').splitlines()
        for line in lines:
            stripped_line = line.strip()
            if stripped_line and not stripped_line.startswith('#'):
                required_packages.append(stripped_line)
        logger.info(f"Found {len(required_packages)} packages to install: {required_packages}")
        if not required_packages:
             print_failure(f"No packages found in {requirements_filename}. Installation cannot proceed.")

    except FileNotFoundError:
        # This will be caught by find_and_get_resource_path if file not found.
        # Added specific check for clarity and to ensure print_failure is called directly.
        print_failure(f"Could not find the requirements file: {requirements_filename}. Ensure it is bundled correctly relative to the installer module.")
    except Exception as e:
        print_failure(f"Failed to read or parse {requirements_filename}: {e}")

    # Install the packages read from the file
    for package in required_packages:
        run_pip_install(python_exe, package)
    print_step("All required packages installed successfully.")

def copy_app_code(target_install_path: str):
    """Copies the application source code (anpe_gui) to the target dir."""
    print_step("Deploying application source code...")
    try:
        # Source path is now relative to installer dir (needs ..)
        source_gui_rel_path = APP_SOURCE_FOLDER_NAME 
        source_gui_abs_path = find_and_get_resource_path(source_gui_rel_path)
        source_gui_path = Path(source_gui_abs_path)

        # Define target path
        target_gui_path = Path(target_install_path) / APP_CODE_DIR_NAME # Use constant for target dir name
        
        logger.info(f"Copying GUI source from '{source_gui_path}' to '{target_gui_path}'...")

        # Remove existing target directory if it exists
        if target_gui_path.exists():
            logger.warning(f"Removing existing directory before copy: {target_gui_path}")
            shutil.rmtree(target_gui_path)

        # --- Ignore __pycache__ --- 
        def ignore_pycache(dir, files):
            return [f for f in files if f == '__pycache__']
        # --------------------------
        shutil.copytree(source_gui_path, target_gui_path, dirs_exist_ok=False, ignore=ignore_pycache)
        logger.info("Successfully copied anpe_gui directory.")
        print_step("Application source code deployed successfully.")

    except FileNotFoundError as fnf_error:
        logger.error(f"Error copying GUI source: {fnf_error}", exc_info=True)
        print_failure(f"Failed to copy application source code: {fnf_error}")
    except Exception as e:
        logger.error(f"Unexpected error copying GUI source: {e}", exc_info=True)
        print_failure(f"An unexpected error occurred while copying application source code: {e}")

def copy_bundled_executables(target_install_path: str):
    """Copies the bundled ANPE.exe and uninstall.exe to the target dir."""
    executables_to_copy = {
        # Paths relative to _MEIPASS root, need .. from installer dir base
        "ANPE.exe": "../assets/ANPE.exe",
        "uninstall.exe": "../assets/uninstall.exe" 
    }
    
    for exe_name, source_rel_path in executables_to_copy.items():
        print_step(f"Deploying {exe_name}...")
        try:
            # find_and_get_resource_path expects path relative to installer dir base
            source_abs_path = find_and_get_resource_path(source_rel_path)
            destination_path = Path(target_install_path) / exe_name
            
            logger.info(f"Copying {exe_name} from '{source_abs_path}' to '{destination_path}'...")
            shutil.copy2(source_abs_path, destination_path) # copy2 preserves metadata
            logger.info(f"Successfully copied {exe_name}.")
            print_step(f"{exe_name} deployed successfully.")
            
        except FileNotFoundError as fnf_error:
            logger.error(f"Error copying {exe_name}: {fnf_error}", exc_info=True)
            print_failure(f"Could not find the bundled executable '{exe_name}' at expected path '{source_rel_path}'.")
        except Exception as e:
            logger.error(f"Unexpected error copying {exe_name}: {e}", exc_info=True)
            print_failure(f"An unexpected error occurred while copying {exe_name}: {e}")

def copy_icon_file(target_install_path: str):
    """Copies the application icon file to the installation root."""
    icon_filename = "app_icon_logo.ico"
    # Path relative to _MEIPASS root, needs .. from installer dir base
    source_rel_path = f"../assets/{icon_filename}"
    print_step(f"Deploying {icon_filename}...")
    try:
        # find_and_get_resource_path expects path relative to installer dir base
        source_abs_path = find_and_get_resource_path(source_rel_path)
        # Copy directly to the install root
        destination_path = Path(target_install_path) / icon_filename

        logger.info(f"Copying {icon_filename} from '{source_abs_path}' to '{destination_path}'...")
        shutil.copy2(source_abs_path, destination_path) # copy2 preserves metadata
        logger.info(f"Successfully copied {icon_filename}.")
        print_step(f"{icon_filename} deployed successfully.")

    except FileNotFoundError as fnf_error:
        logger.error(f"Error copying {icon_filename}: {fnf_error}", exc_info=True)
        print_failure(f"Could not find the bundled icon file '{icon_filename}' at expected path '{source_rel_path}'.")
    except Exception as e:
        logger.error(f"Unexpected error copying {icon_filename}: {e}", exc_info=True)
        print_failure(f"An unexpected error occurred while copying {icon_filename}: {e}")

# --- Main Execution --- 

def main(install_path: str):
    """Main logic for Stage 1 setup."""
    logger.info(f"Starting ANPE Environment Setup in {install_path}")

    # 1. Validate install path (Basic checks, more robust validation in GUI)
    print_step("Validating installation path permissions...")
    install_path_abs = Path(install_path).resolve() # Use Path object
    install_parent_dir = install_path_abs.parent

    try:
        # Ensure parent exists and we can create the target directory
        install_parent_dir.mkdir(parents=True, exist_ok=True)
        install_path_abs.mkdir(exist_ok=True)
        
        # Writability check
        test_file = install_path_abs / ".anpe_installer_write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
    except Exception as e:
        print_failure(f"Installation path is invalid or not writable: {install_path_abs}. Error: {e}")
    print_step("Installation path is valid and writable.")

    # 2. Unpack Python
    python_extract_path = unpack_python(str(install_path_abs))

    # 3. Find Python executable AND enable site-packages
    python_exe = find_python_executable(python_extract_path)
    enable_site_packages(python_extract_path)

    # 4. Bootstrap Pip
    bootstrap_pip(python_exe)

    # 5. Upgrade pip
    run_pip_install(python_exe, "--upgrade pip")

    # 6. Install packages from requirements file
    install_required_packages(python_exe, str(install_path_abs))

    # 7. Copy application code (anpe_gui source)
    copy_app_code(str(install_path_abs))

    # 8. Copy bundled executables (ANPE.exe, uninstall.exe)
    copy_bundled_executables(str(install_path_abs))

    # 9. Copy the application icon file
    copy_icon_file(str(install_path_abs))

    print_success("Environment setup complete.")

# --- Standalone Execution Guard ---
if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1]:
        logging.error("Usage: python installer_core.py <target_install_path>")
        print_failure("Usage: python installer_core.py <target_install_path>")

    target_install_path_arg = sys.argv[1]
    try:
        main(target_install_path_arg)
    except Exception as e:
        logging.critical(f"An unexpected error occurred during setup: {e}", exc_info=True)
        print_failure(f"An unexpected error occurred during setup: {e}")
