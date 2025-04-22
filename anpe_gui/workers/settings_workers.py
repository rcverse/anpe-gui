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

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# Constants and Utilities from ANPE Core (Mirroring settings_dialog.py)
CORE_PACKAGE_NAME = "anpe"
try:
    from anpe.utils.setup_models import (
        check_spacy_model, check_benepar_model, check_nltk_models,
        SPACY_MODEL_MAP, BENEPAR_MODEL_MAP, install_nltk_models, install_spacy_model, install_benepar_model,
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
    def check_nltk_models(*args, **kwargs): return False
    def install_nltk_models(*args, **kwargs): return False
    def install_spacy_model(*args, **kwargs): return False
    def install_benepar_model(*args, **kwargs): return False
    def clean_all(*args, **kwargs): return {"spacy": False, "benepar": False, "nltk": False}
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

# --- Worker Objects --- 

class CoreUpdateWorker(QObject):
    """Worker for checking and performing ANPE core updates."""
    check_finished = pyqtSignal(str, str, str) # latest_version, current_version, error_string
    update_progress = pyqtSignal(int, str)    # value (-1 for indeterminate), message
    update_finished = pyqtSignal(bool, str)   # success, message
    
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
        """Run pip install --upgrade anpe."""
        success = False
        message = ""
        try:
            self.update_progress.emit(-1, "Starting update process...") # Indeterminate
            # Ensure pip is available and upgrade it first for robustness
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True, text=True, encoding='utf-8')
            except Exception as pip_e:
                logging.warning(f"Could not upgrade pip: {pip_e}")
            
            # Run the update command
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", CORE_PACKAGE_NAME],
                check=True, # Raise error on failure
                capture_output=True,
                text=True,
                encoding='utf-8' # Explicitly set encoding
            )
            message = f"Update successful!\n\nOutput:\n{result.stdout[-500:]}" # Show last bit of output
            success = True
            self.update_progress.emit(100, "Update complete.")
            
        except subprocess.CalledProcessError as e:
            message = f"Update failed.\n\nError:\n{e.stderr[-500:]}"
            success = False
            self.update_progress.emit(0, "Update failed.")
        except Exception as e:
            message = f"An unexpected error occurred during update: {e}"
            success = False
            self.update_progress.emit(0, "Update failed.")
            
        self.update_finished.emit(success, message)

class CleanWorker(QObject):
    """Worker to run clean_all in a background thread."""
    finished = pyqtSignal(dict) # Return status dictionary from clean_all
    progress = pyqtSignal(str) # To send status updates

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
            self.progress.emit("Cleaning NLTK resources...") # Example stage message
            self.progress.emit("Model cleanup process finished.")
        except Exception as e:
            logging.error(f"Exception during background model cleanup: {e}", exc_info=True)
            self.progress.emit(f"Error during cleanup: {e}")
            # Ensure results dict still has keys even on error
            results = {"spacy": False, "benepar": False, "nltk": False}
        finally:
            # Ensure finished is always emitted
            self.finished.emit(results)

