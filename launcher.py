import sys
import os
import subprocess
import time
import logging
import ctypes
from pathlib import Path

# --- Configuration ---
APP_NAME = "ANPE GUI"
APP_RUN_SCRIPT = "anpe_gui/run.py" # Relative to install root
PYTHON_DIR_NAME = "python" # Directory containing pythonw.exe
PYTHON_EXECUTABLE = "pythonw.exe" # Windowed executable
LAUNCHER_LOG_FILE = "launcher_debug.log"
STARTUP_TIMEOUT_SECONDS = 7 # How long to wait for initial stability

def get_install_dir() -> Path | None:
    """Determine the installation directory.
    
    Assumes the launcher (.exe) is placed in the root of the installation directory.
    Handles running from source vs. frozen executable.
    """
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        return Path(sys.executable).parent
    else:
        # Running as a script (development/testing) - assume script is in root
        return Path(__file__).parent

def setup_logging(log_path: Path):
    """Set up basic file logging for the launcher."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=log_path,
        filemode='w' # Overwrite log each time
    )
    logging.info(f"--- {APP_NAME} Launcher Started ---")
    logging.info(f"Launcher executable: {sys.executable}")
    logging.info(f"Working directory: {Path.cwd()}")

def show_error_message(title: str, message: str):
    """Display a Windows message box."""
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 | 0x0) # MB_ICONERROR | MB_OK

def main():
    install_dir = get_install_dir()
    if not install_dir:
        show_error_message(f"{APP_NAME} Launch Error", "Could not determine the application installation directory.")
        sys.exit(1)
        
    log_file_path = install_dir / LAUNCHER_LOG_FILE
    setup_logging(log_file_path)
    logging.info(f"Determined install directory: {install_dir}")

    python_exe_path = install_dir / PYTHON_DIR_NAME / PYTHON_EXECUTABLE
    app_script_path = install_dir / APP_RUN_SCRIPT

    logging.info(f"Looking for Python executable at: {python_exe_path}")
    logging.info(f"Looking for application script at: {app_script_path}")

    if not python_exe_path.is_file():
        error_msg = f"Could not find the required Python executable: {python_exe_path}"
        logging.error(error_msg)
        show_error_message(f"{APP_NAME} Launch Error", error_msg)
        sys.exit(1)

    if not app_script_path.is_file():
        error_msg = f"Could not find the application script: {app_script_path}"
        logging.error(error_msg)
        show_error_message(f"{APP_NAME} Launch Error", error_msg)
        sys.exit(1)

    # --- Launch the application ---
    process = None
    try:
        command = [str(python_exe_path), str(app_script_path)]
        logging.info(f"Launching command: {' '.join(command)}")
        # Use CREATE_NO_WINDOW flag to prevent console flash with pythonw.exe
        # Capture stderr to check for early crashes
        process = subprocess.Popen(
            command,
            cwd=install_dir, # Run the script from the install directory
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE, # Capture stdout too, just in case
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW 
        )
        logging.info(f"Application process started (PID: {process.pid}). Monitoring for {STARTUP_TIMEOUT_SECONDS} seconds...")

        # --- Monitor for quick failure ---
        start_time = time.time()
        while time.time() - start_time < STARTUP_TIMEOUT_SECONDS:
            return_code = process.poll()
            if return_code is not None:
                # Process terminated early
                stderr_output = process.stderr.read()
                stdout_output = process.stdout.read() # Read stdout as well
                error_details = f"The application terminated unexpectedly shortly after launch (exit code: {return_code}).\n\n"
                if stderr_output:
                    error_details += f"Error Output:\n{stderr_output[:1000]}" # Limit length
                if stdout_output:
                     error_details += f"\nStandard Output:\n{stdout_output[:1000]}" # Limit length
                
                logging.error(f"Application process terminated early. Exit code: {return_code}")
                logging.error(f"Stderr: {stderr_output}")
                logging.error(f"Stdout: {stdout_output}") # Log stdout too
                show_error_message(f"{APP_NAME} Startup Error", error_details)
                sys.exit(return_code) # Exit launcher with the same code
            time.sleep(0.5) # Check every half second

        # --- Application seems stable, assume successful launch ---
        logging.info(f"Application running for {STARTUP_TIMEOUT_SECONDS} seconds. Assuming successful startup.")
        
        # Close log file handle before attempting deletion
        logging.shutdown() 
        
        # Try to delete the log file on successful startup
        try:
            if log_file_path.exists():
                log_file_path.unlink()
        except OSError as e:
            # Don't show an error if log deletion fails, just log it (if possible, but logging is shut down)
            # print(f"Warning: Could not delete launcher log file: {e}") # Cannot log here
            pass
            
        sys.exit(0) # Launcher exits successfully

    except FileNotFoundError:
        error_msg = f"Launch command failed. Ensure Python ({python_exe_path}) and script ({app_script_path}) exist."
        logging.exception("FileNotFoundError during launch.") # Log full traceback
        show_error_message(f"{APP_NAME} Launch Error", error_msg)
        sys.exit(1)
    except Exception as e:
        logging.exception("An unexpected error occurred during launch.") # Log full traceback
        error_msg = f"An unexpected error occurred while trying to launch {APP_NAME}:\n\n{str(e)}"
        show_error_message(f"{APP_NAME} Launch Error", error_msg)
        sys.exit(1)
    finally:
        # Ensure resources are cleaned up if something went very wrong
        if process and process.poll() is None:
             # If we exit due to an exception but the process is still running? Unlikely but possible.
             # We probably want to let it run, as the user might see it.
             pass 
        # Ensure logging is shut down even if deletion failed
        logging.shutdown() 

if __name__ == "__main__":
    main() 