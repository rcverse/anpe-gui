"""
Dialog for managing ANPE settings, including core updates, 
model usage preferences, and model installation/management.
"""

import anpe
import sys
import logging
import nltk # Need nltk for the status check part (will move to page)
import importlib.metadata # For getting core version
import subprocess # For core update
import urllib.request # For checking latest core version
import json # For parsing PyPI response

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot, QSize, QSettings, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QGridLayout, QProgressBar, QMessageBox, QWidget, QSpacerItem, QSizePolicy,
    QApplication, QFrame, QStackedWidget, QListWidget, QListWidgetItem, 
    QSplitter, QFormLayout, QComboBox
)
from PyQt6.QtGui import QIcon, QPixmap

from anpe_gui.theme import ERROR_COLOR, PRIMARY_COLOR, get_scroll_bar_style, LIGHT_HOVER_BLUE # Import theme elements
from anpe_gui.resource_manager import ResourceManager # ADDED THIS IMPORT
# from anpe_gui.setup_wizard import SetupWizard # No longer needed here

# Assuming these utilities exist and work as expected
# (We will need more specific imports later in the page widgets)
try:
    from anpe.utils.setup_models import (
        check_spacy_model, check_benepar_model, check_nltk_models, setup_models,
        SPACY_MODEL_MAP, BENEPAR_MODEL_MAP, install_nltk_models, install_spacy_model, install_benepar_model # Import maps and new functions
    )
    from anpe.utils.clean_models import clean_all
    from anpe.utils.model_finder import (
        find_installed_spacy_models, find_installed_benepar_models,
        select_best_spacy_model, select_best_benepar_model
    )
    CORE_PACKAGE_NAME = "anpe" # Define the package name
    # ANPE_AVAILABLE = True # Removed: Assume core is always available for this dialog
except ImportError as e:
    logging.error(f"Failed to import ANPE utilities for Settings Dialog: {e}")
    # ANPE_AVAILABLE = False # Removed
    # Define dummy maps and functions if core package is missing
    # These remain useful for displaying model names even if install/check fails
    SPACY_MODEL_MAP = {"sm": "en_core_web_sm", "md": "en_core_web_md", "lg": "en_core_web_lg", "trf": "en_core_web_trf"} # Keep dummies for UI display
    BENEPAR_MODEL_MAP = {"default": "benepar_en3", "large": "benepar_en3_large"} # Keep dummies for UI display
    CORE_PACKAGE_NAME = "anpe"
    def check_spacy_model(*args, **kwargs): return False
    def check_benepar_model(*args, **kwargs): return False
    def check_nltk_models(*args, **kwargs): return False
    def setup_models(*args, **kwargs): return False
    def clean_all(*args, **kwargs): return {}
    def find_installed_spacy_models(): return []
    def find_installed_benepar_models(): return []
    def select_best_spacy_model(l): return None
    def select_best_benepar_model(l): return None
    class DummyNLTKData:
        def find(self, path): raise LookupError()
    class DummyNLTK: data = DummyNLTKData()
    nltk = DummyNLTK()


# --- Worker Objects --- 
# (These will be used by the page widgets)

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
            with urllib.request.urlopen(pypi_url, timeout=10) as response:
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
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)
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
            # clean_all now handles logging internally
            # We just capture the results dictionary
            results = clean_all() # Removed logger passing
            self.progress.emit("Model cleanup process finished.")
        except Exception as e:
            logging.error(f"Exception during background model cleanup: {e}", exc_info=True)
            self.progress.emit(f"Error during cleanup: {e}")
            # Ensure results dict still has keys even on error
            results = {"spacy": False, "benepar": False, "nltk": False} 
        finally:
            # Ensure finished is always emitted
            self.finished.emit(results)


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
        
        try:
            self.progress.emit(f"Starting {self.action} for {self.model_type} model{f' {self.alias}' if self.alias else ''}...")
            
            # Import necessary functions from setup_models
            from anpe.utils.setup_models import install_nltk_models, install_spacy_model, install_benepar_model

            # Handle NLTK models specially
            if self.model_type == 'nltk':
                if self.action == 'install':
                    try:
                        # Use the dedicated install function from setup_models
                        success = install_nltk_models()
                        if success:
                            message = "NLTK resources successfully installed."
                        else:
                            message = "Failed to install NLTK resources. Check logs."
                    except Exception as e:
                        message = f"Failed to install NLTK resources: {e}"
                        success = False
                elif self.action == 'uninstall':
                    # Uninstallation logic for NLTK remains here as it's simpler
                    try:
                        import nltk.data
                        # Try to find and remove punkt resources
                        try:
                            punkt_path = nltk.data.find('tokenizers/punkt')
                            import shutil, os
                            if os.path.exists(punkt_path):
                                if os.path.isdir(punkt_path):
                                    shutil.rmtree(punkt_path)
                                else:
                                    os.remove(punkt_path)
                            # Handle punkt_tab too
                            punkt_tab_path = nltk.data.find('tokenizers/punkt_tab')
                            if os.path.exists(punkt_tab_path):
                                if os.path.isdir(punkt_tab_path):
                                    shutil.rmtree(punkt_tab_path)
                                else:
                                    os.remove(punkt_tab_path)
                            success = not check_nltk_models(['punkt', 'punkt_tab'])
                            message = "NLTK resources successfully uninstalled."
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
                                if self.model_type == 'spacy':
                                    # Use the dedicated install function from setup_models
                                    success = install_spacy_model(model_name=model_name)
                                elif self.model_type == 'benepar':
                                    # Use the dedicated install function from setup_models
                                    success = install_benepar_model(model_name=model_name)
                                
                                if success:
                                    message = f"Successfully installed {self.model_type} model {model_name}."
                                else:
                                    message = f"Failed to install {self.model_type} model {model_name}. Check logs."
                            except Exception as e:
                                message = f"Failed to install {model_name}: {e}"
                                success = False

                        elif self.action == 'uninstall':
                            # Uninstallation logic remains the same (as it was already implemented here)
                            if self.model_type == 'spacy':
                                # Use subprocess to run pip uninstall for spaCy models
                                import subprocess
                                import sys
                                import spacy
                                import shutil
                                
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
                                        result = subprocess.run(
                                            [sys.executable, "-m", "pip", "uninstall", "-y", model_name],
                                            check=False, capture_output=True, text=True
                                        )
                                        if result.returncode != 0 and "not installed" not in result.stderr.lower():
                                            self.progress.emit(f"Pip uninstall failed: {result.stderr.strip()}")
                                            success = False
                                    except Exception as e:
                                        self.progress.emit(f"Error running pip uninstall: {e}")
                                        success = False
                                    
                                    # 2. Try removing from spaCy data directory
                                    try:
                                        data_path = spacy.util.get_data_path()
                                        if data_path and os.path.exists(data_path):
                                            model_path = os.path.join(data_path, model_name)
                                            if os.path.exists(model_path):
                                                try:
                                                    if os.path.isdir(model_path):
                                                        shutil.rmtree(model_path)
                                                    else:
                                                        os.remove(model_path)
                                                    self.progress.emit(f"Removed model from data directory: {model_path}")
                                                except Exception as e:
                                                    self.progress.emit(f"Failed to remove from data directory: {e}")
                                                    success = False
                                    except Exception as e:
                                        self.progress.emit(f"Could not access spaCy data directory: {e}")
                                        # Don't mark as failure if we just couldn't check
                                
                                # Final check
                                if not check_spacy_model(model_name):
                                    message = f"Successfully uninstalled {self.model_type} model {model_name}."
                                else:
                                    message = f"Failed to completely uninstall {model_name}. It may still be available."
                                    success = False
                                
                            elif self.model_type == 'benepar':
                                # For Benepar, find and remove the model files using model_finder utility
                                import os
                                import shutil
                                
                                success = True
                                found_something = False
                                
                                # Check if the model is installed before proceeding
                                installed_models = find_installed_benepar_models()
                                if model_name not in installed_models:
                                    message = f"Benepar model {model_name} is not installed."
                                    success = True  # Not an error, the model is already not installed
                                else:
                                    try:
                                        # Use nltk.data to find the model
                                        try:
                                            # Get the path directly from nltk.data.find
                                            import nltk
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
                                                    success = False
                                        except LookupError:
                                            self.progress.emit(f"Could not find models/{model_name} using nltk.data.find")
                                            # Continue to look with alternative methods

                                        # Also check for zip files in NLTK paths
                                        import nltk
                                        nltk_paths = nltk.data.path
                                        for nltk_path in set(nltk_paths):  # Use set to avoid duplicates
                                            models_dir = os.path.join(nltk_path, "models")
                                            if not os.path.isdir(models_dir):
                                                continue
                                                
                                            # Check for zip file
                                            zip_path = os.path.join(models_dir, model_name + ".zip")
                                            if os.path.exists(zip_path):
                                                found_something = True
                                                self.progress.emit(f"Removing zip file: {zip_path}")
                                                try:
                                                    os.remove(zip_path)
                                                except Exception as e:
                                                    self.progress.emit(f"Failed to remove zip file {zip_path}: {e}")
                                                    success = False
                                        
                                        # Final check
                                        if not check_benepar_model(model_name):
                                            if found_something:
                                                message = f"Successfully uninstalled {self.model_type} model {model_name}."
                                            else:
                                                message = f"Model {model_name} was not found in known locations."
                                                # Still consider it success since the model is not present
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
            
        self.progress.emit("Operation complete.")
        self.finished.emit(success, message)


