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
import traceback # <<< Added for detailed error logging

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
    from anpe.utils.clean_models import (
        clean_all,
        uninstall_spacy_model,
        uninstall_benepar_model
    )
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
    def install_spacy_model(model_name, log_callback=None): return False
    def install_benepar_model(model_name, log_callback=None): return False
    def clean_all(log_callback=None): return {"spacy": False, "benepar": False}
    def uninstall_spacy_model(model_name, log_callback=None): return False
    def uninstall_benepar_model(model_name, log_callback=None): return False
    def find_installed_spacy_models(): return []
    def find_installed_benepar_models(): return []
    def setup_models(log_callback=None):
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
    log_message = pyqtSignal(str) # Signal for detailed log messages

    def _emit_log_message(self, message: str):
        """Emits the log message signal."""
        self.log_message.emit(message.strip())

    @pyqtSlot()
    def run(self):
        self.progress.emit("Starting model cleanup process...")
        results = {"spacy": False, "benepar": False} # Initialize results
        try:
            # Assuming clean_all now accepts log_callback and logs internally
            results = clean_all(log_callback=self._emit_log_message) # <<< Pass callback
            self.progress.emit("Model cleanup process finished.")
        except ImportError:
            error_msg = "Error: Could not import ANPE clean utilities."
            logging.error(error_msg, exc_info=True)
            self.progress.emit(error_msg)
            self._emit_log_message(f"ERROR: {error_msg}\n{traceback.format_exc()}")
            results = {"spacy": False, "benepar": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Exception during background model cleanup: {e}"
            logging.error(error_msg, exc_info=True)
            self.progress.emit(f"Error during cleanup: {e}")
            self._emit_log_message(f"ERROR: {error_msg}\n{traceback.format_exc()}") # Send error to log panel
            # Ensure results dict still has keys even on error
            results = {"spacy": False, "benepar": False, "error": str(e)}
        finally:
            # Ensure finished is always emitted
            self.finished.emit(results)

class InstallDefaultsWorker(QObject):
    """Worker to run setup_models with default settings."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str) # success, final_message
    log_message = pyqtSignal(str) # Signal for detailed log messages

    def _emit_log_message(self, message: str):
        """Emits the log message signal."""
        self.log_message.emit(message.strip())

    @pyqtSlot()
    def run(self):
        success = False
        message = ""
        try:
            self.progress.emit("Starting default model setup...")
            # Assuming setup_models now accepts log_callback and logs internally
            success = setup_models(log_callback=self._emit_log_message) # <<< Pass callback

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
            self._emit_log_message(f"ERROR: {message}\n{traceback.format_exc()}") # Send error to log panel
            success = False
        except Exception as e:
            message = f"An unexpected error occurred during default setup: {e}"
            logging.error(message, exc_info=True)
            self.progress.emit(message)
            self._emit_log_message(f"ERROR: {message}\n{traceback.format_exc()}") # Send error to log panel
            success = False
        finally:
            self.finished.emit(success, message)

class ModelActionWorker(QObject):
    """Worker for installing or uninstalling specific models."""
    progress = pyqtSignal(str) # Message only for progress updates
    finished = pyqtSignal(str, str, bool, str) # action, alias, success, message
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
        
        self.gui_log_handler = None # Attribute to hold the GUI handler instance

    def _emit_log_message(self, message: str):
        """Emits the log message signal."""
        self.log_message.emit(message.strip())

    @pyqtSlot()
    def run(self):
        """Execute the requested model action."""
        success = False
        message = ""
        action_verb = "Installing" if self.action == 'install' else "Uninstalling"
        target_desc = f"{self.model_type} model '{self.alias}'"

        try:
            self.progress.emit(f"Starting {action_verb.lower()} {target_desc}...")

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
                        # Use functions from anpe.utils.setup_models
                        self.progress.emit(f"Calling {self.model_type} install function for {model_name}...")
                         
                        if self.model_type == 'spacy':
                            # Assuming install_spacy_model accepts log_callback
                            success = install_spacy_model(model_name, log_callback=self._emit_log_message) # <<< Pass callback
                        elif self.model_type == 'benepar':
                            # Assuming install_benepar_model accepts log_callback
                            success = install_benepar_model(model_name, log_callback=self._emit_log_message) # <<< Pass callback
 
                        message = f"Successfully installed {self.model_type} model {model_name}." if success else \
                                  f"Failed to install/verify {self.model_type} model {model_name}. Check logs."
                        self.progress.emit(message)
                                       
                    # --- UNINSTALL ACTION --- 
                    elif self.action == 'uninstall':
                        # Use functions from anpe.utils.clean_models 
                        self.progress.emit(f"Calling {self.model_type} uninstall function for {model_name}...")
                        
                        if self.model_type == 'spacy':
                            # Assuming uninstall_spacy_model accepts log_callback
                            success = uninstall_spacy_model(model_name, log_callback=self._emit_log_message) # <<< Pass callback
                        elif self.model_type == 'benepar':
                            # Assuming uninstall_benepar_model accepts log_callback
                            success = uninstall_benepar_model(model_name, log_callback=self._emit_log_message) # <<< Pass callback
                        else:
                             success = False # Should not happen
                             logging.error(f"Unknown model type for uninstall: {self.model_type}")

                        message = f"Successfully uninstalled {self.model_type} model {model_name}." if success else \
                                  f"Failed to uninstall {self.model_type} model {model_name}. Check logs."
                        self.progress.emit(message)
                            
        except ImportError:
            success = False
            message = f"Error: Could not import ANPE core utilities for {self.action}."
            logging.error(message, exc_info=True)
            self.progress.emit(message)
            self._emit_log_message(f"ERROR: {message}\n{traceback.format_exc()}")
        except Exception as e:
            success = False
            message = f"An unexpected error occurred during model action: {e}"
            logging.error(f"Model action worker error: {e}", exc_info=True)
            self.progress.emit(message) # Emit error to status label
            self._emit_log_message(f"FATAL ERROR: {message}\n{traceback.format_exc()}") # Emit error to log
            
        finally:
            self.progress.emit("Operation complete.") # Keep this final generic message
            self.finished.emit(self.action, self.alias, success, message)

# --- NEW WORKER for Status Check ---

class StatusCheckWorker(QObject):
    """Worker to asynchronously check for installed models."""
    finished = pyqtSignal(dict) # Emits {'spacy_models': list, 'benepar_models': list, 'error': str|None}

    def __init__(self, parent=None):
        super().__init__(parent)
        logging.debug("StatusCheckWorker initialized.")

    @pyqtSlot()
    def run(self):
        """Check for installed models."""
        logging.debug("StatusCheckWorker run method started.")
        status_update = {
            'spacy_models': [],
            'benepar_models': [],
            'error': None
        }
        try:
            # Assuming these imports are valid in this context
            from anpe.utils.model_finder import find_installed_spacy_models, find_installed_benepar_models
            status_update['spacy_models'] = find_installed_spacy_models()
            status_update['benepar_models'] = find_installed_benepar_models()
            logging.debug(f"StatusCheckWorker found models: SpaCy={status_update['spacy_models']}, Benepar={status_update['benepar_models']}")
        except ImportError as e:
            error_msg = f"Core ANPE components not found for status check: {e}"
            logging.error(error_msg)
            status_update['error'] = error_msg
        except Exception as e:
            error_msg = f"Error during model status check: {e}"
            logging.error(error_msg, exc_info=True)
            status_update['error'] = error_msg

        logging.debug(f"StatusCheckWorker emitting finished signal with data: {status_update}")
        self.finished.emit(status_update)
        logging.debug("StatusCheckWorker run method finished.")

# --- END NEW WORKER --- 