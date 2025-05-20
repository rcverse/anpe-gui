import sys
import os
import re
import logging
from typing import Optional
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QProcess, QProcessEnvironment, QThread

from installer_macos.widgets.task_list_widget_macos import TaskStatus

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
        self._processing_tasks = set() # Tracks tasks in PROCESSING state
        self._needs_action_tasks = set() # Tracks tasks in NEEDS_ACTION state
        self._error_message = "" # Store last significant error
        
        # Define GRANULAR tasks
        self._tasks = {
            "check_spacy": "Check spaCy Model",
            "install_spacy": "Install spaCy Model",
            "check_benepar": "Check Benepar Model",
            "install_benepar": "Install Benepar Model",
        }
        self._task_order = ["check_spacy", "install_spacy", "check_benepar", "install_benepar"] # For sequential processing

        # No longer using _phase_patterns, parsing will be more direct
        
        # Verify the python executable path exists
        if not self._python_exe_path or not os.path.isfile(self._python_exe_path):
             logger.error(f"Standalone Python executable not found or invalid at: {self._python_exe_path}")
             self.status_update.emit("ERROR: Standalone Python executable not found.")
             raise FileNotFoundError(f"Standalone Python executable not found at: {self._python_exe_path}")

    def run(self):
        """Run the anpe.utils.setup_models script. Runs in a separate thread."""
        logger.info("ModelSetupWorkerMacOS thread started.")
        # Initialize tasks as pending
        for task_id in self._task_order: # Use task_order for initialization
            self.task_status_update.emit(task_id, TaskStatus.PENDING, self._tasks[task_id])

        self.log_update.emit(f"Starting model setup using standalone Python")
        self.status_update.emit("Starting language model check...")

        # Start with the first task in order
        self._active_task_id = self._task_order[0] if self._task_order else None
        if self._active_task_id:
            self._set_task_status(self._active_task_id, TaskStatus.PROCESSING, f"Processing: {self._tasks[self._active_task_id]}")
        else:
            logger.error("Task order is empty, cannot start.")
            self.finished.emit(False, "Internal error: Task order empty.")
            return

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
        """Set up the QProcess, clean its environment, and connect signals."""
        self._process = QProcess()

        # --- BEGIN ENVIRONMENT CLEANING FOR MODEL SCRIPT ---
        process_env = QProcessEnvironment.systemEnvironment()
        process_env.remove("PYTHONHOME")
        logger.info("Removed PYTHONHOME from model setup QProcess environment.")

        # Expecting python_exe_path to be 3.11 now
        python_exe_path_obj = Path(self._python_exe_path)
        # Derive version from the executable name (e.g., python3.11)
        if python_exe_path_obj.name.startswith("python3."):
            try:
                version_str = python_exe_path_obj.name.split('python')[1]
                major, minor = map(int, version_str.split('.')[:2])
                logger.debug(f"Derived version {major}.{minor} from executable name for model setup QProcess env.")
            except Exception:
                logger.warning(f"Could not derive version from {python_exe_path_obj.name} for model setup QProcess env, falling back to 3.11")
                major, minor = 3, 11 # Hardcoded fallback based on current target
        else:
            logger.warning(f"Cannot parse version from {python_exe_path_obj.name} for model setup QProcess env, assuming 3.11")
            major, minor = 3, 11 # Hardcoded fallback

        standalone_python_lib_dir = python_exe_path_obj.parent.parent / "lib" / f"python{major}.{minor}"

        if standalone_python_lib_dir.is_dir():
            logger.info(f"Setting PYTHONPATH for model setup QProcess EXCLUSIVELY to: {standalone_python_lib_dir}")
            process_env.insert("PYTHONPATH", str(standalone_python_lib_dir)) # Set ONLY this path
            logger.debug(f"Effective PYTHONPATH for model setup QProcess: {process_env.value('PYTHONPATH')}")
        else:
            # This would be a critical error, the previous steps should have ensured this exists
            logger.error(f"CRITICAL: Could not find standalone Python lib directory at {standalone_python_lib_dir} for model setup QProcess.")
            process_env.remove("PYTHONPATH")
            self._error_message = f"Cannot find library path for standalone Python: {standalone_python_lib_dir}"
            return False # Indicate failure to setup process

        self._process.setProcessEnvironment(process_env)
        # --- END ENVIRONMENT CLEANING FOR MODEL SCRIPT ---

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
                # Clean status message is now primarily handled within _update_task_status_from_line
                # to provide more context-specific status updates.
                # General status_update can still be used for broader messages if needed.
                # clean_status = self._clean_status_message(line) 
                # if clean_status:
                #    self.status_update.emit(clean_status)

        except Exception as e:
            self.log_update.emit(f"Error processing stdout: {e}")
            logger.error("Error processing stdout: {e}", exc_info=True)

    def _update_task_status_from_line(self, line: str):
        """Update simplified task status based on log line content."""
        line_lower = line.strip().lower()
        if not line_lower: return

        # --- Global Error/Success Check First ---
        if any(err in line_lower for err in ["error:", " failed", "exception", "critical", "traceback"]):
            self._error_message = f"Error during model setup: {line}"
            self.log_update.emit(f"ERROR DETECTED: {self._error_message}")
            if self._active_task_id:
                self._set_task_status(self._active_task_id, TaskStatus.FAILED, f"Failed: {self._tasks[self._active_task_id]}")
            self._fail_subsequent_tasks(self._active_task_id)
            return # Stop further processing of this line

        if "model setup process completed successfully" in line_lower:
            self.log_update.emit("Overall success message detected in logs.")
            # Mark all remaining PENDING/PROCESSING tasks as COMPLETED
            for task_id_to_complete in self._task_order:
                if task_id_to_complete not in self._completed_tasks:
                    # Check if it's an install task that might have been skipped
                    if "install" in task_id_to_complete and self._is_model_already_present(task_id_to_complete.split('_')[1]):
                        self._set_task_status(task_id_to_complete, TaskStatus.COMPLETED, f"{self._tasks[task_id_to_complete]} (already present)")
                    else:
                        self._set_task_status(task_id_to_complete, TaskStatus.COMPLETED, f"{self._tasks[task_id_to_complete]}")
            self._active_task_id = None # No more active tasks
            self.status_update.emit("Language model setup complete.")
            return

        # --- Active Task Processing ---
        if not self._active_task_id:
            return # No active task to update

        current_task_description = self._tasks[self._active_task_id]
        status_to_emit = self._clean_status_message(line) # Get a cleaned version for user status

        # --- SpaCy Check ---
        if self._active_task_id == "check_spacy":
            if "checking spacy model" in line_lower:
                self._set_task_status("check_spacy", TaskStatus.PROCESSING, "Checking spaCy model...")
                if status_to_emit: self.status_update.emit(status_to_emit)
            elif "spacy model already present" in line_lower or "spacy model is already installed" in line_lower:
                self._set_task_status("check_spacy", TaskStatus.COMPLETED, "spaCy model already present.")
                self._set_task_status("install_spacy", TaskStatus.COMPLETED, "spaCy model installation skipped (already present).")
                self._completed_tasks.add("install_spacy") # Mark as completed for logic
                self._advance_to_next_task()
                if status_to_emit: self.status_update.emit(status_to_emit or "spaCy model found.")
            elif "spacy model not found" in line_lower: # Explicit not found
                self._set_task_status("check_spacy", TaskStatus.COMPLETED, "spaCy model not found.")
                # Set install task to NEEDS_ACTION instead of directly proceeding to install
                self._set_task_status("install_spacy", TaskStatus.NEEDS_ACTION, "spaCy model needs to be installed")
                self._advance_to_next_task() # Moves to install_spacy
                if status_to_emit: self.status_update.emit(status_to_emit or "spaCy model not found, installation needed.")
            # If "not found" is part of a download attempt, install_spacy will pick it up

        # --- SpaCy Install ---
        elif self._active_task_id == "install_spacy":
            # If task is in NEEDS_ACTION state and actual download begins, update to PROCESSING
            if "installing spacy model" in line_lower or "downloading spacy model" in line_lower or "en_core_web_" in line_lower:
                if "install_spacy" in self._needs_action_tasks:
                    # Clear NEEDS_ACTION state when starting actual download
                    self._needs_action_tasks.discard("install_spacy")
                self._set_task_status("install_spacy", TaskStatus.PROCESSING, "Installing spaCy model...")
                if status_to_emit: self.status_update.emit(status_to_emit)
            elif "successfully downloaded and verified spacy model" in line_lower or "spacy model installed successfully" in line_lower:
                self._set_task_status("install_spacy", TaskStatus.COMPLETED, "spaCy model installed successfully.")
                self._advance_to_next_task()
                if status_to_emit: self.status_update.emit(status_to_emit or "spaCy model installed.")
        
        # --- Benepar Check ---
        elif self._active_task_id == "check_benepar":
            if "checking benepar model" in line_lower:
                self._set_task_status("check_benepar", TaskStatus.PROCESSING, "Checking Benepar model...")
                if status_to_emit: self.status_update.emit(status_to_emit)
            elif "benepar model already present" in line_lower or "benepar model is already installed" in line_lower:
                self._set_task_status("check_benepar", TaskStatus.COMPLETED, "Benepar model already present.")
                self._set_task_status("install_benepar", TaskStatus.COMPLETED, "Benepar installation skipped (already present).")
                self._completed_tasks.add("install_benepar")
                self._advance_to_next_task()
                if status_to_emit: self.status_update.emit(status_to_emit or "Benepar model found.")
            elif "benepar model not found" in line_lower: # Explicit not found
                self._set_task_status("check_benepar", TaskStatus.COMPLETED, "Benepar model not found.")
                # Set install task to NEEDS_ACTION instead of directly proceeding to install
                self._set_task_status("install_benepar", TaskStatus.NEEDS_ACTION, "Benepar model needs to be installed")
                self._advance_to_next_task() # Moves to install_benepar
                if status_to_emit: self.status_update.emit(status_to_emit or "Benepar model not found, installation needed.")

        # --- Benepar Install ---
        elif self._active_task_id == "install_benepar":
            # If task is in NEEDS_ACTION state and actual download begins, update to PROCESSING
            if "installing benepar model" in line_lower or "downloading benepar model" in line_lower or "benepar_en" in line_lower:
                if "install_benepar" in self._needs_action_tasks:
                    # Clear NEEDS_ACTION state when starting actual download
                    self._needs_action_tasks.discard("install_benepar")
                self._set_task_status("install_benepar", TaskStatus.PROCESSING, "Installing Benepar model...")
                if status_to_emit: self.status_update.emit(status_to_emit)
            elif "successfully downloaded and verified benepar model" in line_lower or "benepar model installed successfully" in line_lower:
                self._set_task_status("install_benepar", TaskStatus.COMPLETED, "Benepar model installed successfully.")
                self._advance_to_next_task() # Should be the end of tasks
                if status_to_emit: self.status_update.emit(status_to_emit or "Benepar model installed.")
        
        # Fallback for general download messages if not caught by specific model install
        elif "downloading model file" in line_lower and self._active_task_id and "install" in self._active_task_id:
            # Always transition from NEEDS_ACTION to PROCESSING when actual download starts
            if self._active_task_id in self._needs_action_tasks:
                self._needs_action_tasks.discard(self._active_task_id)
            self._set_task_status(self._active_task_id, TaskStatus.PROCESSING, f"Downloading: {current_task_description}...")
            if status_to_emit: self.status_update.emit(status_to_emit)

    def _is_model_already_present(self, model_type: str) -> bool:
        """Helper to check if a model type (spacy/benepar) was marked as already present."""
        # This is a placeholder. In a more robust system, you might check the status of the 'check' task.
        # For now, we assume if an 'install' task is skipped, it's because the 'check' found it.
        # This logic is now more integrated into _update_task_status_from_line.
        check_task_id = f"check_{model_type}"
        # A more direct way: if install_spacy is completed but was never set to processing, it was skipped.
        # However, this check isn't easily done without more state.
        # The current _update_task_status_from_line directly marks install as completed if check says "already present".
        return f"install_{model_type}" in self._completed_tasks and \
               not self._was_task_processed(f"install_{model_type}")

    def _was_task_processed(self, task_id: str) -> bool:
        """ Helper to see if a task was ever set to PROCESSING. Needs more state tracking if used. """
        # This is a conceptual helper. To implement it fully, you'd need to store the history of states.
        # For now, this isn't strictly necessary with the current refactoring.
        return True # Placeholder

    def _advance_to_next_task(self):
        """Advances _active_task_id to the next task in _task_order."""
        if not self._active_task_id:
            logger.debug("Cannot advance task, no active task ID.")
            return

        try:
            current_index = self._task_order.index(self._active_task_id)
            if current_index + 1 < len(self._task_order):
                self._active_task_id = self._task_order[current_index + 1]
                # Set the new active task to PROCESSING if it's not already completed (e.g. skipped)
                if self._active_task_id not in self._completed_tasks:
                    self._set_task_status(self._active_task_id, TaskStatus.PROCESSING, f"Processing: {self._tasks[self._active_task_id]}")
                logger.info(f"Advanced to next task: {self._active_task_id}")
            else:
                logger.info("All tasks processed or current task was the last.")
                self._active_task_id = None # No more tasks
        except ValueError:
            logger.error(f"Could not find active task {self._active_task_id} in task order.")
            self._active_task_id = None

    def _fail_subsequent_tasks(self, failed_task_id: Optional[str]):
        """Marks all tasks from the failed_task_id onwards as FAILED."""
        if not failed_task_id: # If no specific task failed, fail all non-completed.
            for task_id in self._task_order:
                if task_id not in self._completed_tasks:
                    self._set_task_status(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]}")
            return

        try:
            start_index = self._task_order.index(failed_task_id)
            for i in range(start_index, len(self._task_order)):
                task_to_fail = self._task_order[i]
                if task_to_fail not in self._completed_tasks:
                    self._set_task_status(task_to_fail, TaskStatus.FAILED, f"Failed: {self._tasks[task_to_fail]}")
        except ValueError:
            logger.error(f"Failed task {failed_task_id} not found in task order. Marking all remaining as failed.")
            self._mark_all_tasks_failed()

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
            # More specific messages are now handled in _update_task_status_from_line
            return "Model download verified." 
        if "model setup process completed successfully" in cleaned.lower():
            return "Language model setup complete."
        if "already present" in cleaned.lower():
             # Specific "already present" for spaCy/Benepar handled in _update_task_status_from_line
             return "" # Avoid generic "already present" status
        if "attempting download" in cleaned.lower():
             # Specific download messages for spaCy/Benepar handled in _update_task_status_from_line
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
        
        # Don't change status if already completed
        if task_id in self._completed_tasks and status != TaskStatus.COMPLETED:
            logger.debug(f"Task {task_id} is already completed, not changing to {status}")
            return
            
        # Emit signal for UI update (TaskItemMacOS will handle the text display)
        self.task_status_update.emit(task_id, status, status_text)

        # Track task state in appropriate collections
        if status == TaskStatus.PROCESSING:
            self._processing_tasks.add(task_id)
            self._needs_action_tasks.discard(task_id)
        elif status == TaskStatus.NEEDS_ACTION:
            self._needs_action_tasks.add(task_id)
            self._processing_tasks.discard(task_id)
        elif status == TaskStatus.COMPLETED:
            self._completed_tasks.add(task_id)
            self._processing_tasks.discard(task_id)
            self._needs_action_tasks.discard(task_id)
        elif status == TaskStatus.FAILED:
            self._completed_tasks.discard(task_id) 
            self._processing_tasks.discard(task_id)
            self._needs_action_tasks.discard(task_id)

    def _mark_all_tasks_failed(self):
        """Mark all defined tasks as failed if they aren't completed."""
        for task_id in self._task_order: # Iterate through the defined order
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
            all_tasks_completed_or_skipped = True
            for task_id in self._task_order: # Use task_order
                if task_id not in self._completed_tasks:
                    # Check if it's an install task that might have been skipped because model was present
                    model_type = None
                    if task_id == "install_spacy": model_type = "spacy"
                    elif task_id == "install_benepar": model_type = "benepar"

                    is_skipped_install = False
                    if model_type:
                        check_task_id = f"check_{model_type}"
                        # If check task is complete AND this install task is not, assume it was present/skipped
                        if check_task_id in self._completed_tasks:
                             # A bit more specific: check if the 'check' task specifically said 'already present'
                             # This requires storing more detail about the check task's outcome if needed.
                             # For now, assume if check is done and install isn't, it was due to presence.
                             # The _update_task_status_from_line should handle this ideally.
                             self._set_task_status(task_id, TaskStatus.COMPLETED, f"{self._tasks[task_id]} (already present or completed)")
                             is_skipped_install = True


                    if not is_skipped_install:
                        logger.warning(f"Task '{self._tasks[task_id]}' not marked complete by logs, but process exited cleanly. Marking complete.")
                        self._set_task_status(task_id, TaskStatus.COMPLETED, f"{self._tasks[task_id]}")
                    
            # Re-evaluate all_tasks_completed_or_skipped based on the _completed_tasks set *after* potential updates
            all_tasks_completed_or_skipped = all(t_id in self._completed_tasks for t_id in self._task_order)


            if all_tasks_completed_or_skipped:
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

        # Ensure any task still marked PROCESSING or PENDING is marked FAILED if overall failure
        if not final_success:
            self._fail_subsequent_tasks(self._active_task_id) # Fail current and subsequent
            # Also ensure any earlier PENDING tasks are marked failed if not already handled.
            for task_id in self._task_order:
                 if task_id not in self._completed_tasks: # Check all, not just subsequent
                      # Check if it's already failed by _fail_subsequent_tasks to avoid double signal
                      # This requires a way to get current status, or trust _set_task_status handles no-op if already failed
                      self._set_task_status(task_id, TaskStatus.FAILED, f"Failed: {self._tasks[task_id]} (due to overall failure)")

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