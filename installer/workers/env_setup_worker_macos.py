import sys
import platform
import os
import logging
import traceback
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QProcess

# Use absolute import for utils and TaskStatus
# REMOVED: from installer.utils import get_resource_path
from installer.widgets.task_list_widget import TaskStatus

# Import necessary functions from macOS-specific installer_core
# Updated imports for standalone python approach
from installer.installer_core_macos import (
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

    def run(self):
        """Execute the environment setup process. Runs in a separate thread."""
        logger.info("EnvironmentSetupWorkerMacOS thread started.")
        python_extract_base_dir = None
        python_exe = None

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

            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED, f"Set up {self._tasks[self._current_task]}")
            self._completed_tasks.add(self._current_task)

            # --- Stage 3: Install Packages (using QProcess) ---
            self._current_task = "install_packages"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING, f"Installing {self._tasks[self._current_task]}...")
            self.status_update.emit("Installing required packages...")

            # 3.2 Install required packages via QProcess
            reqs_filename = "macos_requirements.txt"
            reqs_path_obj = _get_bundled_resource_path_macos(reqs_filename)
            if not reqs_path_obj or not reqs_path_obj.is_file():
                 raise FileNotFoundError(f"Requirements file not found using resource finder: {reqs_filename}")
            reqs_path = str(reqs_path_obj.resolve())
            
            self.status_update.emit(f"Installing required application dependencies...")

            self._pip_process = QProcess()
            self._pip_process.readyReadStandardOutput.connect(self._handle_pip_stdout)
            self._pip_process.readyReadStandardError.connect(self._handle_pip_stderr)
            self._pip_process.finished.connect(self._handle_pip_finished) # Connect to new slot

            command_args = ["-m", "pip", "install", "--no-cache-dir", "-r", reqs_path]

            self.log_update.emit(f"Starting pip install process: {python_exe} {' '.join(command_args)}")
            self._pip_error_occurred = False # Reset flag
            self._pip_stderr_buffer = "" # Reset buffer
            self._pip_process.start(python_exe, command_args)

            # NOTE: The 'run' method will now exit, but the worker object persists.
            # The final 'finished' signal for the *worker* will be emitted
            # from the '_handle_pip_finished' slot.

        except Exception as e:
            logger.exception(f"Error during environment setup: {e}")
            # Comment out progress signals for indeterminate bar
            # self.progress_range_updated.emit(0, 1)
            # self.progress_updated.emit(1)
            self.task_status_update.emit("env_setup", TaskStatus.FAILED, f"Error: {e}")
            self.status_update.emit(f"Environment setup failed: {e}")
            # Handle errors occurring *before* pip process starts
            self._handle_error(e)

    def _handle_pip_stdout(self):
        """Handle stdout data from the pip process."""
        if not self._pip_process: return
        try:
            data = self._pip_process.readAllStandardOutput().data().decode(errors='replace').strip()
            if data:
                for line in data.splitlines():
                    if line.strip():
                        self.log_update.emit(line.strip())
        except Exception as e:
            logger.error(f"Error processing pip stdout: {e}")

    def _handle_pip_stderr(self):
        """Handle stderr data from the pip process."""
        if not self._pip_process: return
        try:
            data = self._pip_process.readAllStandardError().data().decode(errors='replace').strip()
            if data:
                # Only flag as error if stderr contains actual error indicators, not just notices
                is_real_error = False
                log_lines = []
                for line in data.splitlines():
                    line_strip = line.strip()
                    if line_strip:
                        log_line = f"PIP_STDERR: {line_strip}" # Log all stderr for debugging
                        log_lines.append(log_line)
                        self._pip_stderr_buffer += log_line + "\\n" # Store all stderr
                        # Check for common error patterns, ignore '[notice]'
                        if '[notice]' not in line_strip.lower() and any(err_kw in line_strip.lower() for err_kw in ['error', 'failed', 'traceback', 'exception']): 
                            is_real_error = True
                
                if is_real_error:
                    self._pip_error_occurred = True # Mark that a significant error happened
                
                # Emit all captured stderr lines to the log regardless of error status
                for log_line in log_lines:
                     self.log_update.emit(log_line) 

        except Exception as e:
            logger.error(f"Error processing pip stderr: {e}")

    def _handle_pip_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle the QProcess finished signal for pip install."""
        logger.info(f"pip process finished. ExitCode: {exit_code}, ExitStatus: {exit_status}, ErrorOccurred: {self._pip_error_occurred}")
        self._pip_process = None # Clear the process reference

        success = False
        error_message_str = ""

        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0 and not self._pip_error_occurred:
            self.log_update.emit("Installed dependencies successfully.")
            self.task_status_update.emit("install_packages", TaskStatus.COMPLETED, f"Installed {self._tasks['install_packages']}")
            self._completed_tasks.add("install_packages")
            # self.progress_updated.emit(100)
            self.status_update.emit("Environment setup complete.")
            success = True
            self.setup_complete.emit() # Emit success signal
        else:
            # Failure case
            if self._current_task == "install_packages":
                 self.task_status_update.emit(self._current_task, TaskStatus.FAILED, f"Failed: {self._tasks[self._current_task]}")
            error_message_str = f"pip install failed. ExitCode: {exit_code}, ExitStatus: {exit_status}."
            if self._pip_stderr_buffer:
                error_message_str += f"\\n--- Pip Errors ---\\n{self._pip_stderr_buffer.strip()}"

            self.status_update.emit(f"Error during dependency installation.")
            self.log_update.emit(f"ERROR: {error_message_str}")
            logger.error(error_message_str)
            success = False
            self._python_exe_path = None # Ensure path is None on failure
            self.setup_failed.emit(error_message_str) # Emit failure signal

        # Emit the main finished signal for the worker
        logger.info(f"Emitting finished signal: success={success}, error='{error_message_str}', python_exe={self._python_exe_path}")
        self.finished.emit(success, error_message_str, self._python_exe_path)
        logger.info("EnvironmentSetupWorkerMacOS thread finished processing pip result.")

    def _handle_error(self, e: Exception):
        """Handle exceptions occurring during setup (before or after pip process)."""
        error_details = traceback.format_exc()
        error_message_str = str(e)
        log_msg = f"ERROR during environment setup: {error_message_str}\\n{error_details}"
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
        except ValueError:
            for task_id in task_ids:
                if task_id not in self._completed_tasks:
                    self.task_status_update.emit(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]}")

        self._python_exe_path = None # Ensure path is None on failure
        self.setup_failed.emit(error_message_str) # Emit failure signal

        # Emit the main finished signal
        logger.info(f"Emitting finished signal due to error: success=False, error='{error_message_str}', python_exe=None")
        # Ensure _pip_process is cleaned up if error happened before it finished
        if self._pip_process and self._pip_process.state() != QProcess.ProcessState.NotRunning:
             logger.warning("Terminating pip process due to earlier setup error.")
             self._pip_process.terminate()
             self._pip_process.waitForFinished(1000)
        self._pip_process = None
        self.finished.emit(False, error_message_str, None)
        logger.info("EnvironmentSetupWorkerMacOS thread finished due to error.")

    # Method to be called by SetupWizard if cancellation occurs
    def request_stop(self):
         logger.info("Stop requested for EnvironmentSetupWorkerMacOS")
         if self._pip_process and self._pip_process.state() != QProcess.ProcessState.NotRunning:
              logger.warning("Attempting to terminate pip process due to cancellation.")
              self._pip_process.terminate() # Terminate the QProcess
              # Optionally wait a very short time, but avoid blocking the main thread here
              # self._pip_process.waitForFinished(500) 
         # No need to explicitly stop the thread here, _stop_threads handles that

# Note: We don't define start() here anymore. The calling code (SetupWizard)
# will be responsible for creating the QThread and starting it. 