# --- Page Widgets Implementation ---

class ModelsPage(QWidget):
    """Page for model usage settings and installation/management."""
    # Signals to notify the parent dialog (and potentially main window)
    models_changed = pyqtSignal() 
    model_usage_changed = pyqtSignal()

    def __init__(self, parent=None, initial_model_status=None):
        super().__init__(parent)
        logging.debug(f"ModelsPage.__init__: Received initial_model_status = {initial_model_status}") # LOGGING
        self.setObjectName("ModelsPage")
        self.settings = QSettings("rcverse", "ANPE_GUI") # For usage persistence
        self.initial_model_status = initial_model_status # Store initial status
        
        # Store refs to status labels - these will be created in setup_ui
        self.spacy_status_label = None
        self.spacy_aliases_label = None
        self.benepar_status_label = None
        self.benepar_aliases_label = None
        self.nltk_status_label = None
        
        self.install_worker_thread = None
        self.install_worker = None
        self.clean_worker_thread = None
        self.clean_worker = None
        
        self.status_labels = {} # key: full_model_name, value: QLabel
        
        # Metadata for manageable models (Updated descriptions and sizes)
        self.manageable_models = [
            {'type': 'spacy', 'alias': 'sm', 'name': SPACY_MODEL_MAP.get('sm'), 'desc': 'Small (~12MB): Fast, lower accuracy.'}, # Added (default)
            {'type': 'spacy', 'alias': 'md', 'name': SPACY_MODEL_MAP.get('md'), 'desc': 'Medium (~40MB): Good balance (default).'}, 
            {'type': 'spacy', 'alias': 'lg', 'name': SPACY_MODEL_MAP.get('lg'), 'desc': 'Large (~560MB): Best accuracy.'}, 
            {'type': 'spacy', 'alias': 'trf', 'name': SPACY_MODEL_MAP.get('trf'), 'desc': 'Transformer-based (~430MB): State-of-the-art.'}, 
            {'type': 'benepar', 'alias': 'default', 'name': BENEPAR_MODEL_MAP.get('default'), 'desc': 'Standard model (~63MB) T5-small based. (default)'}, # Updated Benepar
            {'type': 'benepar', 'alias': 'large', 'name': BENEPAR_MODEL_MAP.get('large'), 'desc': 'Large model (~208 MB) T5-large based. Higher accuracy.'}, # Updated Benepar
        ]
        # Filter out models if map didn't contain the alias (shouldn't happen with default maps)
        self.manageable_models = [m for m in self.manageable_models if m.get('name')] 
        
        self.action_buttons = {} # key: alias, value: QPushButton
        self.nltk_action_button = None # Button for NLTK actions
        
        self.setup_ui()
        self.connect_signals()
        
        # Update UI using the initial status passed from MainWindow
        if self.initial_model_status:
            logging.debug("ModelsPage: Applying initial status to UI.")
            self._update_ui_from_status(self.initial_model_status)
        else:
            # Fallback if no status was passed (should not happen ideally)
            logging.warning("ModelsPage: No initial status received, performing initial refresh.")
            QTimer.singleShot(100, self.refresh_status) # Perform a check if no data

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)  # Reduced margins
        main_layout.setSpacing(10)  # Spacing between groups

        # --- Model Usage Settings --- 
        usage_group = QGroupBox("Model Usage Preferences")
        usage_layout = QFormLayout(usage_group)
        usage_layout.setSpacing(8)
        usage_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        usage_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.spacy_usage_combo = QComboBox()
        self.spacy_usage_combo.setToolTip("Select the spaCy model ANPE should use.\n'(Auto-detect)' uses the best available installed model.")
        self.spacy_usage_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # Set size policy
        self.benepar_usage_combo = QComboBox()
        self.benepar_usage_combo.setToolTip("Select the Benepar model ANPE should use.\n'(Auto-detect)' uses the best available installed model.")
        self.benepar_usage_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # Set size policy
        
        usage_layout.addRow("Use spaCy Model:", self.spacy_usage_combo)
        usage_layout.addRow("Use Benepar Model:", self.benepar_usage_combo)
        
        # --- Add Explanations --- 
        explanation_style = "font-size: 9pt; color: #666; padding-top: 5px;" # Style for explanation labels
        
        spacy_explanation_label = QLabel(
            "spaCy models handle sentence segmentation and initial structural analysis. "
            "Smaller models (e.g., 'sm') are faster but less accurate. Larger models ('lg', 'trf') "
            "offer higher accuracy but require more resources."
        )
        spacy_explanation_label.setWordWrap(True)
        spacy_explanation_label.setStyleSheet(explanation_style)
        # Add explanation spanning both columns of the form layout
        usage_layout.addRow(spacy_explanation_label) 
        
        benepar_explanation_label = QLabel(
             "Benepar models perform detailed constituent parsing. The 'large' model generally provides "
             "higher accuracy but significantly increases processing time and memory usage."
        )
        benepar_explanation_label.setWordWrap(True)
        benepar_explanation_label.setStyleSheet(explanation_style)
        # Add explanation spanning both columns
        usage_layout.addRow(benepar_explanation_label)
        # --------------------------

        main_layout.addWidget(usage_group)

        # --- Model Installation & Management --- 
        management_group = QGroupBox("Manage Models / Resources")
        management_layout = QVBoxLayout(management_group)
        management_layout.setContentsMargins(10, 10, 10, 10) # Padding inside group
        management_layout.setSpacing(8) # Spacing within group

        # --- Model Management Grid Widget ---
        management_grid_widget = QWidget()
        grid_layout = QGridLayout(management_grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0) # No internal margins for grid itself
        grid_layout.setHorizontalSpacing(15)
        grid_layout.setVerticalSpacing(6)  # Compact vertical spacing

        # Column Stretches
        grid_layout.setColumnStretch(0, 1)  # Model name
        grid_layout.setColumnStretch(1, 2)  # Description
        grid_layout.setColumnStretch(2, 0)  # Button (fixed)

        # Styles
        header_style = f"font-size: 11pt; color: {PRIMARY_COLOR}; font-weight: bold; margin-top: 6px; margin-bottom: 3px;"
        status_style = "font-size: 9pt; color: #555; margin-left: 8px;" # Style for status text
        model_name_style = "font-family: monospace; font-size: 10pt; color: #333;"
        desc_style = "color: #555; font-size: 9pt;"
        subheader_style = "font-size: 9pt; font-weight: bold; color: #444;" # Subheader style

        current_row = 0

        # --- spaCy Section --- 
        spacy_header_widget = QWidget()
        spacy_header_layout = QHBoxLayout(spacy_header_widget)
        spacy_header_layout.setContentsMargins(0,0,0,0)
        spacy_header_layout.setSpacing(5)
        spacy_header_label = QLabel("spaCy MODELS")
        spacy_header_label.setStyleSheet(header_style)
        self.spacy_status_label = QLabel("(Checking status...)") # Status label here
        self.spacy_status_label.setStyleSheet(status_style)
        spacy_header_layout.addWidget(spacy_header_label)
        spacy_header_layout.addWidget(self.spacy_status_label)
        spacy_header_layout.addStretch()
        grid_layout.addWidget(spacy_header_widget, current_row, 0, 1, 3) 
        current_row += 1

        # Subheaders (REMOVED)
        # subheader_name_spacy = QLabel("Model Name")
        # subheader_name_spacy.setStyleSheet(subheader_style)
        # subheader_desc_spacy = QLabel("Description")
        # subheader_desc_spacy.setStyleSheet(subheader_style)
        # grid_layout.addWidget(subheader_name_spacy, current_row, 0)
        # grid_layout.addWidget(subheader_desc_spacy, current_row, 1)
        # current_row += 1

        # spaCy Models
        for model_info in [m for m in self.manageable_models if m['type'] == 'spacy']:
            name_label = QLabel(model_info['name'])
            name_label.setStyleSheet(model_name_style)
            desc_label = QLabel(model_info['desc'])
            desc_label.setStyleSheet(desc_style)
            desc_label.setWordWrap(True)
            action_button = QPushButton("Checking...")
            action_button.setFixedWidth(80) # Reduced width
            action_button.setFixedHeight(24)
            action_button.setProperty("model_alias", model_info['alias'])
            action_button.setProperty("model_type", model_info['type'])
            action_button.clicked.connect(self.run_model_action)
            
            grid_layout.addWidget(name_label, current_row, 0, Qt.AlignmentFlag.AlignVCenter)
            grid_layout.addWidget(desc_label, current_row, 1, Qt.AlignmentFlag.AlignVCenter)
            grid_layout.addWidget(action_button, current_row, 2, Qt.AlignmentFlag.AlignCenter)
            self.action_buttons[model_info['alias']] = action_button
            current_row += 1

        # Separator
        separator_spacy = QFrame()
        separator_spacy.setFrameShape(QFrame.Shape.HLine)
        separator_spacy.setFixedHeight(1)
        separator_spacy.setStyleSheet("background-color: #e0e0e0; margin-top: 5px; margin-bottom: 5px;")
        grid_layout.addWidget(separator_spacy, current_row, 0, 1, 3)
        current_row += 1

        # --- Benepar Section --- 
        benepar_header_widget = QWidget()
        benepar_header_layout = QHBoxLayout(benepar_header_widget)
        benepar_header_layout.setContentsMargins(0,0,0,0)
        benepar_header_layout.setSpacing(5)
        benepar_header_label = QLabel("Benepar MODELS")
        benepar_header_label.setStyleSheet(header_style)
        self.benepar_status_label = QLabel("(Checking status...)") # Status label here
        self.benepar_status_label.setStyleSheet(status_style)
        benepar_header_layout.addWidget(benepar_header_label)
        benepar_header_layout.addWidget(self.benepar_status_label)
        benepar_header_layout.addStretch()
        grid_layout.addWidget(benepar_header_widget, current_row, 0, 1, 3) 
        current_row += 1

        # Subheaders (REMOVED)
        # subheader_name_benepar = QLabel("Model Name")
        # subheader_name_benepar.setStyleSheet(subheader_style)
        # subheader_desc_benepar = QLabel("Description")
        # subheader_desc_benepar.setStyleSheet(subheader_style)
        # grid_layout.addWidget(subheader_name_benepar, current_row, 0)
        # grid_layout.addWidget(subheader_desc_benepar, current_row, 1)
        # current_row += 1

        # Benepar Models
        for model_info in [m for m in self.manageable_models if m['type'] == 'benepar']:
            name_label = QLabel(model_info['name'])
            name_label.setStyleSheet(model_name_style)
            desc_label = QLabel(model_info['desc'])
            desc_label.setStyleSheet(desc_style)
            desc_label.setWordWrap(True)
            action_button = QPushButton("Checking...")
            action_button.setFixedWidth(80)
            action_button.setFixedHeight(24)
            action_button.setProperty("model_alias", model_info['alias'])
            action_button.setProperty("model_type", model_info['type'])
            # Removed setStyleSheet here
            action_button.clicked.connect(self.run_model_action)
            
            grid_layout.addWidget(name_label, current_row, 0, Qt.AlignmentFlag.AlignVCenter)
            grid_layout.addWidget(desc_label, current_row, 1, Qt.AlignmentFlag.AlignVCenter)
            grid_layout.addWidget(action_button, current_row, 2, Qt.AlignmentFlag.AlignCenter)
            self.action_buttons[model_info['alias']] = action_button
            current_row += 1

        # Separator
        separator_benepar = QFrame()
        separator_benepar.setFrameShape(QFrame.Shape.HLine)
        separator_benepar.setFixedHeight(1)
        separator_benepar.setStyleSheet("background-color: #e0e0e0; margin-top: 5px; margin-bottom: 5px;")
        grid_layout.addWidget(separator_benepar, current_row, 0, 1, 3)
        current_row += 1

        # --- NLTK Section --- 
        nltk_header_widget = QWidget()
        nltk_header_layout = QHBoxLayout(nltk_header_widget)
        nltk_header_layout.setContentsMargins(0,0,0,0)
        nltk_header_layout.setSpacing(5)
        nltk_header_label = QLabel("NLTK RESOURCES")
        nltk_header_label.setStyleSheet(header_style)
        self.nltk_status_label = QLabel("(Checking status...)") # Status label here
        self.nltk_status_label.setStyleSheet(status_style)
        nltk_header_layout.addWidget(nltk_header_label)
        nltk_header_layout.addWidget(self.nltk_status_label)
        nltk_header_layout.addStretch()
        grid_layout.addWidget(nltk_header_widget, current_row, 0, 1, 3) 
        current_row += 1

        # Subheaders (REMOVED)
        # subheader_name_nltk = QLabel("Resources")
        # subheader_name_nltk.setStyleSheet(subheader_style)
        # subheader_desc_nltk = QLabel("Description")
        # subheader_desc_nltk.setStyleSheet(subheader_style)
        # grid_layout.addWidget(subheader_name_nltk, current_row, 0)
        # grid_layout.addWidget(subheader_desc_nltk, current_row, 1)
        # current_row += 1

        # NLTK Resources
        nltk_name_label = QLabel("punkt, punkt_tab")
        nltk_name_label.setStyleSheet(model_name_style)
        
        nltk_desc_label = QLabel("Required sentence tokenizers (~40MB)") # Added size
        nltk_desc_label.setStyleSheet(desc_style)
        nltk_desc_label.setWordWrap(True)
        self.nltk_action_button = QPushButton("Checking...")
        self.nltk_action_button.setFixedWidth(80) # Reduced width
        self.nltk_action_button.setFixedHeight(24)
        self.nltk_action_button.setProperty("model_type", "nltk")
        self.nltk_action_button.clicked.connect(self.run_model_action)
        
        grid_layout.addWidget(nltk_name_label, current_row, 0, Qt.AlignmentFlag.AlignVCenter)
        grid_layout.addWidget(nltk_desc_label, current_row, 1, Qt.AlignmentFlag.AlignVCenter)
        grid_layout.addWidget(self.nltk_action_button, current_row, 2, Qt.AlignmentFlag.AlignCenter)
        current_row += 1

        management_layout.addWidget(management_grid_widget) # Add grid to the group layout

        # --- Progress/Feedback & Global Actions Row ---
        # Separator before actions
        separator_actions = QFrame()
        separator_actions.setFrameShape(QFrame.Shape.HLine)
        separator_actions.setFixedHeight(1)
        separator_actions.setStyleSheet("background-color: #d0d0d0; margin-top: 8px; margin-bottom: 6px;") # Slightly darker
        management_layout.addWidget(separator_actions)

        feedback_actions_layout = QHBoxLayout()
        feedback_actions_layout.setContentsMargins(0, 0, 0, 0) 
        feedback_actions_layout.setSpacing(10) 

        # Feedback Area (Status Label + Progress Bar)
        feedback_widget = QWidget()
        feedback_layout = QVBoxLayout(feedback_widget)
        feedback_layout.setContentsMargins(0,0,0,0)
        feedback_layout.setSpacing(3)
        self.model_action_status_label = QLabel("Status updated.")
        self.model_action_status_label.setWordWrap(True)
        self.model_action_status_label.setStyleSheet("color: #666; font-style: italic; font-size: 9pt;") 
        self.model_action_progress = QProgressBar()
        self.model_action_progress.setVisible(False)
        self.model_action_progress.setTextVisible(False)
        self.model_action_progress.setFixedHeight(6) # Even smaller progress bar
        self.model_action_progress.setStyleSheet(f""" QProgressBar {{ border: 1px solid #ccc; border-radius: 2px; background-color: #f5f5f5; }} QProgressBar::chunk {{ background-color: {PRIMARY_COLOR}; }} """)
        feedback_layout.addWidget(self.model_action_status_label)
        feedback_layout.addWidget(self.model_action_progress)
        feedback_actions_layout.addWidget(feedback_widget, 1) # Feedback takes expanding space

        # Global Action Buttons (Refresh, Clean)
        self.refresh_button = QPushButton("Refresh Status")
        self.refresh_button.setFixedHeight(26)
        # Removed setStyleSheet here - uses global theme
        
        self.clean_button = QPushButton("Clean All") # Shorter text
        self.clean_button.setFixedWidth(80) # Reduced width
        self.clean_button.setFixedHeight(26)
        self.clean_button.setProperty("danger", True) # Apply danger style (now outline)
        self.clean_button.setToolTip("Clean All ANPE-related Models")
        
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0,0,0,0)
        button_layout.setSpacing(8)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.clean_button)

        feedback_actions_layout.addWidget(button_widget) # Add buttons container (fixed size)
        management_layout.addLayout(feedback_actions_layout) # Add actions layout to group

        main_layout.addWidget(management_group) # Add management group to main layout
        main_layout.addStretch(1) # Push content up 

        # NOTE: Initial UI update is now called from __init__ after setup_ui completes

    def connect_signals(self):
        # Usage settings
        self.spacy_usage_combo.currentTextChanged.connect(self.save_usage_settings)
        self.benepar_usage_combo.currentTextChanged.connect(self.save_usage_settings)
        # Management actions
        self.refresh_button.clicked.connect(self.refresh_status)
        self.clean_button.clicked.connect(self.run_clean)

    def load_usage_settings(self):
        """Load saved model usage preferences and set combo boxes.
        Must be called AFTER _update_usage_combos populates the items.
        """
        logging.debug(f"Attempting to load usage settings. Settings file: {self.settings.fileName()}")
        spacy_pref = self.settings.value("modelUsage/spacyModel", "(Auto-detect)")
        benepar_pref = self.settings.value("modelUsage/beneparModel", "(Auto-detect)")
        logging.debug(f"  Read from QSettings: spaCy='{spacy_pref}', Benepar='{benepar_pref}'")
        
        # Log current items in combo boxes for debugging
        spacy_items = [self.spacy_usage_combo.itemText(i) for i in range(self.spacy_usage_combo.count())]
        benepar_items = [self.benepar_usage_combo.itemText(i) for i in range(self.benepar_usage_combo.count())]
        logging.debug(f"  Current spaCy combo items: {spacy_items}")
        logging.debug(f"  Current Benepar combo items: {benepar_items}")

        # Check if saved preference is actually in the current list of items
        spacy_index = self.spacy_usage_combo.findText(spacy_pref)
        if spacy_index != -1:
            self.spacy_usage_combo.setCurrentIndex(spacy_index)
        else:
            self.spacy_usage_combo.setCurrentIndex(0) # Default to (Auto-detect)
            if spacy_pref != "(Auto-detect)":
                logging.warning(f"Saved spaCy usage preference '{spacy_pref}' not found among installed models. Using Auto-detect.")

        benepar_index = self.benepar_usage_combo.findText(benepar_pref)
        if benepar_index != -1:
            self.benepar_usage_combo.setCurrentIndex(benepar_index)
        else:
            self.benepar_usage_combo.setCurrentIndex(0) # Default to (Auto-detect)
            if benepar_pref != "(Auto-detect)":
                logging.warning(f"Saved Benepar usage preference '{benepar_pref}' not found among installed models. Using Auto-detect.")

        logging.debug(f"Loaded usage settings: spaCy={self.spacy_usage_combo.currentText()}, Benepar={self.benepar_usage_combo.currentText()}")

    @pyqtSlot()
    def save_usage_settings(self):
        """Save current model usage preferences to QSettings."""
        spacy_pref = self.spacy_usage_combo.currentText()
        benepar_pref = self.benepar_usage_combo.currentText()
        
        self.settings.setValue("modelUsage/spacyModel", spacy_pref)
        self.settings.setValue("modelUsage/beneparModel", benepar_pref)
        self.settings.sync() # Force writing to persistent storage
        logging.info(f"Saved usage settings: spaCy={spacy_pref}, Benepar={benepar_pref}")
        self.model_usage_changed.emit() # Signal that usage pref changed

    def _update_usage_combos(self, installed_spacy: list, installed_benepar: list):
        """Updates the items in the usage combo boxes based on the provided lists."""
        current_spacy_selection = self.spacy_usage_combo.currentText()
        current_benepar_selection = self.benepar_usage_combo.currentText()
        
        # Block signals while repopulating to avoid triggering save prematurely
        self.spacy_usage_combo.blockSignals(True)
        self.benepar_usage_combo.blockSignals(True)
        
        self.spacy_usage_combo.clear()
        self.benepar_usage_combo.clear()
        
        self.spacy_usage_combo.addItem("(Auto-detect)")
        self.benepar_usage_combo.addItem("(Auto-detect)")
        
        # Use the provided lists directly
        self.spacy_usage_combo.addItems(sorted(installed_spacy))
        self.benepar_usage_combo.addItems(sorted(installed_benepar))
        
        # Restore previous selection if possible, otherwise default to Auto-detect
        spacy_index = self.spacy_usage_combo.findText(current_spacy_selection)
        self.spacy_usage_combo.setCurrentIndex(spacy_index if spacy_index != -1 else 0)
        
        benepar_index = self.benepar_usage_combo.findText(current_benepar_selection)
        self.benepar_usage_combo.setCurrentIndex(benepar_index if benepar_index != -1 else 0)
        
        # Unblock signals
        self.spacy_usage_combo.blockSignals(False)
        self.benepar_usage_combo.blockSignals(False)
        
    def _update_ui_from_status(self, status_data: dict):
        """Updates the UI elements based on the provided status dictionary."""
        logging.debug(f"ModelsPage._update_ui_from_status: Received status_data = {status_data}") # LOGGING
        
        # Extract data from the dictionary (handle potential None)
        installed_spacy_models = status_data.get('spacy_models', [])
        installed_benepar_models = status_data.get('benepar_models', [])
        nltk_present_overall = status_data.get('nltk_present', False)
        init_error = status_data.get('error') # Check if there was an initial error

        # Calculate worker status first
        is_worker_running = (self.install_worker_thread and self.install_worker_thread.isRunning()) or \
                          (self.clean_worker_thread and self.clean_worker_thread.isRunning())

        # Determine button enable state (only disable if worker running)
        self._set_buttons_enabled(not is_worker_running)

        # Update status labels based on installed models
        # Update spaCy Status Label
        if installed_spacy_models:
            found_aliases = []
            reverse_spacy_map = {v: k for k, v in SPACY_MODEL_MAP.items() if not k.startswith('en_')} 
            for name in installed_spacy_models:
                alias = reverse_spacy_map.get(name, name) 
                found_aliases.append(alias)
            status_text = f"(<b style='color:green;'>Ready:</b> {', '.join(sorted(found_aliases))})"
            self.spacy_status_label.setText(status_text)
            self.spacy_status_label.setToolTip("Installed spaCy models: " + ", ".join(installed_spacy_models))
        else:
            status_text = "(<b style='color:red;'>Missing</b>)"
            self.spacy_status_label.setText(status_text)
            self.spacy_status_label.setToolTip("No compatible spaCy models found.")

        # Update Benepar Status Label
        if installed_benepar_models:
            found_aliases = []
            reverse_benepar_map = {v: k for k, v in BENEPAR_MODEL_MAP.items() if not k.startswith('benepar_')}
            for name in installed_benepar_models:
                alias = reverse_benepar_map.get(name, name)
                found_aliases.append(alias)
            status_text = f"(<b style='color:green;'>Ready:</b> {', '.join(sorted(found_aliases))})"
            self.benepar_status_label.setText(status_text)
            self.benepar_status_label.setToolTip("Installed Benepar models: " + ", ".join(installed_benepar_models))
        else:
            status_text = "(<b style='color:red;'>Missing</b>)"
            self.benepar_status_label.setText(status_text)
            self.benepar_status_label.setToolTip("No compatible Benepar models found.")

        # Update NLTK Status Label
        if nltk_present_overall:
            status_text = "(<b style='color:green;'>Ready</b>)"
            self.nltk_status_label.setText(status_text)
            self.nltk_status_label.setToolTip("Required NLTK tokenizers (punkt) found.")
        else:
            status_text = "(<b style='color:red;'>Missing</b>)"
            self.nltk_status_label.setText(status_text)
            self.nltk_status_label.setToolTip("Required NLTK tokenizers (punkt) are missing.")

        # Update Action Buttons (based on installed status)
        for model in self.manageable_models:
            alias = model['alias']
            button = self.action_buttons.get(alias)
            if not button: continue
            model_type = model['type']
            is_installed = False
            if model_type == 'spacy':
                is_installed = model['name'] in installed_spacy_models
            elif model_type == 'benepar':
                is_installed = model['name'] in installed_benepar_models

            # Button enabling is handled by _set_buttons_enabled
            # Only update text and style here
            if is_installed:
                button.setText("Uninstall")
                button.setProperty("danger", True) # Set danger property for uninstall
                button.setToolTip(f"Uninstall {model['name']}")
            else:
                button.setText("Install")
                button.setProperty("danger", False) # Remove danger property for install
                button.setToolTip(f"Install {model['name']}")
            # Force style re-evaluation after changing property
            button.style().unpolish(button)
            button.style().polish(button)

        # NLTK Action Button
        if self.nltk_action_button:
            if nltk_present_overall:
                self.nltk_action_button.setText("Uninstall") # Changed text
                self.nltk_action_button.setProperty("danger", True) # Set danger property
                self.nltk_action_button.setToolTip("Uninstall NLTK tokenizers (punkt, punkt_tab).")
            else:
                self.nltk_action_button.setText("Install NLTK")
                self.nltk_action_button.setProperty("danger", False) # Remove danger property
                self.nltk_action_button.setToolTip("Install NLTK tokenizers (punkt, punkt_tab).")
            # Force style re-evaluation
            self.nltk_action_button.style().unpolish(self.nltk_action_button)
            self.nltk_action_button.style().polish(self.nltk_action_button)

        # Update usage combos based on installed models
        self._update_usage_combos(installed_spacy_models, installed_benepar_models)

        # --- DEBUG LOGGING for SpaCy --- 
        logging.debug(f"_update_ui_from_status: Processing SpaCy. Installed list received: {installed_spacy_models}")
        for model_dbg in [m for m in self.manageable_models if m['type'] == 'spacy']:
             alias_dbg = model_dbg['alias']
             name_dbg = model_dbg['name']
             is_installed_dbg = name_dbg in installed_spacy_models
             logging.debug(f"  Checking SpaCy '{alias_dbg}' ('{name_dbg}'): Found = {is_installed_dbg}")
        # --- END DEBUG LOGGING ---

        # Update the feedback status label
        if init_error:
            self.model_action_status_label.setText(f"Error checking status: {init_error}")
        elif not is_worker_running:
            self.model_action_status_label.setText("Model status updated.")
        # If a worker is running, the status label will be updated by the worker signals
        
        # --- Load persistent usage settings AFTER combo boxes are populated ---
        self.load_usage_settings()
        # ---------------------------------------------------------------------

    @pyqtSlot()
    def refresh_status(self):
        """Checks status of all known models and updates the UI via _update_ui_from_status."""
        # Assume ANPE core is available
        self.model_action_status_label.setText("Refreshing status...")
        QApplication.processEvents() # Ensure UI updates during check
        try:
            status_update = {
                'spacy_models': find_installed_spacy_models(),
                'benepar_models': find_installed_benepar_models(),
                'nltk_present': check_nltk_models(['punkt', 'punkt_tab']),
                'error': None
            }
            # Status label text updated within _update_ui_from_status
        except Exception as e:
            logging.error(f"Error during manual refresh: {e}", exc_info=True)
            status_update = {'spacy_models': [], 'benepar_models': [], 'nltk_present': False, 'error': f'Refresh error: {e}'}
            # Error message set within _update_ui_from_status

        # --- DEBUG LOGGING --- 
        logging.debug(f"refresh_status: Collected Status: {status_update}")
        # --- END DEBUG LOGGING ---

        # Update the UI using the collected status
        self._update_ui_from_status(status_update)

    def _set_buttons_enabled(self, enabled: bool):
        """Enable/disable action buttons, optionally forcing disable (e.g., if core missing)."""
        
        # Enable/disable global action buttons
        # Refresh should only be disabled if a worker is running
        self.refresh_button.setEnabled(enabled)
        # Assume core is present, only disable if worker running
        self.clean_button.setEnabled(enabled)
        
        # Enable/disable buttons in the grid
        # Assume core is present, only disable if worker running
        model_action_enabled_state = enabled
        for alias, button in self.action_buttons.items():
            button.setEnabled(model_action_enabled_state)
        if self.nltk_action_button:
            self.nltk_action_button.setEnabled(model_action_enabled_state)
        
        # Enable/disable usage combos (only disable if worker running)
        self.spacy_usage_combo.setEnabled(enabled)
        self.benepar_usage_combo.setEnabled(enabled)

    @pyqtSlot()
    def run_model_action(self):
        """Slot connected to all Install/Uninstall buttons in the grid."""
        sender_button = self.sender()
        if not isinstance(sender_button, QPushButton):
            return
            
        alias = sender_button.property("model_alias")
        model_type = sender_button.property("model_type")
        # Determine action based on button text (more robustly)
        button_text = sender_button.text()
        if "Install" in button_text:
            action = "install"
        elif "Uninstall" in button_text:
            action = "uninstall"
        else:
            action = None # Should not happen if button text is updated correctly
        
        if not model_type or not action or (model_type != 'nltk' and not alias):
            logging.error("Missing model info on button signal.")
            QMessageBox.critical(self.window(), "Error", "Internal error: Could not determine action from button.")
            return
            
        # Use install_worker_thread for simplicity, assuming only one action runs at a time
        if self.install_worker_thread and self.install_worker_thread.isRunning():
             QMessageBox.warning(self.window(), "In Progress", "Another model action is already running. Please wait.")
             return
             
        # Confirmation for uninstall
        if action == "uninstall":
            confirm_message = ""
            if model_type == 'nltk':
                 confirm_message = f"Are you sure you want to uninstall the required NLTK resources (punkt, punkt_tab)?"
            else:
                 model_name = SPACY_MODEL_MAP.get(alias) if model_type == 'spacy' else BENEPAR_MODEL_MAP.get(alias)
                 confirm_message = f"Are you sure you want to uninstall the {model_type} model '{alias}' ({model_name})?"
                 
            reply = QMessageBox.question(
                self.window(),
                "Confirm Uninstall",
                confirm_message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
                 
        self._set_buttons_enabled(False) # Disable all action buttons
        self.model_action_status_label.setText(f"Starting {action} for {model_type} model '{alias}'...")
        self.model_action_progress.setRange(0,0) # Indeterminate
        self.model_action_progress.setVisible(True)
        
        # Cleanup previous thread/worker
        if self.install_worker: # Reuse install_worker attribute name
            self.install_worker.deleteLater()
        if self.install_worker_thread:
            self.install_worker_thread.quit()
            self.install_worker_thread.wait()
            self.install_worker_thread.deleteLater()
            
        # Pass alias=None for NLTK
        self.install_worker = ModelActionWorker(action, model_type, alias if model_type != 'nltk' else None)
        self.install_worker_thread = QThread(self) 
        self.install_worker.moveToThread(self.install_worker_thread)
        
        # Connect signals (use the same slots as install/verify for now)
        self.install_worker.progress.connect(self.model_action_status_label.setText)
        self.install_worker.finished.connect(self.on_model_action_finished) # Use a generic finished slot
        self.install_worker_thread.started.connect(self.install_worker.run)
        # Cleanup
        self.install_worker.finished.connect(self.install_worker_thread.quit)
        self.install_worker.finished.connect(self.install_worker.deleteLater)
        self.install_worker_thread.finished.connect(self.install_worker_thread.deleteLater)
        
        self.install_worker_thread.start()
        
    @pyqtSlot(bool, str)
    def on_model_action_finished(self, success: bool, message: str):
        """Handle completion of any model install/uninstall worker."""
        self.model_action_progress.setVisible(False)
        self.install_worker_thread = None # Clear thread/worker references
        self.install_worker = None
        
        if success:
             QMessageBox.information(self.window(), "Action Complete", message)
        else:
             QMessageBox.warning(self.window(), "Action Failed", message)
             
        # Use a timer to delay refresh_status call slightly to ensure UI has time to process
        QTimer.singleShot(100, self.refresh_status)
        self.models_changed.emit() # Notify parent dialog/main window

    @pyqtSlot()
    def run_clean(self):
        """Confirm and start the background cleaning process."""
        if self.clean_worker_thread and self.clean_worker_thread.isRunning():
            QMessageBox.warning(self.window(), "In Progress", "Model cleanup is already running.")
            return

        # --- Detect currently installed models BEFORE showing the confirmation ---
        try:
            detected_spacy = find_installed_spacy_models()
            detected_benepar = find_installed_benepar_models()
            detected_nltk = check_nltk_models(['punkt', 'punkt_tab'])
        except Exception as e:
            logging.error(f"Error detecting models for clean confirmation: {e}")
            QMessageBox.critical(self.window(), "Error", f"Could not detect installed models before cleanup: {e}")
            return

        # --- Format the message dynamically ---
        message_parts = ["This action will attempt to remove the following <b>currently detected</b> ANPE-related models:<br><br>"]
        
        if detected_spacy:
            spacy_models_str = ", ".join([f"<b>{name}</b>" for name in sorted(detected_spacy)])
            message_parts.append(f" • <b>spaCy:</b> {spacy_models_str}<br>")
        else:
             message_parts.append(" • <b>spaCy:</b> (None detected)<br>")
             
        if detected_benepar:
            benepar_models_str = ", ".join([f"<b>{name}</b>" for name in sorted(detected_benepar)])
            message_parts.append(f" • <b>Benepar:</b> {benepar_models_str}<br>")
        else:
             message_parts.append(" • <b>Benepar:</b> (None detected)<br>")
             
        if detected_nltk:
            message_parts.append(" • <b>NLTK:</b> <b>punkt</b>, <b>punkt_tab</b><br>")
        else:
             message_parts.append(" • <b>NLTK:</b> (None detected)<br>")

        message_parts.append(
            "<br>from all known locations on your system.<br>"
            "Models may need to be re-downloaded if removed.<br><br>"
            "<b>Are you sure you want to proceed?</b>"
        )
        confirm_message = "".join(message_parts)
        # -------------------------------------

        reply = QMessageBox.question(
            self.window(), # Parent to main window
            "Confirm Cleanup",
            confirm_message, # Use the dynamically generated message
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        self._set_buttons_enabled(False)
        self.model_action_status_label.setText("Starting cleanup...")
        self.model_action_progress.setRange(0,0) # Indeterminate
        self.model_action_progress.setVisible(True)
        
        # Cleanup previous thread/worker
        if self.clean_worker:
            self.clean_worker.deleteLater()
        if self.clean_worker_thread:
            self.clean_worker_thread.quit()
            self.clean_worker_thread.wait()
            self.clean_worker_thread.deleteLater()

        self.clean_worker = CleanWorker()
        self.clean_worker_thread = QThread(self)
        self.clean_worker.moveToThread(self.clean_worker_thread)

        # Connect signals
        self.clean_worker.progress.connect(self.model_action_status_label.setText)
        self.clean_worker.finished.connect(self.on_clean_finished)
        self.clean_worker_thread.started.connect(self.clean_worker.run)
        # Clean up
        self.clean_worker.finished.connect(self.clean_worker_thread.quit)
        self.clean_worker.finished.connect(self.clean_worker.deleteLater)
        self.clean_worker_thread.finished.connect(self.clean_worker_thread.deleteLater)

        self.clean_worker_thread.start()

    @pyqtSlot(dict)
    def on_clean_finished(self, results: dict):
        """Handle completion of the clean process."""
        self.model_action_progress.setVisible(False)
        self.clean_worker_thread = None
        self.clean_worker = None
        
        all_succeeded = all(results.values()) # Check if all removals were error-free

        if all_succeeded:
            message = "Model cleanup process finished successfully."
            QMessageBox.information(self.window(), "Cleanup Complete", message)
        else:
            failed_models = [model for model, success in results.items() if not success]
            message = (f"Model cleanup process finished, but some errors occurred "
                       f"(e.g., for {', '.join(failed_models)}). Please check logs.")
            QMessageBox.warning(self.window(), "Cleanup Incomplete", message)
            
        self.model_action_status_label.setText(message)
        self.refresh_status() # Update status labels
        self._set_buttons_enabled(True)
        self.models_changed.emit() # Notify parent dialog/main window

    @pyqtSlot()
    def on_model_usage_preference_changed(self):
        """Slot called when the model usage preference is changed in the SettingsDialog."""
        logging.debug("ModelsPage: Model usage preference changed.")
        self.save_usage_settings()
        self.model_usage_changed.emit()


class CorePage(QWidget):
    """Page for checking and updating the ANPE core package."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CorePage")
        
        self.worker_thread = None
        self.worker = None
        self.current_version = "N/A"
        self.latest_version = "N/A"
        
        self.setup_ui()
        self.load_initial_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20) 
        layout.setSpacing(15)

        # Use QGroupBox for better visual separation
        group_box = QGroupBox("ANPE Core Package Status")
        group_layout = QVBoxLayout(group_box)
        group_layout.setSpacing(10)
        
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(10)

        self.current_version_label = QLabel("Checking...")
        self.latest_version_label = QLabel("-")
        self.check_update_button = QPushButton("Check for Updates")
        self.status_label = QLabel("Ready to check for updates.")
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100) # For determinate, 0,0 for indeterminate

        form_layout.addRow("Current Installed Version:", self.current_version_label)
        form_layout.addRow("Latest Available Version:", self.latest_version_label)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.check_update_button)
        button_layout.addStretch()
        
        group_layout.addLayout(form_layout)
        group_layout.addWidget(self.status_label)
        group_layout.addWidget(self.progress_bar)
        group_layout.addLayout(button_layout)
        group_layout.addStretch(1) # Push content to top
        
        layout.addWidget(group_box)
        layout.addStretch(1) # Push group box to top
        
        # Connect button signal
        self.check_update_button.clicked.connect(self.handle_core_action)
        
    def load_initial_data(self):
        """Get the current installed version (assuming core is installed)."""
        try:
            # Assume core is installed, directly get version
            self.current_version = importlib.metadata.version(CORE_PACKAGE_NAME)
            self.current_version_label.setText(self.current_version)
            self.status_label.setText("Ready to check for updates.")
        except Exception as e:
            # Error getting version even though core is expected
            self.current_version = "N/A (Error)"
            self.current_version_label.setText(f"<i style='color: {ERROR_COLOR};'>{self.current_version}</i>")
            self.status_label.setText(f"Error reading core version: {e}")
            logging.error(f"Error getting current core version: {e}", exc_info=True)
        finally:
            # Button should always be enabled unless worker running
            self.check_update_button.setEnabled(True)
            self.check_update_button.setText("Check for Updates") # Ensure initial text

    @pyqtSlot()
    def handle_core_action(self):
        """Decide whether to check for update or run update based on button state."""
        if self.worker_thread and self.worker_thread.isRunning():
            logging.warning("Core action already in progress.")
            return
            
        # Clean up previous thread/worker if they exist
        if self.worker:
             self.worker.deleteLater()
        if self.worker_thread:
             self.worker_thread.quit()
             self.worker_thread.wait()
             self.worker_thread.deleteLater()
             
        self.worker = CoreUpdateWorker(self.current_version)
        self.worker_thread = QThread(self)
        self.worker.moveToThread(self.worker_thread)
        
        button_text = self.check_update_button.text()
        
        if button_text == "Check for Updates":
            self.status_label.setText("Checking PyPI for latest version...")
            self.progress_bar.setRange(0, 0) # Indeterminate
            self.progress_bar.setVisible(True)
            self.check_update_button.setEnabled(False)
            self.latest_version_label.setText("Checking...")
            
            # Connect check signals
            self.worker.check_finished.connect(self.on_check_finished)
            self.worker_thread.started.connect(self.worker.run_check)
            # Cleanup connections
            self.worker.check_finished.connect(self.worker_thread.quit)
            self.worker.check_finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            
            self.worker_thread.start()
            
        elif button_text == "Update ANPE Core":
            reply = QMessageBox.question(
                self.window(), 
                "Confirm Update",
                f"This will attempt to update the '{CORE_PACKAGE_NAME}' package using pip.\n\n" 
                f"Current Version: {self.current_version}\n" 
                f"Target Version: {self.latest_version}\n\n" 
                "Ensure you have an internet connection and necessary permissions.\n"
                "Do you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                 return
                 
            self.status_label.setText("Starting update process...")
            self.progress_bar.setRange(0, 100) # Determinate for update (or -1 in worker)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.check_update_button.setEnabled(False)
            
            # Connect update signals
            self.worker.update_progress.connect(self.on_update_progress)
            self.worker.update_finished.connect(self.on_update_finished)
            self.worker_thread.started.connect(self.worker.run_update)
            # Cleanup connections
            self.worker.update_finished.connect(self.worker_thread.quit)
            self.worker.update_finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            
            self.worker_thread.start()
            
    @pyqtSlot(str, str, str)
    def on_check_finished(self, latest_version, current_version, error_string):
        """Handle the result of the PyPI version check."""
        self.progress_bar.setVisible(False)
        self.worker_thread = None # Allow new actions
        self.worker = None
        
        if error_string:
            self.status_label.setText(f"Error checking for updates: {error_string}")
            self.latest_version_label.setText("Error")
            self.check_update_button.setText("Check for Updates")
            # Button should remain enabled to allow retrying the check
            self.check_update_button.setEnabled(True) 
            logging.error(f"Update check failed: {error_string}")
        else:
            self.latest_version = latest_version # Store latest version
            self.latest_version_label.setText(latest_version)
            
            # Determine if an action is needed (update only, assume installed)
            can_install_or_update = latest_version != "N/A"
            needs_update = False
            if self.current_version != "N/A (Error)" and latest_version != "N/A":
                 # Basic version comparison (consider using 'packaging' library for robustness if needed)
                 try:
                      from packaging import version
                      needs_update = version.parse(latest_version) > version.parse(self.current_version)
                 except ImportError:
                      # Fallback to string comparison
                      needs_update = latest_version > self.current_version
                 except version.InvalidVersion:
                      logging.warning(f"Could not parse versions for comparison: current='{self.current_version}', latest='{latest_version}'")
                      needs_update = False # Avoid potentially incorrect update prompt

            if needs_update:
                self.status_label.setText(f"Update available (Version {latest_version}).")
                self.check_update_button.setText(f"Update ANPE Core ({latest_version})")
                self.check_update_button.setEnabled(True)
            else: # Up-to-date or latest is N/A
                self.status_label.setText("ANPE core package is up to date.")
                self.check_update_button.setText("Up to Date")
                self.check_update_button.setEnabled(False) # Disable if up to date
                
    @pyqtSlot(int, str)
    def on_update_progress(self, value, message):
        """Update progress bar and status label during update."""
        if value == -1: # Indeterminate
             self.progress_bar.setRange(0, 0)
        else:
             self.progress_bar.setRange(0, 100)
             self.progress_bar.setValue(value)
        self.status_label.setText(message)

    @pyqtSlot(bool, str)
    def on_update_finished(self, success, message):
        """Handle completion of the update process."""
        self.progress_bar.setVisible(False)
        self.worker_thread = None # Allow new actions
        self.worker = None
        
        if success:
             QMessageBox.information(self.window(), "Update Complete", message)
             # Update current version display after successful update
             self.load_initial_data()
             # Reset button state after successful update
             self.latest_version_label.setText("-") # Clear latest version
             self.status_label.setText("Update successful. Check for updates again if needed.")
             self.check_update_button.setText("Check for Updates")
             self.check_update_button.setEnabled(True)
        else:
             QMessageBox.warning(self.window(), "Update Failed", message)
             self.status_label.setText("Update failed. Check logs for details.")
             # Keep button as Update? Or revert to Check?
             # Let's revert to Check for simplicity, user can try again
             self.check_update_button.setText("Check for Updates")
             self.check_update_button.setEnabled(True)

class AboutPage(QWidget):
    """Displays About information: versions, author, links, acknowledgements."""
    def __init__(self, gui_version: str, core_version: str, parent=None):
        super().__init__(parent)
        self.gui_version = gui_version
        # Ensure core_version is displayed correctly even if passed as N/A
        self.core_version = core_version 
        self.setObjectName("AboutPage")
        self.setup_ui()
        
    def setup_ui(self):
        # Replicate layout from help_dialog.AboutDialog
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        # Add margins to simulate dialog padding within the page
        main_layout.setContentsMargins(30, 20, 30, 20) 

        # --- Header Section ---
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setSpacing(20)
        header_layout.setContentsMargins(0, 0, 0, 10)

        # Icon (left)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Need ResourceManager - assume it's importable or handle import error
        try:
             from anpe_gui.resource_manager import ResourceManager
             pixmap = ResourceManager.get_pixmap("app_icon.png")
        except ImportError:
             logging.warning("ResourceManager not found, using placeholder icon.")
             pixmap = QPixmap(100, 100)
             pixmap.fill(Qt.GlobalColor.gray)
             
        pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(100, 100)
        header_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Title/Subtitle (right)
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)
        title_layout.addStretch(1)

        title_label = QLabel("ANPE")
        title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {PRIMARY_COLOR};")
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("Another Noun Phrase Extractor")
        subtitle_label.setStyleSheet("font-size: 16px; color: #666666;")
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch(1)

        header_layout.addWidget(title_container, 1)
        main_layout.addWidget(header_widget)

        # --- Info Grid ---
        info_widget = QWidget()
        info_layout = QGridLayout(info_widget)
        info_layout.setContentsMargins(10, 0, 10, 10)
        info_layout.setSpacing(8)
        info_layout.setColumnStretch(1, 1)

        label_width = 110

        # GUI Version
        gui_label = QLabel("GUI Version:")
        gui_label.setStyleSheet("font-weight: bold;")
        gui_label.setFixedWidth(label_width)
        gui_value = QLabel(self.gui_version)
        info_layout.addWidget(gui_label, 0, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(gui_value, 0, 1, Qt.AlignmentFlag.AlignLeft)

        # Core Version
        core_label = QLabel("Core Version:")
        core_label.setStyleSheet("font-weight: bold;")
        core_label.setFixedWidth(label_width)
        core_value = QLabel(self.core_version)
        info_layout.addWidget(core_label, 1, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(core_value, 1, 1, Qt.AlignmentFlag.AlignLeft)

        # Author
        author_label = QLabel("Author:")
        author_label.setStyleSheet("font-weight: bold;")
        author_label.setFixedWidth(label_width)
        author_value = QLabel("Richard Chen (@rcverse)")
        info_layout.addWidget(author_label, 2, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(author_value, 2, 1, Qt.AlignmentFlag.AlignLeft)

        # License
        license_label = QLabel("License:")
        license_label.setStyleSheet("font-weight: bold;")
        license_label.setFixedWidth(label_width)
        license_value = QLabel("GNU General Public License v3") # Button handled below
        info_layout.addWidget(license_label, 3, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(license_value, 3, 1, Qt.AlignmentFlag.AlignLeft)

        # Contact
        email_label = QLabel("Contact:")
        email_label.setStyleSheet("font-weight: bold;")
        email_label.setFixedWidth(label_width)
        email_value = QLabel('<a href="mailto:rcverse6@gmail.com">rcverse6@gmail.com</a>')
        email_value.setTextFormat(Qt.TextFormat.RichText)
        email_value.setOpenExternalLinks(True)
        info_layout.addWidget(email_label, 4, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(email_value, 4, 1, Qt.AlignmentFlag.AlignLeft)

        main_layout.addWidget(info_widget)

        # --- Separator ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)

        # --- Acknowledgements Section ---
        ack_widget = QWidget()
        ack_layout = QVBoxLayout(ack_widget)
        ack_layout.setContentsMargins(10, 5, 10, 5)
        ack_layout.setSpacing(5)

        ack_title = QLabel("Acknowledgements")
        ack_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #333; margin-bottom: 5px;")
        ack_layout.addWidget(ack_title)

        ack_text = (
            "This application uses the following open-source libraries:<br>"
            "• <b>PyQt6</b> (GPLv3 / Commercial)<br>"
            "• <b>spaCy</b> (MIT License)<br>"
            "• <b>Benepar</b> (MIT License)<br>"
            "• <b>NLTK</b> (Apache License 2.0)<br><br>"
            "We are grateful for the developers of these packages that make ANPE and ANPE GUI possible. "
            "Click 'View License' for more details."
        )
        ack_label = QLabel(ack_text)
        ack_label.setWordWrap(True)
        ack_label.setTextFormat(Qt.TextFormat.RichText)
        ack_label.setStyleSheet("font-size: 11px; color: #555;")
        ack_layout.addWidget(ack_label)

        main_layout.addWidget(ack_widget)
        main_layout.addStretch(1) # Push buttons to the bottom

        # --- Button Bar --- 
        # Add buttons relevant to this page (links)
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(10, 10, 10, 0)
        button_layout.setSpacing(10)

        project_page_button = QPushButton("Visit Project Page")
        project_page_button.clicked.connect(self._visit_project_page)
        button_layout.addWidget(project_page_button)
        
        license_view_button = QPushButton("View License")
        license_view_button.clicked.connect(self._show_license)
        button_layout.addWidget(license_view_button)
        
        button_layout.addStretch(1)
        main_layout.addWidget(button_widget)

    def _show_license(self):
        """Show the license dialog."""
        # Need LicenseDialog - assume it's importable or handle error
        try:
            from anpe_gui.widgets.license_dialog import LicenseDialog
            from PyQt6.QtWidgets import QApplication # Added import

            license_dialog = LicenseDialog(self.window()) # Parent to the main dialog window

            # --- Center on parent's screen --- 
            parent_window = self.window()
            screen = None
            if parent_window:
                screen = QApplication.screenAt(parent_window.pos())
            if not screen:
                screen = QApplication.primaryScreen()
                
            if screen:
                screen_center = screen.availableGeometry().center()
                dialog_geom = license_dialog.frameGeometry()
                dialog_geom.moveCenter(screen_center)
                license_dialog.move(dialog_geom.topLeft())
            # If no screen info, let Qt decide default placement
            # -------------------------------

            license_dialog.exec()
        except ImportError:
             logging.error("LicenseDialog not found. Cannot display license.")

    def _visit_project_page(self):
        """Open project page in browser."""
        from PyQt6.QtGui import QDesktopServices # Import locally for clarity
        from PyQt6.QtCore import QUrl # Import locally for clarity
        QDesktopServices.openUrl(QUrl("https://github.com/rcverse/Another-Noun-Phrase-Extractor"))


# --- Main Dialog Class ---

class SettingsDialog(QDialog):
    """Dialog window for managing ANPE settings."""

    # Signal emitted when an action might require the main window to re-check things
    models_changed = pyqtSignal() 
    # Signal emitted if model usage preference changes
    model_usage_changed = pyqtSignal() 

    def __init__(self, parent=None, initial_model_status=None):
        super().__init__(parent)
        logging.debug(f"SettingsDialog.__init__: Received initial_model_status = {initial_model_status}") # LOGGING
        self.initial_model_status = initial_model_status # Store the passed status
        self.setWindowTitle("ANPE Settings")
        # Increased default/minimum height
        self.setMinimumSize(700, 600) # Increased height
        self.resize(800, 700)        # Increased height

        # Store references to page widgets
        self.models_page = None
        self.core_page = None
        self.about_page = None

        self.setup_ui()
        self.connect_signals()

        # Load initial state if needed (e.g., select first nav item)
        if self.nav_list.count() > 0:
            self.nav_list.setCurrentRow(0)

        # Center the dialog after setup
        self._center_on_screen()
        
        # --- Trigger initial refresh after dialog is set up --- 
        # Use QTimer.singleShot to schedule the refresh slightly after __init__ completes
        # REMOVED: QTimer.singleShot(50, self.models_page.refresh_status)
        # NOTE: Initial UI state is now set in ModelsPage.__init__ using the passed initial_model_status

    def _center_on_screen(self):
        """Centers the dialog on the primary screen."""
        try:
            screen = QApplication.primaryScreen()
            if not screen:
                logging.warning("SettingsDialog: Could not get primary screen. Centering skipped.")
                return
            screen_geometry = screen.availableGeometry() # Use available geometry
            window_rect = self.frameGeometry()
            center_point = screen_geometry.center()
            window_rect.moveCenter(center_point)
            # Ensure the window doesn't go off-screen
            final_pos = window_rect.topLeft()
            final_pos.setX(max(screen_geometry.x(), final_pos.x()))
            final_pos.setY(max(screen_geometry.y(), final_pos.y()))
            self.move(final_pos)
            logging.debug(f"SettingsDialog: Centered window on screen at {final_pos}")
        except Exception as e:
            logging.error(f"SettingsDialog: Error centering window: {e}", exc_info=True)

    def setup_ui(self):
        """Create the main UI structure with navigation and stacked pages."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Main Content Splitter ---
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(1) # Minimal handle
        content_splitter.setStyleSheet("QSplitter::handle { background-color: #cccccc; }")

        # Left Pane: Navigation List
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0) # No margins for the container
        nav_layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180) # Adjust width as needed
        self.nav_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #f0f0f0;
                border: none;
                padding-top: 10px;
                outline: none; /* Remove focus outline */
            }}
            QListWidget::item {{
                padding: 10px 15px 10px 15px; /* Adjusted top/bottom padding */
                border-bottom: 1px solid #e0e0e0;
                color: #333;
            }}
            QListWidget::item:hover {{
                background-color: {LIGHT_HOVER_BLUE};
                color: {PRIMARY_COLOR};
                border-left: 3px solid {PRIMARY_COLOR};
                padding-left: 12px; /* Adjust padding for border */
            }}
            QListWidget::item:selected {{
                background-color: white; /* Selected item matches page background */
                color: {PRIMARY_COLOR};
                font-weight: bold;
                border-left: 3px solid {PRIMARY_COLOR};
                padding-left: 12px; /* Adjust padding for border */
                border-bottom-color: transparent; /* Hide bottom border when selected */
            }}
            QListWidget:focus {{
                outline: none; /* Remove focus outline */
                border: none; /* Ensure no focus border */
            }}
        """)
        # Add navigation items with icons
        models_item = QListWidgetItem("Models")
        models_item.setIcon(ResourceManager.get_icon("layers.svg"))
        self.nav_list.addItem(models_item)

        core_item = QListWidgetItem("Core")
        core_item.setIcon(ResourceManager.get_icon("package.svg"))
        self.nav_list.addItem(core_item)

        about_item = QListWidgetItem("About")
        about_item.setIcon(ResourceManager.get_icon("info.svg"))
        self.nav_list.addItem(about_item)
        
        nav_layout.addWidget(self.nav_list)
        content_splitter.addWidget(nav_widget)

        # Right Pane: Stacked Pages
        self.pages_stack = QStackedWidget()
        self.pages_stack.setStyleSheet("QStackedWidget > QWidget { background-color: white; }") # Ensure pages have white background

        # Create and add pages (Pass initial status to ModelsPage)
        self.models_page = ModelsPage(self, initial_model_status=self.initial_model_status) # Use self.initial_model_status
        self.core_page = CorePage(self)
        # Pass version info to AboutPage
        try:
            from anpe_gui.version import __version__ as gui_version
        except ImportError:
            gui_version = "N/A"
        try:
             core_version = importlib.metadata.version(CORE_PACKAGE_NAME)
        except importlib.metadata.PackageNotFoundError:
             core_version = "N/A (Not Found)"
             
        self.about_page = AboutPage(gui_version=gui_version, core_version=core_version, parent=self)

        self.pages_stack.addWidget(self.models_page)
        self.pages_stack.addWidget(self.core_page)
        self.pages_stack.addWidget(self.about_page)

        content_splitter.addWidget(self.pages_stack)

        # Set initial splitter sizes (navigation fixed, pages expand)
        content_splitter.setSizes([180, 670]) # Adjust based on total width
        content_splitter.setStretchFactor(0, 0) # Nav doesn't stretch
        content_splitter.setStretchFactor(1, 1) # Pages stretch

        main_layout.addWidget(content_splitter)

    def connect_signals(self):
        """Connect signals for navigation and page updates."""
        self.nav_list.currentRowChanged.connect(self.pages_stack.setCurrentIndex)

        # Connect signals from ModelsPage to SettingsDialog signals
        self.models_page.models_changed.connect(self.models_changed.emit)
        self.models_page.model_usage_changed.connect(self.model_usage_changed.emit)