class InstallDefaultsWorker(QObject):
    """Worker to run setup_models with default settings."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str) # success, final_message

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
    
    def __init__(self, action: str, model_type: str, alias: str = None):
        """
        Initialize the worker.
        
        Args:
            action: Either "install" or "uninstall"
            model_type: One of "spacy", "benepar", or "nltk"
            alias: The model alias (e.g., "md", "lg", "default"), None for NLTK
        """
        super().__init__()
        self.action = action
        self.model_type = model_type
        self.alias = alias
        
    @pyqtSlot()
    def run(self):
        """Execute the requested model action."""
        success = False
        message = ""
        action_verb = "Installing" if self.action == 'install' else "Uninstalling"
        target_desc = f"{self.model_type} model{f' {self.alias}' if self.alias else ' resources'}"

        try:
            self.progress.emit(f"Starting {action_verb.lower()} {target_desc}...")

            # Import necessary functions from setup_models - relies on imports at top now
            # from anpe.utils.setup_models import install_nltk_models, install_spacy_model, install_benepar_model

            # Handle NLTK models specially
            if self.model_type == 'nltk':
                if self.action == 'install':
                    try:
                        self.progress.emit("Downloading NLTK resources...") # More specific message
                        success = install_nltk_models()
                        if success:
                            message = "NLTK resources successfully installed."
                        else:
                            message = "Failed to install NLTK resources. Check logs."
                    except Exception as e:
                        message = f"Failed to install NLTK resources: {e}"
                        success = False
                elif self.action == 'uninstall':
                    try:
                        self.progress.emit("Removing NLTK resources...") # More specific
                        # Try to find and remove punkt resources
                        try:
                            punkt_path = nltk.data.find('tokenizers/punkt')
                            if os.path.exists(punkt_path):
                                if os.path.isdir(punkt_path):
                                    shutil.rmtree(punkt_path)
                                else:
                                    os.remove(punkt_path)
                            # Handle punkt_tab too - REMOVED DUPLICATE PROGRESS EMIT
                            punkt_tab_path = nltk.data.find('tokenizers/punkt_tab')
                            if os.path.exists(punkt_tab_path):
                                if os.path.isdir(punkt_tab_path):
                                    shutil.rmtree(punkt_tab_path)
                                else:
                                    os.remove(punkt_tab_path)
                            # Verify removal after attempting
                            success = not check_nltk_models(['punkt', 'punkt_tab'])
                            if success:
                                message = "NLTK resources successfully uninstalled."
                            else:
                                message = "Could not confirm removal of all NLTK resources." # Updated message
                        except (LookupError, OSError, IOError) as e:
                            message = f"Error removing NLTK resources: {e}"
                            success = False
                    except Exception as e:
                        message = f"Failed to uninstall NLTK resources: {e}"
                        success = False
            # Handle spaCy and Benepar models
            else:
                if not self.alias:
                    message = f"Missing alias for {self.model_type} model action."
                    success = False
                else:
                    # Get the full model name from the alias
                    model_map = SPACY_MODEL_MAP if self.model_type == 'spacy' else BENEPAR_MODEL_MAP
                    model_name = model_map.get(self.alias)
                    
                    if not model_name:
                        message = f"Unknown {self.model_type} model alias: {self.alias}"
                        success = False
                    else:
                        if self.action == 'install':
                            try:
                                self.progress.emit(f"Downloading {self.model_type} model {model_name}...") # More specific
                                if self.model_type == 'spacy':
                                    success = install_spacy_model(model_name=model_name)
                                elif self.model_type == 'benepar':
                                    success = install_benepar_model(model_name=model_name)
                                
                                if success:
                                    message = f"Successfully installed {self.model_type} model {model_name}."
                                else:
                                    message = f"Failed to install {self.model_type} model {model_name}. Check logs."
                            except Exception as e:
                                message = f"Failed to install {model_name}: {e}"
                                success = False

                        elif self.action == 'uninstall':
                            self.progress.emit(f"Attempting to uninstall {self.model_type} model {model_name}...")
                            if self.model_type == 'spacy':
                                success = True  # Will be set to False if any step fails
                                self.progress.emit(f"Attempting to uninstall spaCy model {model_name}...")
                                
                                # Check if the model is installed before proceeding
                                installed_models = find_installed_spacy_models()
                                if model_name not in installed_models:
                                    message = f"spaCy model {model_name} is not installed."
                                    success = True  # Not an error, the model is already not installed
                                else:
                                    # 1. Try pip uninstall
                                    try:
                                        self.progress.emit(f"Running pip uninstall {model_name}...") # More specific
                                        result = subprocess.run(
                                            [sys.executable, "-m", "pip", "uninstall", "-y", model_name],
                                            check=False, capture_output=True, text=True, encoding='utf-8'
                                        )
                                        # Check both return code and stderr for confirmation
                                        if result.returncode != 0 and "successfully uninstalled" not in result.stdout.lower() and "not installed" not in result.stderr.lower():
                                            self.progress.emit(f"Pip uninstall may have failed: {result.stderr.strip()}")
                                            # Don't set success = False here, rely on final check
                                    except Exception as e:
                                        self.progress.emit(f"Error running pip uninstall: {e}")
                                        # Don't set success = False here, rely on final check
                                    
                                    # 2. Try removing from spaCy data directory (if available)
                                    try:
                                        data_path = spacy.util.get_data_path()
                                        if data_path and os.path.exists(data_path):
                                            model_path = os.path.join(data_path, model_name)
                                            # Also check linked paths like en_core_web_md -> en_core_web_md-x.y.z
                                            model_link_path = os.path.join(data_path, model_name.replace("-", "_")) # Check link name too

                                            paths_to_remove = []
                                            if os.path.exists(model_path):
                                                paths_to_remove.append(model_path)
                                            if os.path.islink(model_link_path) and os.path.exists(model_link_path):
                                                # Follow link to check if it points to our target before removing link
                                                try:
                                                    resolved_link = os.path.realpath(model_link_path)
                                                    # Need to check if resolved path contains the target model version directory
                                                    # This is complex, maybe just remove link if it exists
                                                    # For now, just add the link path for removal
                                                    paths_to_remove.append(model_link_path)
                                                except Exception as link_e:
                                                    logging.warning(f"Could not resolve link {model_link_path}: {link_e}")

                                            for path_to_remove in set(paths_to_remove):
                                                try:
                                                    self.progress.emit(f"Removing model path: {path_to_remove}...")
                                                    if os.path.isdir(path_to_remove):
                                                        shutil.rmtree(path_to_remove)
                                                    else:
                                                        os.remove(path_to_remove)
                                                    self.progress.emit(f"Removed model path: {path_to_remove}")
                                                except Exception as e:
                                                    self.progress.emit(f"Failed to remove {path_to_remove}: {e}")
                                                    # Don't set success = False here, rely on final check
                                    except Exception as e:
                                        self.progress.emit(f"Could not access or process spaCy data directory: {e}")
                                
                                    # Final check using check_spacy_model
                                    if not check_spacy_model(model_name):
                                        message = f"Successfully uninstalled {self.model_type} model {model_name}."
                                        success = True
                                    else:
                                        message = f"Failed to completely uninstall {model_name}. It may still be available. Manual check/removal might be needed."
                                        success = False
                                
                            elif self.model_type == 'benepar':
                                success = True
                                found_something = False
                                
                                # Check if the model is installed before proceeding
                                installed_models = find_installed_benepar_models()
                                if model_name not in installed_models:
                                    message = f"Benepar model {model_name} is not installed."
                                    success = True  # Not an error
                                else:
                                    try:
                                        paths_to_remove = []
                                        # Use nltk.data to find the model directory
                                        try:
                                            self.progress.emit(f"Checking NLTK path for {model_name} directory...")
                                            model_dir_path = nltk.data.find(f'models/{model_name}')
                                            if os.path.exists(model_dir_path):
                                                found_something = True
                                                paths_to_remove.append(model_dir_path)
                                        except LookupError:
                                            self.progress.emit(f"Could not find models/{model_name} directory using nltk.data.find")

                                        # Also check for zip files in NLTK paths
                                        nltk_paths = nltk.data.path
                                        for nltk_path in set(nltk_paths):  # Use set to avoid duplicates
                                            if not os.path.isdir(nltk_path):
                                                continue
                                            models_dir = os.path.join(nltk_path, "models")
                                            if not os.path.isdir(models_dir):
                                                continue
                                                
                                            zip_path = os.path.join(models_dir, model_name + ".zip")
                                            if os.path.exists(zip_path):
                                                found_something = True
                                                paths_to_remove.append(zip_path)
                                        
                                        # Attempt removal
                                        if not paths_to_remove:
                                            self.progress.emit(f"No specific paths found for {model_name} in NLTK directories.")
                                            # Might still be installed but not found by these methods
                                        else:
                                            for path_to_remove in set(paths_to_remove):
                                                self.progress.emit(f"Removing path: {path_to_remove}")
                                                try:
                                                    if os.path.isdir(path_to_remove):
                                                        shutil.rmtree(path_to_remove)
                                                    elif os.path.isfile(path_to_remove):
                                                        os.remove(path_to_remove)
                                                except Exception as e:
                                                    self.progress.emit(f"Failed to remove {path_to_remove}: {e}")
                                                    # Don't set success = False, rely on final check
                                        
                                        # Final check
                                        if not check_benepar_model(model_name):
                                            if found_something or not installed_models: # If we removed something OR it wasn't listed as installed initially
                                                 message = f"Successfully uninstalled {self.model_type} model {model_name}."
                                                 success = True
                                            else:
                                                 # It was listed as installed, but we didn't find paths to remove, yet check says it's gone.
                                                 message = f"Model {model_name} is no longer detected, but specific files were not found for removal."
                                                 success = True
                                        else:
                                            message = f"Failed to completely uninstall {model_name}. It may still be available."
                                            success = False
                                            
                                    except Exception as e:
                                        message = f"Error uninstalling Benepar model: {e}"
                                        success = False
                            
        except Exception as e:
            success = False
            message = f"An unexpected error occurred: {e}"
            logging.error(f"Model action worker error: {e}", exc_info=True)

        self.progress.emit("Operation complete.") # Keep this final generic message
        self.finished.emit(success, message) 