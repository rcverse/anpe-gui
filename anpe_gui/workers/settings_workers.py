"""
Background workers for ANPE GUI settings dialog operations.
"""

import sys
import logging
import nltk
import subprocess
import urllib.request
import urllib.error
import json
import os
import shutil
import spacy
import importlib.metadata
import re # Import regex module

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# Constants and Utilities from ANPE Core (Mirroring settings_dialog.py)
CORE_PACKAGE_NAME = "anpe"
try:
    from anpe.utils.setup_models import (
        check_spacy_model, check_benepar_model,
        SPACY_MODEL_MAP, BENEPAR_MODEL_MAP, install_spacy_model, install_benepar_model,
        DEFAULT_SPACY_ALIAS, DEFAULT_BENEPAR_ALIAS, # Needed by ModelActionWorker
        setup_models # Add setup_models here
    )
    from anpe.utils.clean_models import clean_all
    from anpe.utils.model_finder import (
        find_installed_spacy_models, find_installed_benepar_models
    )
    # Core ANPE is assumed available by workers needing it
except ImportError as e:
    logging.error(f"Failed to import ANPE utilities for Settings Workers: {e}")
    # Define dummy maps and functions if core package is missing
    SPACY_MODEL_MAP = {"sm": "en_core_web_sm", "md": "en_core_web_md", "lg": "en_core_web_lg", "trf": "en_core_web_trf"}
    BENEPAR_MODEL_MAP = {"default": "benepar_en3", "large": "benepar_en3_large"}
    DEFAULT_SPACY_ALIAS = "md" # Need a default value
    DEFAULT_BENEPAR_ALIAS = "default" # Need a default value
    def check_spacy_model(*args, **kwargs): return False
    def check_benepar_model(*args, **kwargs): return False
    def install_spacy_model(*args, **kwargs): return False
    def install_benepar_model(*args, **kwargs): return False
    def clean_all(*args, **kwargs): return {"spacy": False, "benepar": False}
    def find_installed_spacy_models(): return []
    def find_installed_benepar_models(): return []
    # Setup models worker needs the actual function
    # try:
    #     from anpe.utils.setup_models import setup_models
    # except ImportError:
    #     def setup_models(*args, **kwargs): return False
    # Define the dummy here if the main import failed
    def setup_models(*args, **kwargs): 
        logging.error("Dummy setup_models called - ANPE core import failed.")
        return False
    # NLTK dummy for path finding in ModelActionWorker
    class DummyNLTKData:
        def find(self, path): raise LookupError(f"DummyNLTKData: Could not find {path}")
    class DummyNLTK:
        data = DummyNLTKData()
    # Avoid overwriting real nltk if it exists but utils failed
    # Check if nltk itself was imported successfully before potentially overwriting
    try:
        nltk.data
    except (NameError, AttributeError):
        nltk = DummyNLTK()

