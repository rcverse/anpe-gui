import sys
import platform
import os
import re
import logging
from typing import Dict, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QProcess
import time

try:
    from ..utils import get_resource_path
    from ..widgets.task_list_widget import TaskStatus  # Import existing TaskStatus
except ImportError:
    pass  # Not critical if we can't import this

logger = logging.getLogger(__name__)

class ModelSetupWorker(QObject):
    """Worker for handling language model setup process."""

    # Signal definitions
    log_update = pyqtSignal(str)  # For detailed logs
    status_update = pyqtSignal(str)  # For user-friendly status updates
    task_status_update = pyqtSignal(str, int)  # task_id, status
    finished = pyqtSignal(bool)  # Success/failure signal

    def __init__(self, python_exe_path: str, is_upgrade: bool = False, parent=None):
        """Initialize the worker.

        Args:
            python_exe_path: The path to the Python executable to use.
            is_upgrade: Whether this is an upgrade. If True, skips model download.
            parent: The parent QObject.
        """
        super().__init__(parent)
        self._python_exe_path = python_exe_path
        self._is_upgrade = is_upgrade
        self._process = None
        self._current_task = None
        self._completed_tasks = set()
        self._processing_tasks = set()  # Track tasks in PROCESSING state
        self._needs_action_tasks = set()  # Track tasks needing action

        # Define tasks to match the actual process in setup_models.py
        self._tasks = {
            "check_models": "Checking model presence",
            "install_spacy": "Installing spaCy model",
            "install_benepar": "Installing Benepar model",
        }

        # Task phase mapping to detect which task is active based on log messages
        self._phase_patterns = {
            "check_models": [
                "checking spacy model", "checking benepar model",
                "check_spacy_model", "check_benepar_model",
                "checking for presence", "starting model setup"
            ],
            "install_spacy": [
                "spacy model not found", "downloading spacy model", "install_spacy_model",
                "installing spacy", "en_core_web_md"
            ],
            "install_benepar": [
                "benepar model not found", "download benepar", "install_benepar_model",
                "benepar_en3", "berkeley neural parser", "constituency parsing"
            ],
        }

    def run(self):
        """Run the model setup process."""
        # For upgrades, skip model installation but keep display for 3 seconds
        if self._is_upgrade:
            upgrade_msg = "Upgrade detected - skipping model installation"
            self.log_update.emit(upgrade_msg)
            logger.info(upgrade_msg)
            
            self.status_update.emit("Skipping model installation for upgrade")
            
            # Mark all tasks as completed immediately
            for task_id in self._tasks:
                self.task_status_update.emit(task_id, TaskStatus.COMPLETED)
                self._completed_tasks.add(task_id)
                
            reuse_msg = "Using existing language models from previous installation"
            self.log_update.emit(reuse_msg)
            logger.info(reuse_msg)
            
            self.status_update.emit("Using existing language models")
            logger.info("Model setup skipped for upgrade - successfully completed")
            
            # Add a delay to give users time to see the success
            self.log_update.emit("Pausing for status review...")
            time.sleep(3)  # 3 second pause
            self.log_update.emit("Continuing with installation...")
            
            self.finished.emit(True)
            return
            
        if not self._python_exe_path or not os.path.isfile(self._python_exe_path):
            error_msg = f"Error: Invalid Python executable: {self._python_exe_path}"
            self.log_update.emit(error_msg)
            logger.error(error_msg)
            self.status_update.emit("Error: Cannot start setup - invalid Python path")
            
            # Mark all tasks as failed
            for task_id in self._tasks:
                self.task_status_update.emit(task_id, TaskStatus.FAILED)
                
            self.finished.emit(False)
            return

        # Initialize tasks as pending
        for task_id in self._tasks:
            self.task_status_update.emit(task_id, TaskStatus.PENDING)

        # Log initial status
        self.log_update.emit(f"Starting model setup with Python: {self._python_exe_path}")
        self.status_update.emit("Starting language model check...")
        
        # Start with the check_models task
        self._set_task_status("check_models", TaskStatus.PROCESSING)
        
        # Set up the process
        self._setup_process()
        
        # Run the setup_models.py script
        module_to_run = "anpe.utils.setup_models"
        command = [self._python_exe_path, "-m", module_to_run]
        
        try:
            self._process.start(command[0], command[1:])
        except Exception as e:
            self.log_update.emit(f"CRITICAL ERROR: Failed to start model setup: {e}")
            self.status_update.emit("Error: Failed to launch model setup script")
            
            # Mark all tasks as failed
            for task_id in self._tasks:
                self.task_status_update.emit(task_id, TaskStatus.FAILED)
                
            self.finished.emit(False)

    def _setup_process(self):
        """Set up the QProcess and connect signals."""
        self._process = QProcess()
        self._process.readyReadStandardOutput.connect(self._handle_stdout)
        self._process.readyReadStandardError.connect(self._handle_stderr)
        self._process.errorOccurred.connect(self._handle_process_error)
        self._process.finished.connect(self._handle_finish)

    def _handle_stdout(self):
        """Process standard output from the script."""
        try:
            data = self._process.readAllStandardOutput().data().decode(errors='replace').strip()
            if not data:
                return
                
            # Log the raw output
            self.log_update.emit(data)
            
            # Process line by line
            for line in data.splitlines():
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Check which task this line corresponds to
                self._update_task_status_from_line(line)
                
                # Send a clean status message
                clean_status = self._clean_status_message(line)
                if clean_status:
                    self.status_update.emit(clean_status)
            
        except Exception as e:
            self.log_update.emit(f"Error processing stdout: {e}")

    def _update_task_status_from_line(self, line: str):
        """Update the active task based on log line content."""
        line_lower = line.strip().lower()
        
        # Check if we need to install models
        if "one or more models are missing" in line_lower:
            # Mark check_models as completed
            self._set_task_status("check_models", TaskStatus.COMPLETED)
            self.status_update.emit("Some models need installation")
            
            # Use NEEDS_ACTION for models that need to be installed
            if "spacy model not found" in line_lower or "installing spacy" in line_lower:
                # Use NEEDS_ACTION instead of PROCESSING for initial detection
                self._set_task_status("install_spacy", TaskStatus.NEEDS_ACTION)
                self.status_update.emit("SpaCy model requires installation")
            
            if "benepar model not found" in line_lower or "installing benepar" in line_lower:
                # Use NEEDS_ACTION instead of PROCESSING for initial detection
                self._set_task_status("install_benepar", TaskStatus.NEEDS_ACTION)
                self.status_update.emit("Benepar model requires installation")
            
            return
            
        # Handle model check results - broader pattern matching for specific model checks
        if any(pattern in line_lower for pattern in ["checking spacy", "spacy model", "en_core_web"]):
            if "install_spacy" not in self._processing_tasks and "install_spacy" not in self._completed_tasks:
                self._set_task_status("install_spacy", TaskStatus.PROCESSING)
                self.status_update.emit("Checking SpaCy model...")
        
        if any(pattern in line_lower for pattern in ["checking benepar", "benepar model", "benepar_en"]):
            if "install_benepar" not in self._processing_tasks and "install_benepar" not in self._completed_tasks:
                self._set_task_status("install_benepar", TaskStatus.PROCESSING)
                self.status_update.emit("Checking Benepar model...")
            
        # Handle model presence detection
        if any(pattern in line_lower for pattern in ["spacy model is already present", "using existing spacy model"]):
            self._set_task_status("install_spacy", TaskStatus.COMPLETED)
            self.status_update.emit("SpaCy model is already installed")
            self.log_update.emit("SpaCy model found. Installation not required.")
            
        elif any(pattern in line_lower for pattern in ["benepar model is already present", "using existing benepar model"]):
            self._set_task_status("install_benepar", TaskStatus.COMPLETED)
            self.status_update.emit("Benepar model is already installed")
            self.log_update.emit("Benepar model found. Installation not required.")
            
        # Model not found triggers - expanded pattern matching
        elif any(pattern in line_lower for pattern in [
            "spacy model not found", "need to download spacy", "missing spacy", "spacy model installation"
        ]):
            # If already in NEEDS_ACTION state and actual download begins, set to PROCESSING
            if "install_spacy" in self._needs_action_tasks:
                self._set_task_status("install_spacy", TaskStatus.PROCESSING)
            else:
                self._set_task_status("install_spacy", TaskStatus.NEEDS_ACTION)
            self.status_update.emit("SpaCy model needs to be downloaded")
        
        elif any(pattern in line_lower for pattern in [
            "benepar model not found", "need to download benepar", "missing benepar", "benepar model installation"
        ]):
            # If already in NEEDS_ACTION state and actual download begins, set to PROCESSING
            if "install_benepar" in self._needs_action_tasks:
                self._set_task_status("install_benepar", TaskStatus.PROCESSING)
            else:
                self._set_task_status("install_benepar", TaskStatus.NEEDS_ACTION)
            self.status_update.emit("Benepar model needs to be downloaded")
            
        # Handle model download - expanded pattern matching - clear transition to PROCESSING
        if any(pattern in line_lower for pattern in [
            "downloading spacy", "install spacy", "installing spacy", "download spacy", "en_core_web"
        ]):
            # When download actually starts, transition from NEEDS_ACTION to PROCESSING
            self._set_task_status("install_spacy", TaskStatus.PROCESSING)
            self.status_update.emit("Downloading SpaCy (text processing) model...")
            
        elif any(pattern in line_lower for pattern in [
            "downloading benepar", "install benepar", "installing benepar", "download benepar", "benepar_en"
        ]):
            # When download actually starts, transition from NEEDS_ACTION to PROCESSING
            self._set_task_status("install_benepar", TaskStatus.PROCESSING)
            self.status_update.emit("Downloading Benepar (parsing) model...")
            
        # Check for error messages first - with broader pattern matching
        if any(err in line_lower for err in ["error", "failed", "exception", "critical"]):
            if any(model in line_lower for model in ["spacy", "en_core_web"]) and "install_spacy" in self._tasks:
                self._set_task_status("install_spacy", TaskStatus.FAILED)
            elif any(model in line_lower for model in ["benepar", "benepar_en"]) and "install_benepar" in self._tasks:
                self._set_task_status("install_benepar", TaskStatus.FAILED)
            elif self._current_task:
                # Default fallback if we can't identify the specific model
                self._set_task_status(self._current_task, TaskStatus.FAILED)
            return
            
        # Check for successful installation messages - with broader pattern matching
        if any(pattern in line_lower for pattern in [
            "successfully downloaded spacy", "spacy model installed", "successfully installed spacy"
        ]):
            self._set_task_status("install_spacy", TaskStatus.COMPLETED)
            self.status_update.emit("SpaCy model installed successfully")
            
        elif any(pattern in line_lower for pattern in [
            "successfully downloaded benepar", "benepar model installed", "successfully installed benepar"
        ]):
            self._set_task_status("install_benepar", TaskStatus.COMPLETED)
            self.status_update.emit("Benepar model installed successfully")
            
        # Check for overall completion
        if any(pattern in line_lower for pattern in [
            "model setup process completed", "all models installed", "setup complete"
        ]):
            # Complete any remaining tasks
            for task_id in self._tasks:
                if task_id not in self._completed_tasks:
                    self._set_task_status(task_id, TaskStatus.COMPLETED)
            self.status_update.emit("All language models installed successfully")

    def _clean_status_message(self, message: str) -> str:
        """Clean up log messages to be more user-friendly.
        
        Args:
            message: The raw log message
            
        Returns:
            A cleaned user-friendly message
        """
        # Remove timestamp pattern (2023-04-15 14:49:50,246)
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}'
        
        # Remove log level and module patterns
        log_pattern = r'(- anpe\.setup_models)? - (INFO|DEBUG|WARNING|ERROR|CRITICAL) - '
        
        # Combine patterns
        full_pattern = rf'({timestamp_pattern})?\s*{log_pattern}?'
        
        # Remove patterns
        cleaned = re.sub(full_pattern, '', message)
        
        # Replace technical terms with user-friendly ones
        replacements = {
            r'en_core_web_md': 'English language model',
            r'Downloading spaCy model: en_core_web_md': 'Downloading English language model',
            r'spaCy': 'spaCy (text processing)',
            r'Benepar': 'Benepar (parsing)',
            r'benepar_en3': 'English parsing model'
        }
        
        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        
        # Remove double spaces and trim
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        
        # Capitalize first letter if needed
        if cleaned and not cleaned[0].isupper():
            cleaned = cleaned[0].upper() + cleaned[1:]
            
        return cleaned

    def _set_task_status(self, task_id: str, status: int):
        """Set task status and track state.
        
        Args:
            task_id: The identifier of the task
            status: The status code (from TaskStatus enum)
        """
        if task_id not in self._tasks:
            return
        
        # Don't change status if already completed (avoid regressing)
        if task_id in self._completed_tasks and status in [TaskStatus.PROCESSING, TaskStatus.NEEDS_ACTION]:
            return
            
        # Update task status through signal
        self.task_status_update.emit(task_id, status)
        
        # Track current task and various status sets
        if status == TaskStatus.PROCESSING:
            self._current_task = task_id
            self._processing_tasks.add(task_id)
            self._needs_action_tasks.discard(task_id)  # Remove from needs_action when processing
            
            # Update status message when changing tasks
            task_name = self._tasks[task_id]
            if task_id == "check_models":
                self.status_update.emit("Checking for language models...")
            elif task_id == "install_spacy":
                self.status_update.emit("Processing spaCy model...")
            elif task_id == "install_benepar":
                self.status_update.emit("Processing Benepar model...")
            
        # Track needs action tasks
        elif status == TaskStatus.NEEDS_ACTION:
            self._needs_action_tasks.add(task_id)
            self._processing_tasks.discard(task_id)
            
            # Update status message for tasks needing action
            if task_id == "install_spacy":
                self.status_update.emit("SpaCy model requires installation")
            elif task_id == "install_benepar":
                self.status_update.emit("Benepar model requires installation")
            
        # Track completed tasks
        elif status == TaskStatus.COMPLETED:
            self._completed_tasks.add(task_id)
            self._processing_tasks.discard(task_id)
            self._needs_action_tasks.discard(task_id)
            
            # Update status message for completed tasks
            if task_id == "check_models":
                self.status_update.emit("Language model check completed.")
            elif task_id == "install_spacy":
                self.status_update.emit("SpaCy model installed successfully.")
            elif task_id == "install_benepar":
                self.status_update.emit("Benepar model installed successfully.")
                
        elif status == TaskStatus.FAILED:
            self._completed_tasks.discard(task_id)
            self._processing_tasks.discard(task_id)
            self._needs_action_tasks.discard(task_id)
            
            # Update status message for failed tasks
            if task_id == "check_models":
                # Don't report as error for model check, since missing models isn't an error
                self.status_update.emit("Language models need to be downloaded.")
            else:
                # For other tasks, report failure
                self.status_update.emit(f"Error in {self._tasks[task_id].lower()}.")

    def _handle_stderr(self):
        """Process error output from the script."""
        try:
            data = self._process.readAllStandardError().data().decode(errors='replace').strip()
            if not data:
                return
                
            # Log the error
            self.log_update.emit(f"ERROR: {data}")
            
            # Check for error indication in the current task
            if self._current_task:
                self._set_task_status(self._current_task, TaskStatus.FAILED)
                
        except Exception as e:
            self.log_update.emit(f"Error processing stderr: {e}")

    def _handle_process_error(self, error: QProcess.ProcessError):
        """Handle QProcess errors."""
        error_string = self._process.errorString()
        self.log_update.emit(f"PROCESS ERROR ({error}): {error_string}")
        self.status_update.emit(f"Error launching model setup: {error_string}")
        
        # Mark all tasks as failed
        for task_id in self._tasks:
            self.task_status_update.emit(task_id, TaskStatus.FAILED)
            
        self.finished.emit(False)

    def _handle_finish(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion."""
        # Process any remaining output
        self._handle_stdout()
        self._handle_stderr()
        
        # Log completion
        self.log_update.emit(f"Model setup process finished. Exit code: {exit_code}")
        
        if exit_status == QProcess.ExitStatus.CrashExit:
            self.log_update.emit("ERROR: Model setup process crashed")
            self.status_update.emit("Error: Model setup process crashed unexpectedly")
            
            # Mark remaining tasks as failed
            for task_id in self._tasks:
                if task_id not in self._completed_tasks:
                    self.task_status_update.emit(task_id, TaskStatus.FAILED)
                    
            self.finished.emit(False)
        elif exit_code == 0:
            self.log_update.emit("Model setup completed successfully")
            self.status_update.emit("All language models installed successfully")
            
            # Mark all remaining tasks as complete
            for task_id in self._tasks:
                if task_id not in self._completed_tasks:
                    self.task_status_update.emit(task_id, TaskStatus.COMPLETED)
                    
            self.finished.emit(True)
        else:
            self.log_update.emit(f"ERROR: Model setup failed with exit code {exit_code}")
            self.status_update.emit("Error: Model setup failed. Check logs for details")
            
            # Mark remaining tasks as failed
            for task_id in self._tasks:
                if task_id not in self._completed_tasks:
                    self.task_status_update.emit(task_id, TaskStatus.FAILED)
                    
            self.finished.emit(False)
            
        # Clear the process
        self._process = None
