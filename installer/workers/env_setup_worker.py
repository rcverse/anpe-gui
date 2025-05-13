import sys
import platform
import os
import logging # Import logging
import traceback # Import traceback
from PyQt6.QtCore import QObject, pyqtSignal

# Use absolute import for utils and TaskStatus consistent with setup_windows.pyw
from installer.utils import get_resource_path
from installer.widgets.task_list_widget import TaskStatus

# Get logger instance (configured in utils.py)
logger = logging.getLogger()

class EnvironmentSetupWorker(QObject):
    """Worker object to handle Stage 1: Environment setup (Python unpack, pip install)."""

    # Signals
    log_update = pyqtSignal(str)          # Emits log messages
    status_update = pyqtSignal(str)       # Emits high-level status updates
    # Emits success (bool), python_exe_path (str | None), error_message (str)
    finished = pyqtSignal(bool, object, str)   # Added error message string
    # Signal for task status updates
    task_status_update = pyqtSignal(str, int)  # task_id, status

    def __init__(self, install_path: str, parent=None):
        """Initialize the worker."""
        super().__init__(parent)
        self._install_path = install_path
        self._python_exe_path = None # Store the found python path
        
        self._tasks = {
            "validate_path": "Validate installation path",
            "setup_python": "Set up Python environment", 
            "install_packages": "Install required packages",
            "copy_files": "Copy application files"
        }
        self._current_task = None
        self._completed_tasks = set()

    def run(self):
        """Execute the environment setup process by directly calling installer_core functions."""
        python_exe = None # Renamed for clarity within run method scope
        success = False
        error_message_str = "" # Initialize error message

        try:
            # Import necessary functions from installer_core
            # Using absolute import path based on current structure
            from installer.installer_core import (
                unpack_python, find_python_executable, enable_site_packages,
                bootstrap_pip, run_pip_install, copy_app_code, 
                copy_bundled_executables, copy_icon_file, install_required_packages # Added install_required_packages
            )

            # Set all tasks to pending initially
            for task_id in self._tasks:
                self.task_status_update.emit(task_id, TaskStatus.PENDING)

            # --- Stage 1: Validate Path (Simulated Step) ---
            self._current_task = "validate_path"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING) # Show as processing initially
            # Actual validation is done in GUI before starting worker
            self.status_update.emit("Validated installation path.")
            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED)
            self._completed_tasks.add(self._current_task)

            # --- Stage 2: Setup Python Environment ---
            self._current_task = "setup_python"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING)

            self.log_update.emit(f"Target installation path: {self._install_path}")

            # 2.1 Unpack Python
            self.status_update.emit("Unpacking Python environment...")
            python_dir = unpack_python(self._install_path)
            self.log_update.emit(f"Python unpacked to: {python_dir}")

            # 2.2 Find Python Executable
            self.status_update.emit("Locating Python executable...")
            python_exe = find_python_executable(python_dir) 
            self.log_update.emit(f"Found Python executable: {python_exe}")
            self._python_exe_path = python_exe # Store for finish signal

            # 2.3 Enable site-packages
            self.status_update.emit("Enabling site-packages...")
            enable_site_packages(python_dir)
            self.log_update.emit("site-packages enabled.")

            # 2.4 Bootstrap Pip
            self.status_update.emit("Installing pip...")
            bootstrap_pip(python_exe)
            self.log_update.emit("pip installed.")

            # 2.5 Upgrade Pip
            self.status_update.emit("Upgrading pip...")
            run_pip_install(python_exe, "--upgrade pip")
            self.log_update.emit("pip upgraded.")

            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED)
            self._completed_tasks.add(self._current_task)

            # --- Stage 3: Install Packages ---
            self._current_task = "install_packages"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING)
            self.status_update.emit("Installing required packages...")

            # Call the new function from installer_core to handle package installation
            install_required_packages(python_exe, self._install_path)
            self.log_update.emit("Required packages installed via installer_core.")

            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED)
            self._completed_tasks.add(self._current_task)

            # --- Stage 4: Copy Application Files ---
            self._current_task = "copy_files"
            self.task_status_update.emit(self._current_task, TaskStatus.PROCESSING)
            self.status_update.emit("Deploying application components...") # General status

            # 4.1 Copy application code
            self.status_update.emit("Copying application code...")
            copy_app_code(self._install_path) # Use the function from installer_core
            self.log_update.emit("Application code copied.")

            # 4.2 Copy bundled executables (ANPE Studio.exe, uninstall.exe)
            self.status_update.emit("Copying executables...")
            copy_bundled_executables(self._install_path) # Use the function from installer_core
            self.log_update.emit("Bundled executables copied.")

            # 4.3 Copy the application icon file
            self.status_update.emit("Copying application icon...")
            copy_icon_file(self._install_path) # <<< ADDED THIS CALL
            self.log_update.emit("Application icon copied.")

            self.task_status_update.emit(self._current_task, TaskStatus.COMPLETED)
            self._completed_tasks.add(self._current_task)

            # --- All Done --- 
            self.status_update.emit("Environment setup complete.")
            success = True

        except Exception as e:
            error_details = traceback.format_exc()
            error_message_str = str(e)
            log_msg = f"ERROR during environment setup: {error_message_str}\n{error_details}"
            self.log_update.emit(log_msg) # Emit detailed log
            logger.error(log_msg) # Also log it directly
            self.status_update.emit(f"Error during setup: {error_message_str}")
            if self._current_task:
                self.task_status_update.emit(self._current_task, TaskStatus.FAILED)
            success = False
            self._python_exe_path = None # Ensure path is None on failure

            # Mark subsequent tasks as failed
            task_ids = list(self._tasks.keys())
            try:
                current_index = task_ids.index(self._current_task)
                for task_id in task_ids[current_index + 1:]:
                     if task_id not in self._completed_tasks:
                        self.task_status_update.emit(task_id, TaskStatus.FAILED)
            except ValueError:
                # If current_task was None or not in list, mark all non-completed as failed
                 for task_id in task_ids:
                      if task_id not in self._completed_tasks:
                           self.task_status_update.emit(task_id, TaskStatus.FAILED)

        finally:
            # Emit the finished signal with success, path (or None), and error message (or "")
            logger.info(f"Emitting finished signal: success={success}, path={self._python_exe_path}, error='{error_message_str}'")
            self.finished.emit(success, self._python_exe_path, error_message_str)

    # --- Helper methods (no longer needed with direct calls) --- 
    # def _handle_stdout(self): ...
    # def _handle_stderr(self): ...
    # def _handle_process_error(self, error: QProcess.ProcessError): ...
    # def _handle_finish(self, exit_code: int, exit_status: QProcess.ExitStatus): ...
    # def _update_task_from_step(self, step_msg: str): ...

    def _set_task_status(self, task_id, status):
        """Set task status and track completion."""
        self.task_status_update.emit(task_id, status)
        self._current_task = task_id
        if status == TaskStatus.COMPLETED:
            self._completed_tasks.add(task_id)
        elif status == TaskStatus.FAILED:
            self._completed_tasks.discard(task_id)

    def _is_task_completed(self, task_id):
        """Check if a task is marked as completed."""
        return task_id in self._completed_tasks
