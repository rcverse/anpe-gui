import sys
import os
import re
import logging
from typing import Optional
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QProcess, QProcessEnvironment, QThread

from installer.widgets.task_list_widget import TaskStatus

# Get logger instance
logger = logging.getLogger()

class ModelSetupWorkerMacOS(QObject):
    """Worker for handling language model setup using anpe.utils.setup_models."""

    # Signals
    log_update = pyqtSignal(str)          # Emits log messages
    status_update = pyqtSignal(str)       # Emits high-level status updates
    # Emits success (bool), error_message (str)
    finished = pyqtSignal(bool, str)
    # Signal for task status updates
    task_status_update = pyqtSignal(str, int, str)  # task_id, status_enum, status_text
    # Progress signals
    progress_update = pyqtSignal(int)     # Current progress value
    progress_range = pyqtSignal(int, int) # Min, max progress values
    # Setup signals
    setup_complete = pyqtSignal()         # Setup completed successfully
    setup_failed = pyqtSignal(str)        # Setup failed with error

    def __init__(self, python_exe_path: str, parent=None):
        """Initialize the worker.

        Args:
            python_exe_path: The path to the standalone Python executable.
            parent: The parent QObject.
        """
        super().__init__(parent)
        self._python_exe_path = python_exe_path # Store the provided path
        self._process = None
        self._current_task_id = None # Keep track of overall phase (spacy/benepar)
        self._active_task_id = None # Specific task ID for status updates (spacy_model/benepar_model)
        self._completed_tasks = set() # Tracks completed task IDs
        self._error_message = "" # Store last significant error
        
        # Define SIMPLIFIED tasks 
        self._tasks = {
            "check_models": "Check Models",    # Single check task
            "install_models": "Install Models",  # Single install task
        }

        # Task phase mapping - map relevant keywords to simplified tasks
        self._phase_patterns = {
            "check_models": [
                "checking spacy model", 
                "checking benepar model",
                "already present", # If found during check
            ],
            "install_models": [
                "not found. attempting download",
                "downloading spacy model", 
                "downloading benepar model", 
                "installing spacy", 
                "installing benepar", 
                "install_spacy_model", 
                "install_benepar_model", 
                "en_core_web_", # Part of spacy download
                "benepar_en",   # Part of benepar download
                "successfully downloaded and verified"
            ],
        }
        
        # Verify the python executable path exists
        if not self._python_exe_path or not os.path.isfile(self._python_exe_path):
             logger.error(f"Standalone Python executable not found or invalid at: {self._python_exe_path}")
             self.status_update.emit("ERROR: Standalone Python executable not found.")
             raise FileNotFoundError(f"Standalone Python executable not found at: {self._python_exe_path}")

    def run(self):
        """Run the anpe.utils.setup_models script. Runs in a separate thread."""
        logger.info("ModelSetupWorkerMacOS thread started.")
        # Initialize tasks as pending
        for task_id in self._tasks:
            self.task_status_update.emit(task_id, TaskStatus.PENDING, self._tasks[task_id]) # Emit base name

        self.log_update.emit(f"Starting model setup using standalone Python")
        self.status_update.emit("Starting language model check...")

        # Start with the check phase
        self._active_task_id = "check_models"
        self._set_task_status(self._active_task_id, TaskStatus.PROCESSING, "Checking language models...")

        # Setup QProcess (No env setup needed anymore)
        self._setup_process()
        # if not self._setup_process():
            # _setup_process now returns False if env setup fails
            # Error messages are emitted within _setup_process
            # self._mark_all_tasks_failed()
            # Use the stored error message from _setup_process if available
            # self.finished.emit(False, self._error_message or "Failed to configure process environment.")
            # return

        # Command uses the provided standalone python executable
        python_executable = self._python_exe_path
        module_to_run = "anpe.utils.setup_models"
        command_args = ["-m", module_to_run] # Args for QProcess.start

        try:
            self.log_update.emit(f"Executing command: {python_executable} {' '.join(command_args)}")
            # Pass executable and arguments separately
            self._process.start(python_executable, command_args)
        except Exception as e:
            self._error_message = f"Failed to start model setup process: {e}"
            self.log_update.emit(f"CRITICAL ERROR: {self._error_message}")
            self.status_update.emit("Error: Failed to launch model setup script.")
            self._mark_all_tasks_failed()
            self.finished.emit(False, self._error_message)

    def _setup_process(self):
        """Set up the QProcess and connect signals. No environment setup needed.
        Returns True (always, as env setup removed).
        """
        self._process = QProcess()

        # --- Connect Signals --- 
        self._process.readyReadStandardOutput.connect(self._handle_stdout)
        self._process.readyReadStandardError.connect(self._handle_stderr)
        self._process.errorOccurred.connect(self._handle_process_error)
        self._process.finished.connect(self._handle_finish)

        return True # Indicate success

    def _handle_stdout(self):
        """Process standard output from the script."""
        if not self._process: return
        try:
            data = self._process.readAllStandardOutput().data().decode(errors='replace').strip()
            if not data: return

            # Log the raw output first
            self.log_update.emit(data)

            # Process line by line for status updates
            for line in data.splitlines():
                if not line.strip(): continue
                self._update_task_status_from_line(line)
                clean_status = self._clean_status_message(line)
                if clean_status:
                    self.status_update.emit(clean_status)

        except Exception as e:
            self.log_update.emit(f"Error processing stdout: {e}")
            logger.error("Error processing stdout: {e}", exc_info=True)

    def _update_task_status_from_line(self, line: str):
        """Update simplified task status based on log line content."""
        line_lower = line.strip().lower()
        if not line_lower: return

        # Determine if this line relates to checking or installing
        current_phase = None
        if any(p in line_lower for p in self._phase_patterns["check_models"]):
            current_phase = "check_models"
        elif any(p in line_lower for p in self._phase_patterns["install_models"]):
            current_phase = "install_models"
        
        if not current_phase:
             return # Ignore lines not matching known phases

        # If moving from checking to installing
        if self._active_task_id == "check_models" and current_phase == "install_models":
            self._set_task_status("check_models", TaskStatus.COMPLETED, "Checked language models.")
            self._active_task_id = "install_models"
            self._set_task_status(self._active_task_id, TaskStatus.PROCESSING, "Installing missing models...")
        
        # Handle specific outcomes within the current phase
        task_id = self._active_task_id
        if task_id:
            # Update status based on parsed line
            status_text = "" # Start with empty, determine based on line
            task_status = TaskStatus.PROCESSING # Default to processing

            # Determine status text and enum based on log content

            # Errors
            if any(err in line_lower for err in ["error:", " failed", "exception", "critical"]):
                failed_text = f"Failed: {self._tasks[task_id]}"
                self._set_task_status(task_id, TaskStatus.FAILED, failed_text)
                self._error_message = f"Failed during model setup: {line}"
                # Mark the other task as failed too if one fails
                other_task = "install_models" if task_id == "check_models" else "check_models"
                if other_task not in self._completed_tasks:
                     self._set_task_status(other_task, TaskStatus.FAILED, f"Failed: {self._tasks[other_task]}")
                return 

            # Successful completion of installation
            if "successfully downloaded and verified" in line_lower or "model setup process completed successfully" in line_lower:
                 # Mark both as completed if the process finishes
                 if "check_models" not in self._completed_tasks:
                      self._set_task_status("check_models", TaskStatus.COMPLETED, "Checked language models.")
                 if "install_models" not in self._completed_tasks:
                      self._set_task_status("install_models", TaskStatus.COMPLETED, "Installed language models.")
            
            # If checking and model(s) already present (may be inferred if install phase not reached before success msg)
            elif task_id == "check_models" and "already present" in line_lower:
                 # Don't change status text yet, wait for overall success or install trigger
                 pass 

    def _clean_status_message(self, message: str) -> str:
        """Clean up log messages for user-friendly display (similar to Windows worker)."""
        # Remove timestamp pattern (YYYY-MM-DD HH:MM:SS,ms)
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}'
        # Remove log level and module patterns (like - anpe.utils.setup_models - INFO -)
        log_pattern = r'(- [a-zA-Z0-9_.]+)? - (INFO|DEBUG|WARNING|ERROR|CRITICAL) - '
        full_pattern = rf'({timestamp_pattern})?\s*{log_pattern}?'
        cleaned = re.sub(full_pattern, '', message).strip()

        # Specific replacements (can be expanded)
        replacements = {
            r'en_core_web_sm': 'English language model',
            r'benepar_en3': 'English parsing model',
            r'spaCy': 'spaCy (text processing)',
            r'Benepar': 'Benepar (parsing)',
            # Add more as needed based on actual anpe.utils.setup_models logs
        }
        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # General cleanup
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        if cleaned and not cleaned[0].isupper(): # Capitalize
            cleaned = cleaned[0].upper() + cleaned[1:]

        # Filter out overly technical or redundant messages if desired
        technical_patterns = [
            r'package found by importlib',
            r'Verification Step \d+ OK',
            r'using importlib',
            r'Found model alias',
            # Add more patterns to filter out if needed
        ]
        for pattern in technical_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return "" # Return empty string to prevent displaying this as status

        # Further specific simplifications
        if "checking spacy model" in cleaned.lower():
            return "Checking required text processing model..."
        if "checking benepar model" in cleaned.lower():
            return "Checking required parsing model..."
        if "successfully downloaded and verified" in cleaned.lower():
            return "Model download verified."
        if "model setup process completed successfully" in cleaned.lower():
            return "Language model setup complete."
        if "already present" in cleaned.lower():
             # Don't show "already present" as main status, keep previous status
             return ""
        if "attempting download" in cleaned.lower():
             return "Downloading required models..."

        # --- Keep existing download cleaning --- 
        if "Downloading" in cleaned:
             match = re.search(r'Downloading model file ([^/]+)', cleaned)
             if match:
                 model_name = match.group(1)
                 return f"Downloading language model: {model_name}"
             
             cleaned = re.sub(r'Downloading [^ ]+ to [^ ]+', 'Downloading language models', cleaned)
             cleaned = re.sub(r'Extracting archive', 'Extracting language models', cleaned)
        # --- End download cleaning --- 

        return cleaned if len(cleaned) > 5 else "" # Avoid very short/empty messages

    def _set_task_status(self, task_id: str, status: int, status_text: str):
        """Helper to set task status, track state, update text, and emit signal."""
        if task_id not in self._tasks:
            logger.warning(f"Attempted to set status for unknown task_id: {task_id}")
            return
                
        # Emit signal for UI update (TaskItemMacOS will handle the text display)
        self.task_status_update.emit(task_id, status, status_text)

        # Track completion state
        if status == TaskStatus.COMPLETED:
            self._completed_tasks.add(task_id)
        elif status == TaskStatus.FAILED:
            self._completed_tasks.discard(task_id) 

    def _mark_all_tasks_failed(self):
        """Mark all simplified tasks as failed."""
        for task_id in self._tasks:
            if task_id not in self._completed_tasks:
                self._set_task_status(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]}")

    def _handle_stderr(self):
        """Process error output from the script."""
        if not self._process: return
        try:
            data = self._process.readAllStandardError().data().decode(errors='replace').strip()
            if not data: return

            self.log_update.emit(f"STDERR: {data}") # Log it clearly as STDERR
            logger.warning(f"Model setup script STDERR: {data}")

            # Try to determine if this indicates a failure
            line_lower = data.lower()
            if any(err in line_lower for err in ["error", "failed", "exception", "traceback"]):
                self._error_message = f"Error during model setup: {data.splitlines()[0]}" # First line usually most relevant
                # Mark current or relevant task as failed
                failed_task = self._active_task_id
                if not failed_task: # Guess based on content if no task active
                    if "spacy" in line_lower: failed_task = "spacy_model"
                    elif "benepar" in line_lower: failed_task = "benepar_model"
                if failed_task:
                    self._set_task_status(failed_task, TaskStatus.FAILED, f"Failed: {self._tasks[failed_task]}")
                else: # Mark all if unsure
                    self._mark_all_tasks_failed()
            
        except Exception as e:
            self.log_update.emit(f"Error processing stderr: {e}")
            logger.error("Error processing stderr: {e}", exc_info=True)

    def _handle_process_error(self, error: QProcess.ProcessError):
        """Handle QProcess execution errors (e.g., command not found)."""
        if not self._process: return
        error_string = self._process.errorString()
        self._error_message = f"Process execution error ({error}): {error_string}"
        self.log_update.emit(f"ERROR: {self._error_message}")
        self.status_update.emit(f"Error launching model setup: {error_string}")
        logger.error(self._error_message)
        self._mark_all_tasks_failed()
        self.finished.emit(False, self._error_message)
        self._process = None # Prevent further processing

    def _handle_finish(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion."""
        # Process any final output buffered before finish signal
        self._handle_stdout()
        self._handle_stderr()

        self.log_update.emit(f"Model setup process finished. Exit code: {exit_code}, Status: {exit_status}")

        final_success = False
        if exit_status == QProcess.ExitStatus.CrashExit:
            self._error_message = self._error_message or "Model setup process crashed unexpectedly."
            self.log_update.emit(f"ERROR: {self._error_message}")
            self.status_update.emit("Error: Model setup process crashed.")
        elif exit_code == 0:
            # Process exited cleanly (Exit Code 0)
            # Aggressively mark all tasks as completed on clean exit, 
            # even if specific log lines weren't caught.
            all_tasks_completed = True
            for task_id in self._tasks:
                if task_id not in self._completed_tasks:
                    logger.warning(f"Task '{task_id}' not marked complete by logs, but process exited cleanly. Marking complete.")
                    self._set_task_status(task_id, TaskStatus.COMPLETED, f"{self._tasks[task_id]} installed.")
                    # Keep track if we had to force-complete any
                    # all_tasks_completed = False # Optional: Be strict?

            if all_tasks_completed:
                self.log_update.emit("Model setup process completed successfully.")
                self.status_update.emit("All language models ready.")
                final_success = True
            # else: # Optional: Treat forced completion as a warning/potential issue? 
            #     self._error_message = "Model setup finished, but completion status for some tasks inferred."
            #     self.log_update.emit(f"WARNING: {self._error_message}")
            #     final_success = True # Still treat as success for now

        else:
            # Explicit non-zero exit code or other failure
            self._error_message = self._error_message or f"Model setup failed with exit code {exit_code}."
            self.log_update.emit(f"ERROR: {self._error_message}")
            self.status_update.emit("Error: Model setup failed. Check logs.")
            final_success = False # Ensure failure

        # Ensure any task still marked PROCESSING is marked FAILED if overall failure
        if not final_success:
            for task_id in self._tasks:
                # A bit aggressive, but ensures UI doesn't show processing on failure
                # Need access to current status to check if PROCESSING...
                # Let's just mark all non-completed as failed on error exit
                if task_id not in self._completed_tasks:
                    # Use _set_task_status to ensure signal is emitted correctly
                    self._set_task_status(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]}") 

        # Log the final outcome before emitting signal
        logger.info(f"ModelWorker determined final_success={final_success}")
        self.finished.emit(final_success, self._error_message if not final_success else "")
        self._process = None # Cleanup 
        logger.info("ModelSetupWorkerMacOS thread finished.")
        # Optionally emit a separate signal if complex cleanup needed after finished
        # self.work_finished.emit()

    # Method to be called by SetupWizard if cancellation occurs
    def request_stop(self):
         logger.info("Stop requested for ModelSetupWorkerMacOS")
         if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
              logger.warning("Attempting to terminate model setup process due to cancellation.")
              self._process.terminate() # Terminate the QProcess
              # Optionally wait a very short time
              # self._process.waitForFinished(500) 

# Note: We don't define start() here anymore. The calling code (SetupWizard)
# will be responsible for creating the QThread and starting it. 