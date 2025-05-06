import sys
import platform
import os
import logging
import traceback
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QProcess, QProcessEnvironment, QEventLoop

# Use absolute import for utils and TaskStatus
# CORRECTED IMPORT for TaskStatus
from installer_macos.widgets.task_list_widget_macos import TaskStatus

# Import necessary functions from macOS-specific installer_core
# Updated imports for standalone python approach
from installer_macos.installer_core_macos import (
    unpack_standalone_python_macos, # New unpack function
    find_standalone_python_executable_macos, # New helper
    bootstrap_pip_macos,
    _get_bundled_resource_path_macos # Import the correct resource finder
)

# Get logger instance
logger = logging.getLogger()

class EnvironmentSetupWorkerMacOS(QObject):
    """Worker object to handle environment setup for macOS (Python unpack, pip install)."""

    # Signals
    log_update = pyqtSignal(str)          # Emits log messages
    status_update = pyqtSignal(str)       # Emits high-level status updates
    # Emits success (bool), error_message (str), python_exe_path (str | None)
    finished = pyqtSignal(bool, str, object)
    # Signal for task status updates - ADDED status_text
    task_status_update = pyqtSignal(str, int, str)  # task_id, status_enum, status_text
    # Progress signals
    progress_update = pyqtSignal(int)     # Current progress value
    progress_range = pyqtSignal(int, int) # Min, max progress values
    # Setup signals
    setup_complete = pyqtSignal()         # Setup completed successfully
    setup_failed = pyqtSignal(str)        # Setup failed with error

    def __init__(self, install_path: str, parent=None):
        """Initialize the worker."""
        super().__init__(parent)
        self._install_path = install_path
        self._python_exe_path = None # Path to standalone python executable
        self._pip_process = None # QProcess for pip install
        self._pip_error_occurred = False # Flag for pip failure
        self._pip_stderr_buffer = "" # Store stderr from pip
        
        self._tasks = {
            "validate_path": "Validate installation path",
            "setup_python": "Set up Python environment", 
            "install_packages": "Install required packages",
        }
        self._current_task = None
        self._completed_tasks = set()

    @property
    def python_exe_path(self):
        """Return the standalone Python executable path found during setup."""
        return self._python_exe_path

    @property
    def install_path(self):
        """Return the installation path."""
        return self._install_path

    # <<< NEW HELPER METHOD for running pip commands synchronously >>>
    def _run_pip_command_sync(self, python_exe: str, pip_args: list[str]) -> tuple[bool, str, str]:
        """Runs a pip command synchronously using QProcess and returns success/output."""
        success = False
        stdout_str = ""
        stderr_str = ""
        process = QProcess()

        # --- Setup Environment (CLEANED) ---
        process_env = QProcessEnvironment.systemEnvironment()
        process_env.remove("PYTHONHOME")
        logger.info("Removed PYTHONHOME from pip QProcess environment.")

        python_exe_path_obj = Path(python_exe)
        # Derive version from the executable name (e.g., python3.11)
        if python_exe_path_obj.name.startswith("python3."):
            try:
                version_str = python_exe_path_obj.name.split('python')[1]
                major, minor = map(int, version_str.split('.')[:2])
                logger.debug(f"Derived version {major}.{minor} from executable name for QProcess env.")
            except Exception:
                logger.warning(f"Could not derive version from {python_exe_path_obj.name} for QProcess env, falling back to 3.11")
                major, minor = 3, 11
        else:
            logger.warning(f"Cannot parse version from {python_exe_path_obj.name} for QProcess env, assuming 3.11")
            major, minor = 3, 11
            
        standalone_python_lib_dir = python_exe_path_obj.parent.parent / "lib" / f"python{major}.{minor}"
        
        if standalone_python_lib_dir.is_dir():
            logger.info(f"Setting PYTHONPATH for pip QProcess EXCLUSIVELY to: {standalone_python_lib_dir}")
            process_env.insert("PYTHONPATH", str(standalone_python_lib_dir)) # Set ONLY this path
            logger.debug(f"Effective PYTHONPATH for pip QProcess: {process_env.value('PYTHONPATH')}")
        else:
            logger.error(f"Could not find standalone Python lib directory at {standalone_python_lib_dir} for QProcess. UNSETTING PYTHONPATH. pip install WILL likely fail.")
            process_env.remove("PYTHONPATH")

        process.setProcessEnvironment(process_env)
        # --- End Environment Setup ---

        command = [python_exe, "-m", "pip"] + pip_args
        log_cmd_str = ' '.join(command)
        self.log_update.emit(f"Running synchronous pip command: {log_cmd_str}")
        logger.info(f"Running synchronous pip command: {log_cmd_str}")

        try:
            process.start(command[0], command[1:])
            # Wait indefinitely for the process to finish.
            # A timeout could be added: process.waitForFinished(timeout_ms)
            if not process.waitForFinished(-1): 
                stderr_str = f"QProcess waitForFinished timed out for command: {log_cmd_str}"
                logger.error(stderr_str)
                success = False
            else:
                exit_code = process.exitCode()
                exit_status = process.exitStatus()
                stdout_bytes = process.readAllStandardOutput().data()
                stderr_bytes = process.readAllStandardError().data()
                stdout_str = stdout_bytes.decode(errors='replace').strip()
                stderr_str = stderr_bytes.decode(errors='replace').strip()

                log_combined = f"Sync pip command finished. ExitCode: {exit_code}, ExitStatus: {exit_status}\n" \
                               f"--- STDOUT ---\n{stdout_str}\n" \
                               f"--- STDERR ---\n{stderr_str}"
                logger.info(log_combined)
                # Emit stdout/stderr lines to UI log
                if stdout_str:
                     for line in stdout_str.splitlines(): self.log_update.emit(line)
                if stderr_str:
                     for line in stderr_str.splitlines(): self.log_update.emit(f"PIP_STDERR: {line}")

                if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
                    success = True
                else:
                    success = False
                    # Error details are in stderr_str already

        except Exception as e:
            logger.exception(f"Exception during _run_pip_command_sync for {log_cmd_str}: {e}")
            stderr_str = f"Exception running command: {e}"
            success = False
        finally:
             process.deleteLater() # Clean up QProcess object

        return success, stdout_str, stderr_str

    def run(self):
        """Execute the environment setup process. Now runs synchronously for pip installs."""
        logger.info("EnvironmentSetupWorkerMacOS thread started.")
        python_extract_base_dir = None
        python_exe = None
        overall_success = False
        final_error_message = ""

        try:
            # Comment out progress signals for indeterminate bar
            # self.progress_range_updated.emit(0, 1)
            # self.progress_updated.emit(0)

            # Set all tasks to pending initially
            for task_id, task_name in self._tasks.items():
                self.task_status_update.emit(task_id, TaskStatus.PENDING, task_name) # Emit base name

            # --- Stage 1: Validate Path (Simulated Step) ---
            self._current_task = "validate_path"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING, f"Validating {self._tasks[self._current_task]}...")
            self.status_update.emit("Validated installation path.")
            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED, f"Validated {self._tasks[self._current_task]}")
            self._completed_tasks.add(self._current_task)
            # self.progress_updated.emit(10)

            # --- Stage 2: Setup Python Environment ---
            self._current_task = "setup_python"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING, f"Setting up {self._tasks[self._current_task]}...")
            self.log_update.emit(f"Target installation path: {self._install_path}")

            # 2.1 Unpack Standalone Python
            self.status_update.emit("Unpacking Python environment...")
            # Call new unpack function
            python_extract_base_dir = unpack_standalone_python_macos(self._install_path)
            self.log_update.emit(f"Standalone Python unpacked to: {python_extract_base_dir}")
            # self.progress_updated.emit(25)  # 25% progress

            # 2.2 Find Standalone Python Executable
            self.status_update.emit("Locating Python executable...")
            # Call new helper function
            python_exe = find_standalone_python_executable_macos(python_extract_base_dir)
            self._python_exe_path = python_exe # Store for signal and property
            self.log_update.emit(f"Found Python executable: {python_exe}")
            # self.progress_updated.emit(30)

            # <<< ADDED: Bootstrap pip before trying to use it >>>
            self.status_update.emit("Ensuring pip is available...")
            self.log_update.emit("Running pip bootstrap check...")
            try:
                bootstrap_pip_macos(python_exe)
                self.log_update.emit("Pip bootstrap check completed.")
            except Exception as pip_bootstrap_error:
                # If bootstrapping fails, we cannot proceed with pip install
                self.log_update.emit(f"ERROR: Failed to bootstrap pip: {pip_bootstrap_error}")
                logger.error(f"Failed to bootstrap pip: {pip_bootstrap_error}", exc_info=True)
                raise RuntimeError(f"Failed to bootstrap pip: {pip_bootstrap_error}") from pip_bootstrap_error

            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED, f"Set up {self._tasks[self._current_task]}")
            self._completed_tasks.add(self._current_task)

            # --- Stage 3: Install Packages (using synchronous helper) ---
            self._current_task = "install_packages"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING, f"Installing {self._tasks[self._current_task]}...")
            self.status_update.emit("Installing required build tools...")
            
            # 3.1 Install Setuptools and Wheel first
            pip_args_build_tools = ["install", "--no-cache-dir", "setuptools", "wheel"]
            build_tools_success, _, build_tools_stderr = self._run_pip_command_sync(python_exe, pip_args_build_tools)
            if not build_tools_success:
                raise RuntimeError(f"Failed to install build tools (setuptools, wheel). Error: {build_tools_stderr}")
            self.log_update.emit("Successfully installed/updated setuptools and wheel.")

            # 3.2 Find requirements file
            self.status_update.emit("Locating requirements file...")
            reqs_filename = "macos_requirements.txt"
            # Pass only the filename to the updated resource finder
            reqs_path_obj = _get_bundled_resource_path_macos(reqs_filename) 
            if not reqs_path_obj or not reqs_path_obj.is_file():
                 # Use the filename in the error message
                 raise FileNotFoundError(f"Requirements file '{reqs_filename}' not found.")
            reqs_path = str(reqs_path_obj.resolve())
            self.log_update.emit(f"Found requirements file: {reqs_path}")
            
            # 3.3 Install from requirements file
            self.status_update.emit(f"Installing application dependencies from {reqs_filename}...")
            pip_args_reqs = ["install", "--no-cache-dir", "-r", reqs_path]
            reqs_success, _, reqs_stderr = self._run_pip_command_sync(python_exe, pip_args_reqs)
            if not reqs_success:
                 raise RuntimeError(f"Failed to install requirements from {reqs_filename}. Error: {reqs_stderr}")

            # If we reach here, all install steps succeeded
            self.log_update.emit("Installed dependencies successfully.")
            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED, f"Installed {self._tasks[self._current_task]}")
            self._completed_tasks.add(self._current_task)
            self.status_update.emit("Environment setup complete.")
            overall_success = True
            self.setup_complete.emit() # Emit success signal

        except Exception as e:
            logger.exception(f"Error during environment setup: {e}")
            # Comment out progress signals for indeterminate bar
            # self.progress_range_updated.emit(0, 1)
            # self.progress_updated.emit(1)
            # Corrected task ID to match _tasks dict keys
            failed_task_id = self._current_task if self._current_task else "validate_path" # Default if error is very early
            self.task_status_update.emit(failed_task_id, TaskStatus.FAILED, f"Error: {e}") 
            self.status_update.emit(f"Environment setup failed: {e}")
            # Handle errors occurring *before* pip process starts
            self._handle_error(e)
            overall_success = False
            self._python_exe_path = None # Ensure path is None on failure
            # NOTE: _handle_error now emits the final finished signal on error

        # Emit the final finished signal *only* if no exception occurred
        # (Error case is handled by _handle_error calling self.finished)
        if overall_success:
             logger.info(f"Emitting final finished signal: success=True, error='', python_exe={self._python_exe_path}")
             self.finished.emit(True, "", self._python_exe_path)
        
        logger.info("EnvironmentSetupWorkerMacOS thread finished.") # Log thread exit

    # Remove old QProcess slots - these are replaced by _run_pip_command_sync
    # def _handle_pip_stdout(self): ... REMOVED
    # def _handle_pip_stderr(self): ... REMOVED
    # def _handle_pip_finished(self, exit_code: int, exit_status: QProcess.ExitStatus): ... REMOVED

    # _handle_error method needs slight adjustment as it's now called for any exception
    def _handle_error(self, e: Exception):
        """Handle exceptions occurring during setup."""
        error_details = traceback.format_exc()
        error_message_str = str(e)
        log_msg = f"ERROR during environment setup: {error_message_str}\n{error_details}"
        self.log_update.emit(log_msg)
        logger.error(log_msg)
        self.status_update.emit(f"Error during setup: {error_message_str}")

        # Mark current and subsequent tasks as failed
        if self._current_task:
            self.task_status_update.emit(self._current_task, TaskStatus.FAILED, f"Failed: {self._tasks[self._current_task]}")
        task_ids = list(self._tasks.keys())
        try:
            current_index = task_ids.index(self._current_task) if self._current_task else -1
            for task_id in task_ids[current_index + 1:]:
                if task_id not in self._completed_tasks:
                    self.task_status_update.emit(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]}")
        except ValueError: # Handle if self._current_task was None
            for task_id in task_ids:
                if task_id not in self._completed_tasks:
                    self.task_status_update.emit(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]}")

        self._python_exe_path = None # Ensure path is None on failure
        self.setup_failed.emit(error_message_str) # Emit failure signal

        # Emit the main finished signal
        logger.info(f"Emitting finished signal due to error: success=False, error='{error_message_str}', python_exe=None")
        # No QProcess to clean up here anymore as _run_pip_command_sync does it
        self.finished.emit(False, error_message_str, None)
        # No need to log thread exit here, it happens in run()

    def request_stop(self):
        # Stop request might be harder to handle cleanly with synchronous calls.
        # For now, log it. A more robust implementation might need flags checked
        # between synchronous calls in run().
        logger.warning("Stop requested for EnvironmentSetupWorkerMacOS, but synchronous operations may block immediate stop.")
        # We can't easily terminate the blocked QProcess from here in the sync helper case.

# Note: We don't define start() here anymore. The calling code (SetupWizard)
# will be responsible for creating the QThread and starting it. 