# --- Setup NLTK Data Directory --- 
def setup_nltk_data_dir() -> str | None:
    """Ensures user's NLTK data directory exists and is preferred.

    Returns:
        str or None: The path to the user's NLTK data directory, or None on error.
    """
    try:
        # User-specific directory (in home directory)
        home = os.path.expanduser("~")
        nltk_user_dir = os.path.join(home, "nltk_data")

        # Create directory if it doesn't exist
        os.makedirs(nltk_user_dir, exist_ok=True)
        logging.debug(f"Ensured NLTK user data directory exists: {nltk_user_dir}")

        # Ensure this directory is the first path NLTK checks
        if nltk_user_dir not in nltk.data.path:
            nltk.data.path.insert(0, nltk_user_dir)
            logging.debug(f"Prepended {nltk_user_dir} to nltk.data.path")

        # Set environment variable for potential subprocess use (like benepar download)
        os.environ['NLTK_DATA'] = nltk_user_dir
        logging.debug(f"Set NLTK_DATA environment variable to: {nltk_user_dir}")

        # Verify it's the primary path
        if nltk.data.path[0] != nltk_user_dir:
             logging.warning(f"Expected {nltk_user_dir} to be the first NLTK path, but found {nltk.data.path[0]}. This might cause issues.")

        return nltk_user_dir

    except PermissionError as e:
        logging.error(f"Permission denied creating or accessing NLTK data directory at {getattr(e, 'filename', 'N/A')}. Please check permissions.", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Unexpected error during NLTK data directory setup: {e}", exc_info=True)
        return None

# Get the primary NLTK data directory path
NLTK_DATA_DIR = setup_nltk_data_dir()
if NLTK_DATA_DIR is None:
    logging.critical("CRITICAL: Could not setup NLTK data directory. Benepar operations will likely fail.")
    # Optionally fallback to a default relative path if needed, but None indicates a problem
    # NLTK_DATA_DIR = "." # Example fallback, might not work well
# ------------------------------- 

# --- Worker Objects --- 

class CoreUpdateWorker(QObject):
    """Worker for checking and performing ANPE core updates."""
    check_finished = pyqtSignal(str, str, str) # latest_version, current_version, error_string
    update_progress = pyqtSignal(int, str)    # value (-1 for indeterminate), message
    update_finished = pyqtSignal(bool, str)   # success, message
    log_message = pyqtSignal(str)             # For detailed subprocess output
    
    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    @pyqtSlot()
    def run_check(self):
        """Check PyPI for the latest version."""
        latest_version = "N/A"
        error_string = ""
        try:
            # Use PyPI JSON API
            pypi_url = f"https://pypi.org/pypi/{CORE_PACKAGE_NAME}/json"
            # Added headers to mimic a browser request, potentially avoiding blocks
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
            }
            req = urllib.request.Request(pypi_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    latest_version = data.get("info", {}).get("version", "N/A")
                else:
                    error_string = f"Failed to fetch from PyPI (Status: {response.status})"
        except urllib.error.URLError as e:
            error_string = f"Network error checking PyPI: {e.reason}"
        except json.JSONDecodeError:
            error_string = "Error parsing PyPI response."
        except Exception as e:
            error_string = f"An unexpected error occurred: {e}"
            
        self.check_finished.emit(latest_version, self.current_version, error_string)

    @pyqtSlot()
    def run_update(self):
        """Run pip install --upgrade anpe, streaming output."""
        success = False
        message = ""
        try:
            self.update_progress.emit(-1, "Starting update process...") # Indeterminate
            
            # --- Upgrade pip with streaming --- 
            self.log_message.emit("--- Upgrading pip ---")
            try:
                pip_upgrade_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
                self.log_message.emit(f"Running: {' '.join(pip_upgrade_cmd)}")
                process_pip = subprocess.Popen(
                    pip_upgrade_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, # Redirect stderr to stdout
                    text=True, 
                    encoding='utf-8', 
                    bufsize=1 # Line buffering
                )
                # Stream output
                for line in iter(process_pip.stdout.readline, ''):
                    self.log_message.emit(line.strip())
                process_pip.stdout.close()
                return_code_pip = process_pip.wait()
                if return_code_pip != 0:
                    self.log_message.emit(f"WARNING: pip upgrade failed with code {return_code_pip}. Continuing update attempt...")
                    # Don't mark overall success as False here, just log warning
                else:
                    self.log_message.emit("pip upgrade successful.")
            except Exception as pip_e:
                self.log_message.emit(f"WARNING: Error running pip upgrade: {pip_e}. Continuing update attempt...")
                logging.warning(f"Could not upgrade pip: {pip_e}")
            self.log_message.emit("----------------------")
            # --------------------------------
            
            # --- Upgrade ANPE core with streaming --- 
            self.log_message.emit(f"--- Upgrading {CORE_PACKAGE_NAME} --- ")
            anpe_upgrade_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", CORE_PACKAGE_NAME]
            self.log_message.emit(f"Running: {' '.join(anpe_upgrade_cmd)}")
            process_anpe = subprocess.Popen(
                anpe_upgrade_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            # Stream output
            full_output = []
            for line in iter(process_anpe.stdout.readline, ''):
                line_strip = line.strip()
                self.log_message.emit(line_strip)
                full_output.append(line_strip)
            process_anpe.stdout.close()
            return_code_anpe = process_anpe.wait()
            # --------------------------------------
            
            if return_code_anpe == 0:
                message = f"{CORE_PACKAGE_NAME} update successful!"
                success = True
                self.update_progress.emit(100, "Update complete.")
                self.log_message.emit("----------------------")
            else:
                message = f"{CORE_PACKAGE_NAME} update failed (exit code: {return_code_anpe}). Check details log."
                success = False
                self.update_progress.emit(0, "Update failed.")
                self.log_message.emit(f"ERROR: Update failed with code {return_code_anpe}")
                self.log_message.emit("----------------------")
                # Optional: Add last few lines of output to the main message?
                # message += "\n\nLast Output:\n" + "\n".join(full_output[-10:])
                
        except Exception as e:
            message = f"An unexpected error occurred during update: {e}"
            logging.error(message, exc_info=True)
            success = False
            self.update_progress.emit(0, "Update failed.")
            self.log_message.emit(f"FATAL ERROR during update: {e}")
            
        self.update_finished.emit(success, message)

class CleanWorker(QObject):
    """Worker to run clean_all in a background thread."""
    finished = pyqtSignal(dict) # Return status dictionary from clean_all
    progress = pyqtSignal(str) # To send status updates
    log_message = pyqtSignal(str) # Added for consistency, but not used

    @pyqtSlot()
    def run(self):
        self.progress.emit("Starting model cleanup process...")
        results = {}
        try:
            # Emit more specific messages if possible within clean_all structure (if it supports callbacks/logging)
            # For now, use generic start/end messages
            self.progress.emit("Cleaning spaCy models...") # Example stage message
            # Assume clean_all internally handles stages like spaCy, Benepar, NLTK
            results = clean_all() # Removed logger passing
            self.progress.emit("Cleaning Benepar models...") # Example stage message
            self.progress.emit("Model cleanup process finished.")
        except Exception as e:
            logging.error(f"Exception during background model cleanup: {e}", exc_info=True)
            self.progress.emit(f"Error during cleanup: {e}")
            # Ensure results dict still has keys even on error
            results = {"spacy": False, "benepar": False}
        finally:
            # Ensure finished is always emitted
            self.finished.emit(results)

class InstallDefaultsWorker(QObject):
    """Worker to run setup_models with default settings."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str) # success, final_message
    log_message = pyqtSignal(str) # Added for consistency, but not used directly by this worker

    @pyqtSlot()
    def run(self):
        success = False
        message = ""
        try:
            self.progress.emit("Starting default model setup...")
            # Import setup_models here to avoid potential issues if core ANPE changes
            # Relies on the import at the top of the file now
            # from anpe.utils.setup_models import setup_models, check_all_models_present

            # Although setup_models handles checks internally, we can emit progress messages
            self.progress.emit("Running setup for default models...")
            # We might need callbacks or better progress reporting from setup_models in the future
            # For now, just call it.
            success = setup_models() # Calls with default arguments

            if success:
                message = "Default models installed/verified successfully."
                self.progress.emit("Default setup complete.")
            else:
                message = "Failed to install/verify one or more default models. Check logs."
                self.progress.emit("Default setup failed.")

        except ImportError:
            message = "Error: Could not import ANPE setup utilities."
            logging.error(message, exc_info=True)
            self.progress.emit(message)
            success = False
        except Exception as e:
            message = f"An unexpected error occurred during default setup: {e}"
            logging.error(message, exc_info=True)
            self.progress.emit(message)
            success = False
        finally:
            self.finished.emit(success, message)

class ModelActionWorker(QObject):
    """Worker for installing or uninstalling specific models."""
    progress = pyqtSignal(str) # Message only for progress updates
    finished = pyqtSignal(bool, str) # success, message
    log_message = pyqtSignal(str) # For detailed subprocess output
    
    def __init__(self, action: str, model_type: str, alias: str = None):
        """
        Initialize the worker.
        
        Args:
            action: Either "install" or "uninstall"
            model_type: One of "spacy", "benepar"
            alias: The model alias (e.g., "md", "lg", "default")
        """
        super().__init__()
        self.action = action
        self.model_type = model_type
        self.alias = alias
        
    def _run_subprocess_and_stream(self, cmd: list[str], description: str) -> tuple[int, list[str]]:
        """Helper to run a subprocess, stream its output, and return status/output."""
        self.log_message.emit(f"--- Running: {description} ---")
        self.log_message.emit(f"Command: {' '.join(cmd)}")
        full_output_lines = [] # Store lines for potential return
        return_code = -1 # Default error code
        # Regex to remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|(?:\[[0-?]*[ -/]*[@-~]))')
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0 # Hide console window on Windows
            )
            for line in iter(process.stdout.readline, ''):
                line_strip = line.strip()
                # Remove ANSI codes before emitting/storing
                cleaned_line = ansi_escape.sub('', line_strip)
                self.log_message.emit(cleaned_line) 
                full_output_lines.append(cleaned_line) # Store cleaned line
            process.stdout.close()
            return_code = process.wait()
            self.log_message.emit(f"--- {description} finished (code: {return_code}) ---")
        except FileNotFoundError:
            err_msg = f"ERROR: Command not found ({cmd[0]}). Is it installed and in PATH?"
            self.log_message.emit(err_msg)
            full_output_lines.append(err_msg)
            logging.error(f"Command not found: {cmd[0]}")
            return_code = -1 # Indicate error
        except Exception as e:
            err_msg = f"ERROR running {description}: {e}"
            self.log_message.emit(err_msg)
            full_output_lines.append(err_msg)
            logging.error(f"Error running subprocess for {description}: {e}", exc_info=True)
            return_code = -1 # Indicate error
        return return_code, full_output_lines
        
    @pyqtSlot()
    def run(self):
        """Execute the requested model action."""
        success = False
        message = ""
        action_verb = "Installing" if self.action == 'install' else "Uninstalling"
        target_desc = f"{self.model_type} model '{self.alias}'"

        try:
            self.progress.emit(f"Starting {action_verb.lower()} {target_desc}...")

            # spaCy / Benepar (Removed redundant outer check)
            # if self.model_type == 'spacy' or self.model_type == 'benepar': # Removed redundant check
            if not self.alias:
                message = f"Missing alias for {self.model_type} model action."
                success = False
            else:
                model_map = SPACY_MODEL_MAP if self.model_type == 'spacy' else BENEPAR_MODEL_MAP
                model_name = model_map.get(self.alias)
                if not model_name:
                    message = f"Unknown {self.model_type} model alias: {self.alias}"
                    success = False
                else:
                    # --- INSTALL ACTION --- 
                    if self.action == 'install':
                        install_success = True # Track overall install success
                        
                        # spaCy Specific Pre-checks/Installs
                        if self.model_type == 'spacy' and model_name.endswith('_trf'):
                            self.progress.emit("Checking for spacy-transformers...")
                            try:
                                importlib.metadata.version("spacy-transformers")
                                self.log_message.emit("'spacy-transformers' is already installed.")
                            except importlib.metadata.PackageNotFoundError:
                                self.progress.emit("Installing spacy-transformers dependency...")
                                cmd_trf = [sys.executable, '-m', 'pip', 'install', "spacy[transformers]"]
                                rc_trf, _ = self._run_subprocess_and_stream(cmd_trf, "spacy-transformers install")
                                if rc_trf != 0:
                                    self.progress.emit("Failed to install 'spacy-transformers'. Model install may fail.")
                                    # Don't set install_success to False here, let model download proceed
                                else:
                                    self.progress.emit("'spacy-transformers' installed.")
                                    
                        # Main Model Download/Install
                        self.progress.emit(f"Downloading/installing {self.model_type} model {model_name}...")
                        return_code = -1 # Default error
                        if self.model_type == 'spacy':
                            cmd_model = [sys.executable, '-m', 'spacy', 'download', model_name]
                            return_code, _ = self._run_subprocess_and_stream(cmd_model, f"spaCy download {model_name}")
                            install_success = (return_code == 0) and check_spacy_model(model_name)
                        elif self.model_type == 'benepar':
                            escaped_nltk_data_dir = NLTK_DATA_DIR.replace('\\', '\\\\')
                            benepar_script = (
                                f"import nltk; import benepar; import sys; "
                                f"nltk.data.path.insert(0, r'{escaped_nltk_data_dir}'); "
                                f"print('--- Starting benepar.download(\'{model_name}\') ---', flush=True); "
                                f"try: benepar.download('{model_name}'); print('--- benepar.download finished ---', flush=True); sys.exit(0); "
                                f"except Exception as e: print(f'ERROR in benepar.download: {{e}}', flush=True); sys.exit(1);"
                            )
                            cmd_model = [sys.executable, '-c', benepar_script]
                            return_code, _ = self._run_subprocess_and_stream(cmd_model, f"Benepar download {model_name}")
                            install_success = check_benepar_model(model_name) # Check after attempt

                        # Final Install Message/Status
                        success = install_success
                        message = f"Successfully installed {self.model_type} model {model_name}." if success else \
                                  f"Failed to install/verify {self.model_type} model {model_name} (code: {return_code}). Check logs."
                        self.progress.emit(message)
                                      
                    # --- UNINSTALL ACTION --- 
                    elif self.action == 'uninstall':
                        uninstall_success = True # Track overall uninstall success
                        
                        # Check if present first (no subprocess needed)
                        is_present = False
                        if self.model_type == 'spacy':
                            is_present = model_name in find_installed_spacy_models()
                        elif self.model_type == 'benepar':
                            is_present = model_name in find_installed_benepar_models()
                            
                        if not is_present:
                            message = f"{self.model_type} model {model_name} is not installed."
                            success = True # Already uninstalled
                        else:
                            self.progress.emit(f"Attempting to uninstall {self.model_type} model {model_name}...")
                            
                            # spaCy Uninstall (uses pip)
                            if self.model_type == 'spacy':
                                cmd_uninstall = [sys.executable, "-m", "pip", "uninstall", "-y", model_name]
                                rc_uninstall, out_uninstall = self._run_subprocess_and_stream(cmd_uninstall, f"pip uninstall {model_name}")
                                # Check return code AND output message from pip
                                pip_failed = rc_uninstall != 0 and not any("not installed" in line.lower() for line in out_uninstall)
                                if pip_failed:
                                     self.progress.emit(f"Pip uninstall command failed or reported issues.")
                                     # Don't set uninstall_success=False yet, try file removal
                                     
                                # Manual File Removal (No Stream)
                                self.progress.emit("Checking spaCy data directory for removal...")
                                try:
                                    data_path = spacy.util.get_data_path()
                                    if data_path and os.path.exists(data_path):
                                        model_path = os.path.join(data_path, model_name)
                                        if os.path.exists(model_path):
                                            self.progress.emit(f"Removing {model_path}...")
                                            if os.path.isdir(model_path):
                                                shutil.rmtree(model_path)
                                            else:
                                                os.remove(model_path)
                                except Exception as e:
                                    self.progress.emit(f"Could not access/remove from spaCy data directory: {e}")
                                    # Don't mark as failure just for this
                                    
                                # Final spaCy Check
                                if not check_spacy_model(model_name):
                                    uninstall_success = True
                                    message = f"Successfully uninstalled spaCy model {model_name}."
                                else:
                                    uninstall_success = False
                                    message = f"Failed to completely uninstall spaCy model {model_name}."

                            # Benepar Uninstall (Manual File Ops)
                            elif self.model_type == 'benepar':
                                found_something = False
                                removal_errors = False
                                try:
                                    import nltk
                                    self.progress.emit(f"Checking NLTK paths for {model_name} files...")
                                    # Check directory
                                    try:
                                        model_dir_path = nltk.data.find(f'models/{model_name}')
                                        if os.path.exists(model_dir_path):
                                            found_something = True
                                            self.progress.emit(f"Removing directory: {model_dir_path}")
                                            try:
                                                if os.path.isdir(model_dir_path):
                                                    shutil.rmtree(model_dir_path)
                                                else:
                                                    os.remove(model_dir_path)
                                            except Exception as e:
                                                self.progress.emit(f"Failed to remove {model_dir_path}: {e}")
                                                removal_errors = True
                                    except LookupError:
                                        self.progress.emit(f"Directory models/{model_name} not found.")
                                        
                                    # Check zip file
                                    nltk_paths = nltk.data.path
                                    for nltk_path in set(nltk_paths):
                                        models_dir = os.path.join(nltk_path, "models")
                                        if not os.path.isdir(models_dir):
                                            continue
                                        zip_path = os.path.join(models_dir, model_name + ".zip")
                                        if os.path.exists(zip_path):
                                            found_something = True
                                            self.progress.emit(f"Removing zip file: {zip_path}")
                                            try:
                                                os.remove(zip_path)
                                            except Exception as e:
                                                self.progress.emit(f"Failed to remove zip file {zip_path}: {e}")
                                                removal_errors = True
                                                    
                                except Exception as e:
                                    message = f"Error checking/removing Benepar model files: {e}"
                                    uninstall_success = False
                                
                                # Final Benepar Check (only if no error above)
                                if uninstall_success:
                                    if not check_benepar_model(model_name):
                                        if found_something and not removal_errors:
                                            message = f"Successfully uninstalled Benepar model {model_name}."
                                            uninstall_success = True
                                        elif not found_something:
                                            message = f"Benepar model {model_name} was not found (already uninstalled?)"
                                            uninstall_success = True
                                        else: # Found something but had removal errors
                                             message = f"Attempted uninstall of Benepar model {model_name}, but errors occurred."
                                             uninstall_success = False
                                    else:
                                        message = f"Failed to completely uninstall Benepar model {model_name}."
                                        uninstall_success = False
                                        
                        # Set overall success based on uninstall result
                        success = uninstall_success
                        # Ensure message is set if not already
                        if not message:
                            message = f"Uninstall process finished for {model_name}. Final status: {'Success' if success else 'Failed'}."
                        self.progress.emit(message) # Emit final status for uninstall
                            
        except Exception as e:
            success = False
            message = f"An unexpected error occurred during model action: {e}"
            logging.error(f"Model action worker error: {e}", exc_info=True)
            self.progress.emit(message) # Emit error to status label
            self.log_message.emit(f"FATAL ERROR: {message}") # Emit error to log
            
        self.progress.emit("Operation complete.") # Keep this final generic message
        self.finished.emit(success, message) 