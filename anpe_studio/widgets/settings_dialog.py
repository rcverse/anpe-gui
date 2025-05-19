"""
Dialog for managing ANPE settings, including core updates, 
model usage preferences, and model installation/management.
"""

import anpe
import sys
import logging
import nltk # Need nltk for the status check part (will move to page) - Still needed for ModelsPage NLTK status check
import importlib.metadata # For getting core version
import json # For parsing PyPI response
import sys # <<< Added for Python version
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot, QSize, QSettings, QTimer, QEvent, QPoint, QUrl, QSize # Added QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QGridLayout, QProgressBar, QMessageBox, QWidget, QSpacerItem, QSizePolicy,
    QApplication, QFrame, QStackedWidget, QListWidget, QListWidgetItem, 
    QSplitter, QFormLayout, QComboBox, QTextEdit, QToolButton # Added QToolButton
)
from PyQt6.QtGui import QIcon, QPixmap, QTextCursor, QColor, QTransform, QDesktopServices # <<< Added QDesktopServices

from anpe_studio.theme import ERROR_COLOR, PRIMARY_COLOR, SUCCESS_COLOR, get_scroll_bar_style, LIGHT_HOVER_BLUE # Import theme elements
from anpe_studio.resource_manager import ResourceManager # ADDED THIS IMPORT
from anpe_studio.widgets.activity_indicator import PulsingActivityIndicator # IMPORT THE INDICATOR
# Import the worker classes from their new location
from anpe_studio.workers.settings_workers import (
    CoreUpdateWorker, CleanWorker, InstallDefaultsWorker, 
    ModelActionWorker, StatusCheckWorker, GuiUpdateCheckWorker # <<< ADDED GuiUpdateCheckWorker
)

# Assuming these utilities exist and work as expected
try:
    from anpe.utils.setup_models import (
        check_spacy_model, check_benepar_model, setup_models, # Removed check_nltk_models
        SPACY_MODEL_MAP, BENEPAR_MODEL_MAP, install_spacy_model, install_benepar_model, # Removed install_nltk_models
        DEFAULT_SPACY_ALIAS, DEFAULT_BENEPAR_ALIAS # Explicitly import defaults
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

# --- Page Widgets Implementation ---

class ModelsPage(QWidget):
    """Page for model usage settings and installation/management."""
    # Signals to notify the parent dialog (and potentially main window)
    models_changed = pyqtSignal() 
    model_usage_changed = pyqtSignal()

    def __init__(self, parent=None, model_status=None):
        super().__init__(parent)
        logging.debug(f"ModelsPage.__init__: Received model_status = {model_status}") # LOGGING
        self.setObjectName("ModelsPage")
        self.settings = QSettings("rcverse", "ANPE_STUDIO") # For usage persistence
        self.model_status = model_status # Store initial status
        self.management_group = None # Initialize attribute
        
        # --- Store base icon --- 
        # self.down_arrow_icon = ResourceManager.get_icon("down_arrow.svg") # REMOVED
        # -----------------------
        
        # Store refs to status labels - these will be created in setup_ui
        self.spacy_status_label = None
        self.spacy_aliases_label = None
        self.benepar_status_label = None
        self.benepar_aliases_label = None
        
        # Worker threads and instances
        self.install_worker_thread = None
        self.install_worker = None
        self.clean_worker_thread = None
        self.clean_worker = None
        self.install_defaults_thread = None # Already exists
        self.install_defaults_worker = None # Already exists
        self.status_check_thread = None   # <<< ADDED Status Check Worker Thread
        self.status_check_worker = None   # <<< ADDED Status Check Worker
        
        self.status_labels = {} # key: full_model_name, value: QLabel
        
        # For log dialog
        self.log_dialog = None
        self.log_text = ""
        self.log_text_edit = None # Will hold the QTextEdit widget instance
        
        # Metadata for manageable models (Updated descriptions and sizes)
        self.manageable_models = [
            {'type': 'spacy', 'alias': 'sm', 'name': SPACY_MODEL_MAP.get('sm'), 'desc': 'Small (~12MB): Fast, lower accuracy.'}, # Added (default)
            {'type': 'spacy', 'alias': 'md', 'name': SPACY_MODEL_MAP.get('md'), 'desc': 'Medium (~40MB): Good balance (default).'}, 
            {'type': 'spacy', 'alias': 'lg', 'name': SPACY_MODEL_MAP.get('lg'), 'desc': 'Large (~560MB): Higher accuracy.'}, 
            {'type': 'spacy', 'alias': 'trf', 'name': SPACY_MODEL_MAP.get('trf'), 'desc': 'Transformer-based (~430MB): Best accuracy.'}, 
            {'type': 'benepar', 'alias': 'default', 'name': BENEPAR_MODEL_MAP.get('default'), 'desc': 'Standard model (~63MB) T5-small based. (default)'}, # Updated Benepar
            {'type': 'benepar', 'alias': 'large', 'name': BENEPAR_MODEL_MAP.get('large'), 'desc': 'Large model (~208 MB) T5-large based. Higher accuracy.'}, # Updated Benepar
        ]
        # Filter out models if map didn't contain the alias (shouldn't happen with default maps)
        self.manageable_models = [m for m in self.manageable_models if m.get('name')] 
        
        self.action_buttons = {} # key: alias, value: QPushButton
        
        self.setup_ui()
        self.connect_signals()
        
        # Update UI using the initial status passed from MainWindow
        if self.model_status:
            logging.debug("ModelsPage: Applying initial status to UI.")
            self._update_ui_from_status(self.model_status)
        else:
            # Fallback if no status was passed (should not happen ideally)
            logging.warning("ModelsPage: No initial status received, performing initial refresh.")
            # Perform initial refresh asynchronously
            QTimer.singleShot(100, self.refresh_status) # <<< Trigger async refresh

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
            "spaCy models handle sentence segmentation and structural analysis. "
            "Smaller models (e.g., 'sm') are faster but slightly less accurate. Larger models ('lg', 'trf') "
            "offer higher accuracy but require more resources. If you are on a CPU-only machine, the transformer model"
            " may be too slow for practical use."
        )
        spacy_explanation_label.setWordWrap(True)
        spacy_explanation_label.setStyleSheet(explanation_style)
        # Add explanation spanning both columns of the form layout
        usage_layout.addRow(spacy_explanation_label) 
        
        benepar_explanation_label = QLabel(
             "Benepar models handle detailed constituent parsing. The 'large' model generally provides "
             "higher accuracy but slighlty increases processing time and memory usage."
        )
        benepar_explanation_label.setWordWrap(True)
        benepar_explanation_label.setStyleSheet(explanation_style)
        # Add explanation spanning both columns
        usage_layout.addRow(benepar_explanation_label)
        # --------------------------

        main_layout.addWidget(usage_group)

        # --- Model Installation & Management --- 
        self.management_group = QGroupBox("Manage Models / Resources") # Assign to self
        management_layout = QVBoxLayout(self.management_group) # Use self.management_group
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
        spacy_header_label = QLabel("spaCy Models")
        spacy_header_label.setStyleSheet(header_style)
        self.spacy_status_label = QLabel("(Checking status...)") # Status label here
        self.spacy_status_label.setStyleSheet(status_style)
        spacy_header_layout.addWidget(spacy_header_label)
        spacy_header_layout.addWidget(self.spacy_status_label)
        spacy_header_layout.addStretch()
        grid_layout.addWidget(spacy_header_widget, current_row, 0, 1, 3) 
        current_row += 1

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
        benepar_header_label = QLabel("Benepar Models")
        benepar_header_label.setStyleSheet(header_style)
        self.benepar_status_label = QLabel("(Checking status...)") # Status label here
        self.benepar_status_label.setStyleSheet(status_style)
        benepar_header_layout.addWidget(benepar_header_label)
        benepar_header_layout.addWidget(self.benepar_status_label)
        benepar_header_layout.addStretch()
        grid_layout.addWidget(benepar_header_widget, current_row, 0, 1, 3) 
        current_row += 1

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

        # Feedback Area (Activity Indicator + Status Label) - Updated
        feedback_widget = QWidget()
        feedback_layout = QHBoxLayout(feedback_widget) # Use QHBoxLayout now
        feedback_layout.setContentsMargins(0,0,0,0)
        feedback_layout.setSpacing(8) # Spacing between indicator and label

        self.model_action_indicator = PulsingActivityIndicator()
        self.model_action_indicator.setFixedSize(20, 20) # Smaller indicator
        # self.model_action_indicator.setVisible(False) # Hidden initially # REMOVED
        self.model_action_indicator.set_color(PRIMARY_COLOR) # Use theme color

        self.model_action_status_label = QLabel("Status updated.")
        self.model_action_status_label.setWordWrap(True)
        self.model_action_status_label.setStyleSheet("color: #666; font-style: italic; font-size: 9pt;")

        # --- Details Button (Show Log Dialog) ---
        self.show_details_button = QToolButton()
        self.show_details_button.setIcon(ResourceManager.get_icon("external-link.svg"))  # Use external-link icon
        self.show_details_button.setIconSize(QSize(12, 12)) # Smaller icon
        self.show_details_button.setFixedSize(22, 22) # Round button size
        self.show_details_button.setToolTip("Show Action Details Log")
        self.show_details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_details_button.setStyleSheet("""
            QToolButton {
                background-color: #e0e0e0;
                border: none;
                border-radius: 11px; /* Half of size */
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #cccccc;
            }
            QToolButton:pressed {
                background-color: #bbbbbb;
            }
        """)
        
        # --- Adjust Layout Order --- 
        feedback_layout.addWidget(self.show_details_button) # Add ToolButton first
        feedback_layout.addWidget(self.model_action_indicator) # Then indicator
        feedback_layout.addWidget(self.model_action_status_label, 1) # Label takes stretch
        # --------------------------

        feedback_actions_layout.addWidget(feedback_widget, 1) # Feedback takes expanding space

        # Global Action Buttons (Refresh, Clean/Install Defaults)
        self.refresh_button = QPushButton("Refresh Status")
        self.refresh_button.setFixedHeight(26)
        # Removed setStyleSheet here - uses global theme

        # Rename clean_button to install_clean_button
        self.install_clean_button = QPushButton("...") # Text set dynamically
        self.install_clean_button.setFixedWidth(120) # Slightly wider for longer text
        self.install_clean_button.setFixedHeight(26)
        # self.install_clean_button.setProperty("danger", True) # Property set dynamically
        # Tooltip set dynamically

        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0,0,0,0)
        button_layout.setSpacing(8)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.install_clean_button) # Use new name

        feedback_actions_layout.addWidget(button_widget) # Add buttons container (fixed size)
        management_layout.addLayout(feedback_actions_layout) # Add actions layout to group

        main_layout.addWidget(self.management_group) # Use self.management_group

        # NOTE: Initial UI update is now called from __init__ after setup_ui completes

    def connect_signals(self):
        # Usage settings
        self.spacy_usage_combo.currentTextChanged.connect(self.save_usage_settings)
        self.benepar_usage_combo.currentTextChanged.connect(self.save_usage_settings)
        # Management actions
        self.refresh_button.clicked.connect(self.refresh_status) # <<< Connects to the NEW async refresh_status
        # Connect the new button to the dynamic handler (to be created)
        self.install_clean_button.clicked.connect(self.handle_install_clean_click)
        # Connect the details button to show log dialog
        self.show_details_button.clicked.connect(self._show_log_dialog)

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
        check_error = status_data.get('error') # Check if there was an error during status check

        # Check if ANY worker is running
        is_any_worker_running = self.is_worker_running()

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

        # --- Update the feedback status label and dynamic button --- 
        # Determine if all default models are present
        try:
            # Rely on module-level imports
            default_spacy_name = SPACY_MODEL_MAP[DEFAULT_SPACY_ALIAS]
            default_benepar_name = BENEPAR_MODEL_MAP[DEFAULT_BENEPAR_ALIAS]
            # NEW: Check if minimum requirements (at least one of each type) are met
            minimum_requirements_met = bool(installed_spacy_models and installed_benepar_models) # MODIFIED
        except KeyError: # Handle case where default alias might not be in map
            logging.error("Default model alias not found in map during UI update.")
            minimum_requirements_met = False # MODIFIED
        except Exception as e:
            logging.error(f"Error determining model presence: {e}")
            minimum_requirements_met = False # MODIFIED

        # Check keyboard modifiers for Alt key
        alt_modifier_pressed = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)

        # Update the install/clean button dynamically
        if alt_modifier_pressed or minimum_requirements_met: # MODIFIED condition
            self.install_clean_button.setText("Clean All")
            self.install_clean_button.setToolTip("Clean all installed ANPE models and resources (spaCy, Benepar).")
            self.install_clean_button.setProperty("danger", True)
        else: # Models missing (minimum requirements not met) and Alt not pressed
            self.install_clean_button.setText("Install Defaults")
            # Use the names determined above, even if fallback N/A
            # Need to handle potential KeyError if maps didn't load
            spacy_name_display = SPACY_MODEL_MAP.get(DEFAULT_SPACY_ALIAS, f'{DEFAULT_SPACY_ALIAS} (N/A)')
            benepar_name_display = BENEPAR_MODEL_MAP.get(DEFAULT_BENEPAR_ALIAS, f'{DEFAULT_BENEPAR_ALIAS} (N/A)')
            self.install_clean_button.setToolTip(f"Install required default models:\n"
                                              f"- spaCy: {spacy_name_display}\n"
                                              f"- Benepar: {benepar_name_display}\n"
                                              f"(Hold Alt to Clean All instead)")
            self.install_clean_button.setProperty("danger", False)
        # Force style re-evaluation
        self.install_clean_button.style().unpolish(self.install_clean_button)
        self.install_clean_button.style().polish(self.install_clean_button)

        # Update the general status label and indicator
        if check_error: # Use the error from the status check
            self.model_action_status_label.setText(f"Error: {check_error}")
            self.model_action_indicator.warn() # Show warning state if check failed
        elif not is_any_worker_running: # Only set "updated" if no worker is active
            # Check if models are missing even if check was successful
            if not installed_spacy_models or not installed_benepar_models:
                self.model_action_status_label.setText("Models missing. Please install the required models.") # Optional message change
                self.model_action_indicator.warn() # <<< SET WARNING STATE IF MODELS MISSING
            else:
                # Successful check, all models present, no worker running
                self.model_action_status_label.setText("Model status updated.")
                self.model_action_indicator.idle() # Set idle only if everything is OK
        # If a worker IS running, the status label/indicator state is handled by worker signals
        # ---------------------------------------------------------------------

        # --- Load persistent usage settings AFTER combo boxes are populated ---
        self.load_usage_settings()
        # ---------------------------------------------------------------------

    @pyqtSlot()
    def refresh_status(self):
        """Starts the asynchronous check for model statuses."""
        if self.is_worker_running():
            logging.warning("ModelsPage: refresh_status called while another worker is running.")
            # Optionally provide feedback, e.g., flash the status label
            # self.model_action_status_label.setText("Operation already in progress...")
            # QTimer.singleShot(2000, lambda: self.model_action_status_label.setText("Previous status message...")) # Restore after delay
            return # Don't start a new check if one is running

        logging.debug("ModelsPage: Starting asynchronous status refresh.")
        self.model_action_status_label.setText("Refreshing status...")
        self._set_buttons_enabled(False) # Disable buttons during check
        self.model_action_indicator.checking() # <<< SET STATE TO CHECKING

        # Clean up previous thread/worker if they somehow exist (shouldn't happen with the check above)
        if self.status_check_worker:
            self.status_check_worker.deleteLater()
        if self.status_check_thread:
            self.status_check_thread.quit()
            self.status_check_thread.wait()
            self.status_check_thread.deleteLater()

        # Create and start the worker
        self.status_check_worker = StatusCheckWorker()
        self.status_check_thread = QThread(self)
        self.status_check_worker.moveToThread(self.status_check_thread)

        # Connect signals
        self.status_check_worker.finished.connect(self.on_status_check_finished)
        self.status_check_thread.started.connect(self.status_check_worker.run)

        # Clean up connections (important!)
        self.status_check_worker.finished.connect(self.status_check_thread.quit)
        # Schedule deletion after the event loop processes the quit signal
        self.status_check_worker.finished.connect(self.status_check_worker.deleteLater)
        self.status_check_thread.finished.connect(self.status_check_thread.deleteLater)
        # Clear references in the slot AFTER thread is confirmed finished
        # Use lambda functions to ensure the correct context for setattr
        self.status_check_worker.finished.connect(lambda: setattr(self, 'status_check_worker', None))
        self.status_check_thread.finished.connect(lambda: setattr(self, 'status_check_thread', None))


        self.status_check_thread.start()

    @pyqtSlot(dict)
    def on_status_check_finished(self, status_data: dict):
        """Handles the results from the asynchronous StatusCheckWorker."""
        logging.debug(f"ModelsPage: --- Entered on_status_check_finished ---") # <<< Added log
        logging.debug(f"ModelsPage: Received status_data: {status_data}")

        # Log thread state *before* UI update
        thread_running_before = self.status_check_thread.isRunning() if self.status_check_thread else 'N/A'
        logging.debug(f"ModelsPage: status_check_thread.isRunning() before UI update: {thread_running_before}")

        # Store the latest status
        self.model_status = status_data

        # --- Clear worker/thread references EARLY ---
        # Store references locally for potential deleteLater call
        worker_to_delete = self.status_check_worker
        thread_to_delete = self.status_check_thread
        # Clear instance attributes so is_worker_running() sees them as gone
        self.status_check_worker = None
        self.status_check_thread = None
        logging.debug("ModelsPage: Cleared status_check_worker/thread references.")
        # ---------------------------------------------

        # Update the UI based on the received status
        # NOTE: Button enabling/disabling is NO LONGER done inside this function
        self._update_ui_from_status(status_data)

        # Log worker state *after* UI update and clearing refs
        any_worker_running_after = self.is_worker_running()
        logging.debug(f"ModelsPage: is_worker_running() after UI update and clearing refs: {any_worker_running_after}")

        # --- Set final indicator/status text ---
        # The final state is now fully determined by _update_ui_from_status
        if status_data.get('error'):
            # Error occurred during the check itself, _update_ui_from_status handled this
            pass 
        else:
            # Status check succeeded, _update_ui_from_status handled whether
            # models are present/missing and set the indicator accordingly (idle/warn).
            # No need to set indicator to idle() here anymore.
            pass

        # --- Re-enable buttons reliably ---
        # Now that the status check worker/thread references are cleared,
        # check if any *other* workers are running.
        if not self.is_worker_running(): # No need for ignore_worker_type anymore
             self._set_buttons_enabled(True)
             logging.debug("ModelsPage: Re-enabled buttons as no workers are active.")
        else:
            # If another worker started *while* the check was running, keep buttons disabled
            logging.warning("ModelsPage: Another worker appears to be running after status check finished. Keeping buttons disabled.")

        # --- Schedule deletion for the original worker/thread objects ---
        # This happens after the slot finishes, ensuring they aren't needed anymore.
        # Note: deleteLater was already connected to the finished signals in refresh_status
        # We don't need to call it explicitly here unless we disconnected those signals.
        # Let's keep the original deleteLater connections for safety.
        # if worker_to_delete:
        #     worker_to_delete.deleteLater()
        # if thread_to_delete:
        #     thread_to_delete.deleteLater()
        # logging.debug("ModelsPage: deleteLater calls confirmed/skipped for original status worker/thread.")
        # --------------------------------------------------------------

        logging.debug("ModelsPage: --- Exiting on_status_check_finished ---") # <<< Added log

    def _set_buttons_enabled(self, enabled: bool):
        """Enable/disable action buttons, considering ALL worker states."""
        # Note: This check might be slightly delayed relative to the signal emission
        # We rely on the calling context (e.g., on_X_finished) to know if the specific worker *just* finished.
        is_any_worker_running = self.is_worker_running()
        actual_enabled_state = enabled and not is_any_worker_running

        # logging.debug(f"ModelsPage: _set_buttons_enabled called with enabled={enabled}. is_worker_running={is_any_worker_running}. Resulting state={actual_enabled_state}") # Verbose

        # Global action buttons
        self.refresh_button.setEnabled(actual_enabled_state)
        self.install_clean_button.setEnabled(actual_enabled_state)

        # Grid action buttons
        for alias, button in self.action_buttons.items():
            button.setEnabled(actual_enabled_state)

        # Usage combos
        self.spacy_usage_combo.setEnabled(actual_enabled_state)
        self.benepar_usage_combo.setEnabled(actual_enabled_state)

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
        
        if not model_type or not action or not alias:
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
        self.model_action_indicator.start() # Set state to ACTIVE
        self._clear_log()                            # Clear log text
        
        # Cleanup previous thread/worker (this part is fine)
        if self.install_worker: # Reuse install_worker attribute name
            self.install_worker.deleteLater()
        if self.install_worker_thread:
            self.install_worker_thread.quit()
            self.install_worker_thread.wait()
            self.install_worker_thread.deleteLater()
            
        self.install_worker = ModelActionWorker(action, model_type, alias)
        self.install_worker_thread = QThread(self) 
        self.install_worker.moveToThread(self.install_worker_thread)
        
        # Connect signals
        self.install_worker.progress.connect(self.model_action_status_label.setText)
        self.install_worker.finished.connect(self.on_model_action_finished) # Use the updated finished slot
        self.install_worker.log_message.connect(self._append_log_details) # Connect log signal (PENDING WORKER CHANGE)
        logging.debug(f"ModelsPage: Connected log_message signal from worker to _append_log_details") # <<< ADD LOG
        self.install_worker_thread.started.connect(self.install_worker.run)

        # Cleanup connections - REMOVE deleteLater calls here
        self.install_worker.finished.connect(self.install_worker_thread.quit)

        
        self.install_worker_thread.start()
        
    @pyqtSlot(str, str, bool, str)
    def on_model_action_finished(self, action: str, alias: str, success: bool, message: str):
        """Handle completion of any model install/uninstall worker with explicit wait."""
        logging.debug(f"on_model_action_finished started for action='{action}', alias='{alias}', success={success}")
        # self.model_action_indicator.stop()           # Stop animation # REMOVED
        # REMOVED: self.model_action_indicator.setVisible(False) # Keep visible for idle glow

        
        # Store references before clearing
        worker_to_delete = self.install_worker
        thread_to_wait = self.install_worker_thread

        # Clear internal references immediately
        self.install_worker = None
        self.install_worker_thread = None
        
        # --- MODIFICATION FOR CUSTOM SUCCESS MESSAGE ---
        show_standard_message_box = True
        if success and action == 'install':
            # Determine model_type for the given alias
            model_info = next((m for m in self.manageable_models if m['alias'] == alias), None)
            model_type = model_info.get('type') if model_info else None
            full_model_name = ""
            if model_type == 'spacy':
                full_model_name = SPACY_MODEL_MAP.get(alias, alias)
                # self.log_text contains all messages from the worker's log_callback
                if "SUCCESS_RESTART_NEEDED:" in self.log_text:
                    msg_box = QMessageBox(self.window())
                    msg_box.setWindowTitle("Installation Successful - Restart Required")
                    msg_box.setIcon(QMessageBox.Icon.Information)

                    text = (f"The spaCy model '<b>{full_model_name}</b>' has been installed successfully.<br><br>" 
                           "ANPE Studio must be restarted to fully activate and use this model.<br><br>" 
                           "<b>Important Note regarding potential warnings:</b><br>" 
                           "After installation, if you observe a warning in the ANPE Studio console similar to: <br>" 
                           f"<code>&nbsp;&nbsp;[WARNING] An unexpected error occurred while trying to load spaCy model '{full_model_name}': " 
                           "[E002] Can't find factory for 'curated_transformer'...</code><br>" 
                           "This typically occurs because the application needs a full restart to correctly load all new components for the model. " 
                           "Restarting ANPE Studio should resolve this issue.<br><br>" 
                           "Please save any unsaved work before restarting.")

                    msg_box.setTextFormat(Qt.TextFormat.RichText)
                    msg_box.setText(text)

                    ok_button = msg_box.addButton(QMessageBox.StandardButton.Ok)
                    restart_button = msg_box.addButton("Restart ANPE Studio", QMessageBox.ButtonRole.AcceptRole)
                    msg_box.setDefaultButton(ok_button)
                    
                    msg_box.exec()

                    if msg_box.clickedButton() == restart_button:
                        # Get the top-level QDialog (SettingsDialog) and emit its signal
                        settings_dialog_instance = self.window()
                        if isinstance(settings_dialog_instance, SettingsDialog):
                            settings_dialog_instance.restart_application_requested.emit()
                        else:
                            logging.error("Could not emit restart_application_requested: self.window() is not SettingsDialog.")
                    
                    show_standard_message_box = False
            # No special message for benepar install success, use standard one
        
        if show_standard_message_box:
            if success:
                 QMessageBox.information(self.window(), "Action Complete", message) # Original message from worker
            else:
                 QMessageBox.warning(self.window(), "Action Failed", message) # Original message from worker
        # --- END MODIFICATION ---

        # --- Set Indicator state AFTER message box ---
        if success:
            self.model_action_indicator.idle() # Set state to IDLE on success
        else:
            self.model_action_indicator.warn() # Set state to WARNING on failure

        # --- Explicitly wait for thread and delete objects ---
        if thread_to_wait is not None:
            logging.debug("Waiting for model action worker thread to finish...")
            # Disconnect signals to avoid potential double cleanup or calls after deletion
            try:
                if worker_to_delete:
                    worker_to_delete.progress.disconnect()
                    worker_to_delete.finished.disconnect()
                    # Disconnect log signal (PENDING WORKER CHANGE)
                    try: 
                        worker_to_delete.log_message.disconnect(self._append_log_details)
                    except TypeError:
                        logging.debug("Log message signal likely already disconnected.")
                    except AttributeError:
                        logging.debug("Worker might not have log_message signal yet.")
                thread_to_wait.started.disconnect()
                thread_to_wait.finished.disconnect()
            except TypeError: # Signals might already be disconnected
                logging.debug("Model action signals likely already disconnected.")
            except Exception as e:
                logging.warning(f"Error disconnecting model action signals during explicit cleanup: {e}")

            if thread_to_wait.isRunning():
                thread_to_wait.quit()
                if not thread_to_wait.wait(5000): # Wait up to 5 seconds (install can take time)
                    logging.warning("Model action worker thread did not finish cleanly after quit().")
                else:
                    logging.debug("Model action worker thread finished after wait().")
            else:
                 logging.debug("Model action worker thread was not running when checked.")

            # Schedule deletion
            if worker_to_delete:
                worker_to_delete.deleteLater()
                logging.debug("Scheduled model action worker deletion.")
            thread_to_wait.deleteLater()
            logging.debug("Scheduled model action worker thread deletion.")
        else:
             logging.debug("No model action worker thread reference found to wait on.")
        # ----------------------------------------------------

        # --- Update button state and UI elements directly --- 
        # Manually update the specific button involved in the action
        self._update_button_after_action(action, alias, success)

        # Re-enable buttons if no other workers are running
        if not self.is_worker_running(): # NEW CHECK (worker refs cleared earlier)
            self._set_buttons_enabled(True)
            logging.debug("on_model_action_finished: Re-enabled buttons as no other workers are active.")
        else:
            logging.warning("on_model_action_finished: Keeping buttons disabled as another worker is active.")
            
        # Signal that models *might* have changed (parent can decide to refresh if needed)
        logging.debug("Emitting models_changed signal after model action.")
        self.models_changed.emit() 
        # ----------------------------------------------------

        logging.debug("on_model_action_finished completed.")

    @pyqtSlot()
    def run_clean(self):
        """Confirm and start the background cleaning process."""
        if self.clean_worker_thread and self.clean_worker_thread.isRunning():
            QMessageBox.warning(self.window(), "In Progress", "Model cleanup is already running.")
            return

        # --- Use the (now updated) model_status instead of re-checking --- 
        detected_spacy = []
        detected_benepar = []
        # detected_nltk = False # Removed NLTK detection variable
        if self.model_status: # Check if status dict exists
            detected_spacy = self.model_status.get('spacy_models', [])
            detected_benepar = self.model_status.get('benepar_models', [])
        else:
            # Fallback if status is somehow missing (shouldn't happen ideally)
            logging.warning("model_status not found in run_clean. Confirmation message may be incomplete.")
            # Optionally, could perform the check here as a last resort, 
            # but sticking to the plan of using the stored status.
            pass 
        # --- End change ---

        # --- Format the message dynamically --- # This part remains the same
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
             
        # if detected_nltk: # Removed NLTK message part
            # message_parts.append(" • <b>NLTK:</b> <b>Core Data</b><br>") # Changed text
        # else:
             # message_parts.append(" • <b>NLTK:</b> (None detected)<br>")

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
        self.model_action_indicator.start() # Set state to ACTIVE
        self._clear_log()                            # Clear log text
        
        # Cleanup previous thread/worker (this part is fine)
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
        self.clean_worker.finished.connect(self.on_clean_finished) # Our explicit cleanup slot
        self.clean_worker.log_message.connect(self._append_log_details) # Connect log signal (PENDING WORKER CHANGE)
        self.clean_worker_thread.started.connect(self.clean_worker.run)

        # Clean up connections - REMOVE deleteLater calls here
        self.clean_worker.finished.connect(self.clean_worker_thread.quit) # Quit is okay
        # self.clean_worker.finished.connect(self.clean_worker.deleteLater) # REMOVE THIS
        # self.clean_worker_thread.finished.connect(self.clean_worker_thread.deleteLater) # REMOVE THIS

        self.clean_worker_thread.start()

    @pyqtSlot(dict)
    def on_clean_finished(self, results: dict):
        """Handle completion of the clean process."""
        logging.debug("on_clean_finished started.") # Add logging
        # self.model_action_indicator.stop()           # Stop animation # REMOVED
        # REMOVED: self.model_action_indicator.setVisible(False) # Keep visible for idle glow

        
        # Store references to worker and thread before clearing them later
        worker_to_delete = self.clean_worker
        thread_to_wait = self.clean_worker_thread

        # Clear internal references immediately to prevent re-entry issues
        # The actual objects will be deleted after waiting.
        self.clean_worker = None
        self.clean_worker_thread = None

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

        # --- Set Indicator state AFTER message box ---
        if all_succeeded:
            self.model_action_indicator.idle() # Set state to IDLE on success
        else:
            self.model_action_indicator.warn() # Set state to WARNING on failure

        # --- Explicitly wait for thread and delete objects ---
        if thread_to_wait is not None:
            logging.debug("Waiting for clean worker thread to finish...")
            # Disconnect signals to avoid potential double cleanup or calls after deletion
            try:
                if worker_to_delete:
                    worker_to_delete.progress.disconnect() # Added progress disconnect
                    worker_to_delete.finished.disconnect()
                    # Disconnect log signal (PENDING WORKER CHANGE)
                    try: 
                        worker_to_delete.log_message.disconnect(self._append_log_details)
                    except TypeError:
                        logging.debug("Log message signal likely already disconnected.")
                    except AttributeError:
                        logging.debug("Worker might not have log_message signal yet.")
                thread_to_wait.started.disconnect()
                thread_to_wait.finished.disconnect()
            except TypeError: # Signals might already be disconnected
                logging.debug("Signals likely already disconnected.")
            except Exception as e:
                logging.warning(f"Error disconnecting signals during explicit cleanup: {e}")
                
            if thread_to_wait.isRunning():
                thread_to_wait.quit()
                if not thread_to_wait.wait(3000): # Wait up to 3 seconds
                    logging.warning("Clean worker thread did not finish cleanly after quit().")
                else:
                    logging.debug("Clean worker thread finished after wait().")
            else:
                logging.debug("Clean worker thread was not running when checked.")

            # Schedule deletion
            if worker_to_delete:
                worker_to_delete.deleteLater()
                logging.debug("Scheduled clean_worker deletion.")
            thread_to_wait.deleteLater()
            logging.debug("Scheduled clean_worker_thread deletion.")
        else:
            logging.debug("No clean worker thread reference found to wait on.")
        # ----------------------------------------------------
        
        # --- Update button state and UI elements directly --- 
        # Clean action affects all buttons indirectly, state updated on manual refresh.
        # Just re-enable buttons if appropriate.
        if not self.is_worker_running(ignore_worker_type='clean'): # Ignore the worker that just finished
            self._set_buttons_enabled(True)
            logging.debug("on_clean_finished: Re-enabled buttons as no other workers are active.")
        else:
            logging.warning("on_clean_finished: Keeping buttons disabled as another worker is active.")

        # Signal that models *might* have changed
        logging.debug("Emitting models_changed signal after clean.")
        self.models_changed.emit()
        # --- Trigger refresh to update UI ---
        logging.debug("Triggering refresh status after clean action.")
        QTimer.singleShot(0, self.refresh_status)
        # ------------------------------------

        logging.debug("on_clean_finished completed.")

    @pyqtSlot()
    def on_model_usage_preference_changed(self):
        """Slot called when the model usage preference is changed in the SettingsDialog."""
        logging.debug("ModelsPage: Model usage preference changed.")
        self.save_usage_settings()
        self.model_usage_changed.emit()

    # --- Dynamic Action Handling ---

    @pyqtSlot()
    def handle_install_clean_click(self):
        """Handles clicks on the dynamic Install Defaults / Clean All button."""
        # Re-check state on click, as Alt key might have changed
        alt_modifier_pressed = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)

        # Determine default model presence based on last known status
        all_defaults_present = False # Default assumption
        if self.model_status:
            try:
                # Remove redundant imports here - rely on module-level imports
                # from anpe.utils.setup_models import SPACY_MODEL_MAP, BENEPAR_MODEL_MAP, DEFAULT_SPACY_ALIAS, DEFAULT_BENEPAR_ALIAS
                default_spacy_name = SPACY_MODEL_MAP[DEFAULT_SPACY_ALIAS]
                default_benepar_name = BENEPAR_MODEL_MAP[DEFAULT_BENEPAR_ALIAS]
                installed_spacy = self.model_status.get('spacy_models', [])
                installed_benepar = self.model_status.get('benepar_models', [])
                all_defaults_present = (
                    default_spacy_name in installed_spacy and
                    default_benepar_name in installed_benepar
                )
            except Exception as e:
                logging.error(f"Error re-checking default model presence on click: {e}")
                # Proceed based on button text as fallback?
                button_text = self.install_clean_button.text()
                if "Clean" in button_text:
                    all_defaults_present = True
                else:
                    all_defaults_present = False

        if alt_modifier_pressed or all_defaults_present:
            # If Alt is held OR all models are present -> Clean All
            self.run_clean()
        else:
            # If Alt is NOT held AND models are missing -> Install Defaults
            self.run_install_defaults()

    def run_install_defaults(self):
        """Start the background default model installation process."""
        if (hasattr(self, 'install_defaults_thread') and self.install_defaults_thread and self.install_defaults_thread.isRunning()) or \
           (self.install_worker_thread and self.install_worker_thread.isRunning()) or \
           (self.clean_worker_thread and self.clean_worker_thread.isRunning()):
            QMessageBox.warning(self.window(), "In Progress", "Another model operation is already running.")
            return

        # Confirmation (optional, but good practice)
        reply = QMessageBox.question(
            self.window(),
            "Confirm Install Defaults",
            "This will attempt to download and install any missing default ANPE models (spaCy-md, Benepar-default). Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self._set_buttons_enabled(False)
        self.model_action_status_label.setText("Starting default installation...")
        self.model_action_indicator.start() # Set state to ACTIVE
        self._clear_log()                            # Clear log text

        # Cleanup previous thread/worker (use dedicated attributes)
        if hasattr(self, 'install_defaults_worker') and self.install_defaults_worker:
            self.install_defaults_worker.deleteLater()
        if hasattr(self, 'install_defaults_thread') and self.install_defaults_thread:
            self.install_defaults_thread.quit()
            self.install_defaults_thread.wait()
            self.install_defaults_thread.deleteLater()

        self.install_defaults_worker = InstallDefaultsWorker()
        self.install_defaults_thread = QThread(self)
        self.install_defaults_worker.moveToThread(self.install_defaults_thread)

        # Connect signals
        self.install_defaults_worker.progress.connect(self.model_action_status_label.setText)
        self.install_defaults_worker.finished.connect(self.on_install_defaults_finished)
        self.install_defaults_worker.log_message.connect(self._append_log_details) # Connect log signal (PENDING WORKER CHANGE)
        self.install_defaults_thread.started.connect(self.install_defaults_worker.run)

        # Clean up connections
        self.install_defaults_worker.finished.connect(self.install_defaults_thread.quit)

        self.install_defaults_thread.start()

    @pyqtSlot(bool, str)
    def on_install_defaults_finished(self, success: bool, message: str):
        """Handle completion of the default install process."""
        logging.debug("on_install_defaults_finished started.")
        # self.model_action_indicator.stop() # REMOVED
        # REMOVED: self.model_action_indicator.setVisible(False) # Keep visible for idle glow

        # Store references before clearing
        worker_to_delete = self.install_defaults_worker if hasattr(self, 'install_defaults_worker') else None
        thread_to_wait = self.install_defaults_thread if hasattr(self, 'install_defaults_thread') else None

        # Clear internal references immediately
        self.install_defaults_worker = None
        self.install_defaults_thread = None

        # Show message box first
        if success:
             QMessageBox.information(self.window(), "Install Defaults Complete", message)
        else:
             QMessageBox.warning(self.window(), "Install Defaults Failed", message)

        # --- Set Indicator state AFTER message box ---
        if success:
            self.model_action_indicator.idle() # Set state to IDLE on success
        else:
            self.model_action_indicator.warn() # Set state to WARNING on failure

        # --- Explicitly wait for thread and delete objects ---
        if thread_to_wait is not None:
            logging.debug("Waiting for install defaults worker thread to finish...")
            try:
                if worker_to_delete:
                    # Assuming signals: progress, finished
                    worker_to_delete.progress.disconnect()
                    worker_to_delete.finished.disconnect()
                    # Disconnect log signal (PENDING WORKER CHANGE)
                    try: 
                        worker_to_delete.log_message.disconnect(self._append_log_details)
                    except TypeError:
                        logging.debug("Log message signal likely already disconnected.")
                    except AttributeError:
                        logging.debug("Worker might not have log_message signal yet.")
                thread_to_wait.started.disconnect()
                thread_to_wait.finished.disconnect()
            except TypeError: # Signals might already be disconnected
                logging.debug("Install defaults signals likely already disconnected.")
            except Exception as e:
                logging.warning(f"Error disconnecting install defaults signals during explicit cleanup: {e}")

            if thread_to_wait.isRunning():
                thread_to_wait.quit()
                if not thread_to_wait.wait(5000): # Wait up to 5 seconds
                    logging.warning("Install defaults worker thread did not finish cleanly after quit().")
                else:
                    logging.debug("Install defaults worker thread finished after wait().")
            else:
                 logging.debug("Install defaults worker thread was not running when checked.")

            if worker_to_delete:
                worker_to_delete.deleteLater()
                logging.debug("Scheduled install_defaults_worker deletion.")
            thread_to_wait.deleteLater()
            logging.debug("Scheduled install_defaults_thread deletion.")
        else:
             logging.debug("No install defaults worker thread reference found to wait on.")

        # --- Update button state and UI elements directly --- 
        # Install Defaults action affects buttons indirectly, state updated on manual refresh.
        # Just re-enable buttons if appropriate.
        if not self.is_worker_running(ignore_worker_type='defaults'): # Ignore the worker that just finished
            self._set_buttons_enabled(True)
            logging.debug("on_install_defaults_finished: Re-enabled buttons as no other workers are active.")
        else:
            logging.warning("on_install_defaults_finished: Keeping buttons disabled as another worker is active.")

        # Signal that models *might* have changed
        logging.debug("Emitting models_changed signal after install defaults.")
        self.models_changed.emit()
        # --- Trigger refresh to update UI ---
        logging.debug("Triggering refresh status after install defaults action.")
        QTimer.singleShot(0, self.refresh_status)
        # ------------------------------------

        logging.debug("on_install_defaults_finished completed.")

    # --- End Dynamic Action Handling ---

    # --- Log Panel Handling ---

    @pyqtSlot(str)
    def _append_log_details(self, message: str):
        """Append a message to the log display in the model action log dialog."""
        self.log_text += message + "\n"  # Append to the primary string buffer
        if self.log_text_edit: # Check if the QTextEdit widget exists
            self.log_text_edit.append(message) # Append to the widget for live update
        else:
            logging.debug("_append_log_details: log_text_edit (QTextEdit widget) does not exist yet. Message buffered.")

    @pyqtSlot()
    def _clear_log(self):
        """Clear the log display in the model action log dialog."""
        self.log_text = ""  # Clear the primary string buffer
        if self.log_text_edit: # Check if the QTextEdit widget exists
            self.log_text_edit.clear()
        else:
            logging.debug("_clear_log called but log_text_edit (QTextEdit widget) does not exist yet.")

    @pyqtSlot()
    def _show_log_dialog(self):
        """Create and show (or raise) the dialog containing model action logs."""
        # Create dialog if it doesn't exist
        if not self.log_dialog:
            parent_dialog = self.window()
            self.log_dialog = QDialog(parent_dialog)
            self.log_dialog.setWindowTitle("Model Action Details")
            self.log_dialog.setMinimumSize(600, 300)
            
            # Create layout
            layout = QVBoxLayout(self.log_dialog)
            
            # Create text edit and assign to ModelsPage attribute
            self.log_text_edit = QTextEdit()
            self.log_text_edit.setReadOnly(True)
            self.log_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.log_text_edit.setStyleSheet("""
                QTextEdit { 
                    background-color: #f8f8f8; 
                    border: 1px solid #e0e0e0; 
                    border-radius: 3px; 
                    font-family: Consolas, monaco, monospace; 
                    font-size: 9pt; 
                    color: #333;
                }
            """)
            
            # Set placeholder text
            self.log_text_edit.setPlaceholderText("Model install/update details will be displayed here.")
            
            # Populate with current buffered log text
            self.log_text_edit.setText(self.log_text)
            
            # Add close button
            close_button = QPushButton("Close") # Changed text
            # REMOVED: clear_button.clicked.connect(self._clear_log)
            close_button.clicked.connect(self.log_dialog.accept) # Connect to accept
            close_button.setFixedWidth(100)
            
            # Add button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch(1)
            button_layout.addWidget(close_button) # Changed variable name
            
            # Add widgets to layout
            layout.addWidget(self.log_text_edit) # Add the correct widget
            layout.addLayout(button_layout)
            
            # Position dialog relative to main window
            self._center_dialog_on_parent(self.log_dialog)
        
        # Show the dialog
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()
    
    def _center_dialog_on_parent(self, dialog):
        """Centers a dialog on its parent."""
        parent = dialog.parent()
        if parent:
            parent_geo = parent.geometry()
            dialog_geo = dialog.geometry()
            
            # Calculate center position
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) / 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) / 2
            
            # --- Cast to int early --- 
            x_int = int(x)
            y_int = int(y)
            # --- End Cast ---
            
            # Ensure dialog is within screen bounds
            # Use integer coordinates for screenAt
            screen = QApplication.screenAt(QPoint(x_int, y_int)) 
            if not screen:
                screen = QApplication.primaryScreen()
            
            if screen:
                screen_geo = screen.availableGeometry()
                # Adjust using integer coordinates
                x_int = max(screen_geo.x(), min(x_int, screen_geo.x() + screen_geo.width() - dialog_geo.width()))
                y_int = max(screen_geo.y(), min(y_int, screen_geo.y() + screen_geo.height() - dialog_geo.height()))
            
            dialog.move(x_int, y_int) # Use final integer coordinates

    # --- End Log Panel Handling ---

    # --- Event Handling for Alt Key --- 

    def _update_dynamic_button_state(self, alt_pressed_hint: bool | None = None):
        """Updates the text, tooltip, and style of the install/clean button based on model status and Alt key.
        
        Args:
            alt_pressed_hint: If True/False, overrides the global modifier check.
                              If None, uses QApplication.keyboardModifiers().
        """
        # Determine default model presence (reusing logic structure)
        minimum_requirements_met = False # MODIFIED
        default_spacy_name = "N/A"
        default_benepar_name = "N/A"
        if self.model_status:
            try:
                default_spacy_name = SPACY_MODEL_MAP[DEFAULT_SPACY_ALIAS]
                default_benepar_name = BENEPAR_MODEL_MAP[DEFAULT_BENEPAR_ALIAS]
                installed_spacy = self.model_status.get('spacy_models', [])
                installed_benepar = self.model_status.get('benepar_models', [])

                minimum_requirements_met = bool(installed_spacy and installed_benepar) # MODIFIED
            except Exception as e:
                logging.error(f"Error determining default model presence for dynamic button: {e}")
                minimum_requirements_met = False # Fallback

        # Check keyboard modifiers for Alt key, using hint if provided
        if alt_pressed_hint is not None:
            alt_modifier_pressed = alt_pressed_hint
            logging.debug(f"_update_dynamic_button_state using hint: {alt_modifier_pressed}")
        else:
            alt_modifier_pressed = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)
            logging.debug(f"_update_dynamic_button_state using global state: {alt_modifier_pressed}")

        # Update the install/clean button dynamically
        if alt_modifier_pressed or minimum_requirements_met: # MODIFIED condition
            self.install_clean_button.setText("Clean All")
            self.install_clean_button.setToolTip("Clean all installed ANPE models and resources (spaCy, Benepar).")
            self.install_clean_button.setProperty("danger", True)
        else: # Models missing and Alt not pressed
            self.install_clean_button.setText("Install Defaults")
            # Use the names determined above, even if fallback N/A
            self.install_clean_button.setToolTip(f"Install required default models:\n- spaCy: {default_spacy_name}\n- Benepar: {default_benepar_name}\n(Hold Alt to Clean All instead)")
            self.install_clean_button.setProperty("danger", False)
            
        # Force style re-evaluation
        self.install_clean_button.style().unpolish(self.install_clean_button)
        self.install_clean_button.style().polish(self.install_clean_button)

    # --- End Event Handling ---

    def is_worker_running(self, ignore_worker_type: str | None = None) -> bool:
        """Check if any model management or status check worker thread is active.

        Args:
            ignore_worker_type: If provided (e.g., 'status', 'install', 'clean', 'defaults'),
                                exclude that worker type from the check.
        """
        install_active = (ignore_worker_type != 'install') and self.install_worker_thread and self.install_worker_thread.isRunning()
        clean_active = (ignore_worker_type != 'clean') and self.clean_worker_thread and self.clean_worker_thread.isRunning()
        defaults_active = (ignore_worker_type != 'defaults') and self.install_defaults_thread and self.install_defaults_thread.isRunning()
        status_check_active = (ignore_worker_type != 'status') and self.status_check_thread and self.status_check_thread.isRunning()

        running = install_active or clean_active or defaults_active or status_check_active
        # Optional verbose logging:
        # if ignore_worker_type:
        #     logging.debug(f"is_worker_running (ignoring '{ignore_worker_type}'): install={install_active}, clean={clean_active}, defaults={defaults_active}, status={status_check_active} -> {running}")
        # else:
        #     logging.debug(f"is_worker_running: install={install_active}, clean={clean_active}, defaults={defaults_active}, status={status_check_active} -> {running}")
        return running

    def _update_button_after_action(self, action: str, alias: Optional[str], success: bool):
        """Update the specific button(s) involved in the last model action, or trigger refresh."""
        logging.debug(f"_update_button_after_action called with action='{action}', alias='{alias}', success={success}")

        if action in ['install', 'uninstall'] and alias:
            button = self.action_buttons.get(alias)
            if not button:
                logging.warning(f"_update_button_after_action: Could not find button for alias '{alias}'")
                return

            if success:
                # Find model name for tooltip update (handle potential missing info)
                model_info = next((m for m in self.manageable_models if m['alias'] == alias), None)
                model_name = model_info.get('name', f"{alias} (Unknown Name)") if model_info else f"{alias} (Unknown Name)"
                
                if action == 'install':
                    button.setText("Uninstall")
                    button.setProperty("danger", True)
                    button.setToolTip(f"Uninstall {model_name}")
                    logging.debug(f"Button '{alias}' updated to Uninstall state.")
                elif action == 'uninstall':
                    button.setText("Install")
                    button.setProperty("danger", False)
                    button.setToolTip(f"Install {model_name}")
                    logging.debug(f"Button '{alias}' updated to Install state.")
                
                # Force style re-evaluation
                button.style().unpolish(button)
                button.style().polish(button)
                # Always refresh status after a successful individual action
                logging.debug(f"Individual action '{action}' for alias '{alias}' succeeded. Triggering refresh.")
                QTimer.singleShot(0, self.refresh_status)
            else:
                # If the action failed, the state is uncertain. Trigger a refresh for accuracy.
                logging.warning(f"Action '{action}' for alias '{alias}' failed. Triggering refresh for accurate state.")
                # Use QTimer.singleShot to avoid potential issues calling refresh directly from within slot
                QTimer.singleShot(0, self.refresh_status)
        
        elif action in ['install_defaults', 'clean_all']:
            # For global actions, the state of multiple buttons might change.
            # Triggering a full refresh is the most reliable way to update the UI.
            logging.debug(f"Global action '{action}' completed. Triggering refresh status.")
            # Use QTimer.singleShot to avoid potential issues calling refresh directly from within slot
            QTimer.singleShot(0, self.refresh_status)
        else:
             logging.warning(f"_update_button_after_action: Unknown action type '{action}' received.")


class CorePage(QWidget):
    """Page for checking and updating the ANPE core package."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CorePage")
        
        self.worker_thread = None
        self.worker = None
        self.current_version = "N/A"
        self.latest_version = "N/A"
        # Log attributes
        self.log_dialog = None 
        self.log_text = ""
        # Environment info attributes
        self.python_version = "N/A"
        self.spacy_version = "N/A"
        self.benepar_version = "N/A"
        self.nltk_version = "N/A" # <<< Added NLTK version attribute
        # UI element attributes
        self.core_action_indicator = None
        self.show_core_log_button = None
        # Environment labels
        self.python_version_label = None
        self.spacy_version_label = None
        self.benepar_version_label = None
        self.nltk_version_label = None # <<< Added NLTK label attribute

        self.setup_ui()
        self.load_initial_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20) 
        layout.setSpacing(15)

        # Use QGroupBox for better visual separation
        status_group_box = QGroupBox("ANPE Core Package") # Renamed group box
        status_group_layout = QVBoxLayout(status_group_box)
        status_group_layout.setSpacing(10)

        # --- Explanatory Text ---
        explanation_style = "font-size: 9pt; color: #444; margin-bottom: 10px;"
        explanation_label1 = QLabel(
            "This GUI application is built upon the <b>ANPE core</b> Python library, "
            "which handles the underlying noun phrase extraction logic."
        )
        explanation_label1.setWordWrap(True)
        explanation_label1.setStyleSheet(explanation_style)
        status_group_layout.addWidget(explanation_label1)

        explanation_label2 = QLabel(
            "You can update the core library manually using the button below."
        )
        explanation_label2.setWordWrap(True)
        explanation_label2.setStyleSheet(explanation_style)
        status_group_layout.addWidget(explanation_label2)

        # --- Version Status Form ---
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

        # --- Activity Indicator --- 
        self.core_action_indicator = PulsingActivityIndicator()
        self.core_action_indicator.setFixedSize(20, 20)
        # self.core_action_indicator.setVisible(False) # REMOVED
        self.core_action_indicator.set_color(PRIMARY_COLOR)
        # --------------------------

        # --- Details Button (Show Log Dialog) --- 
        self.show_core_log_button = QToolButton()
        self.show_core_log_button.setIcon(ResourceManager.get_icon("external-link.svg"))
        self.show_core_log_button.setIconSize(QSize(12, 12))
        self.show_core_log_button.setFixedSize(22, 22)
        self.show_core_log_button.setToolTip("Show Core Action Details Log")
        self.show_core_log_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_core_log_button.setStyleSheet("""
            QToolButton { background-color: #e0e0e0; border: none; border-radius: 11px; padding: 0px; }
            QToolButton:hover { background-color: #cccccc; }
            QToolButton:pressed { background-color: #bbbbbb; }
        """)
        # -----------------------------------------

        form_layout.addRow("Current Installed Version:", self.current_version_label)
        form_layout.addRow("Latest Available Version:", self.latest_version_label)
        
        # --- Status, Indicator, and Log Button Layout --- 
        status_feedback_layout = QHBoxLayout()
        status_feedback_layout.setSpacing(8)
        status_feedback_layout.setContentsMargins(0, 5, 0, 5)
        status_feedback_layout.addWidget(self.show_core_log_button) # Add log button
        status_feedback_layout.addWidget(self.core_action_indicator) # Add indicator
        status_feedback_layout.addWidget(self.status_label, 1) # Status label takes stretch
        # ------------------------------------------------

        # --- Button Layout --- 
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.check_update_button)
        # --- Add PyPI Button ---
        self.pypi_button = QPushButton("View on PyPI")
        self.pypi_button.setToolTip("Open the ANPE project page on the Python Package Index (PyPI)")
        button_layout.addWidget(self.pypi_button)
        # ----------------------
        button_layout.addStretch()
        # --------------------

        status_group_layout.addLayout(form_layout)
        status_group_layout.addLayout(status_feedback_layout) # Add the combined feedback layout
        status_group_layout.addLayout(button_layout)
        # REMOVED: status_group_layout.addStretch(1) # Stretch removed from here

        layout.addWidget(status_group_box)

        # --- Environment Details Group Box ---
        env_group_box = QGroupBox("Environment Details")
        env_layout = QVBoxLayout(env_group_box)
        env_layout.setSpacing(8)

        env_form_layout = QFormLayout()
        env_form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        env_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        env_form_layout.setHorizontalSpacing(20)
        env_form_layout.setVerticalSpacing(8) # Slightly tighter spacing

        self.python_version_label = QLabel("Checking...")
        self.spacy_version_label = QLabel("Checking...")
        self.benepar_version_label = QLabel("Checking...")
        self.nltk_version_label = QLabel("Checking...") # <<< Create NLTK label

        env_form_layout.addRow("Python Version:", self.python_version_label)
        env_form_layout.addRow("spaCy Version:", self.spacy_version_label)
        env_form_layout.addRow("Benepar Version:", self.benepar_version_label)
        env_form_layout.addRow("NLTK Version:", self.nltk_version_label) # <<< Add NLTK row

        env_layout.addLayout(env_form_layout)
        layout.addWidget(env_group_box)
        # -----------------------------------

        layout.addStretch(1) # Add stretch to main layout to push groups up

        # Connect button signals
        self.check_update_button.clicked.connect(self.handle_core_action)
        self.show_core_log_button.clicked.connect(self._show_core_log_dialog)
        self.pypi_button.clicked.connect(self._open_pypi_page) # Connect PyPI button

    def load_initial_data(self):
        """Get the current installed version (assuming core is installed)."""
        # --- Fetch Core Version ---
        try:
            self.current_version = importlib.metadata.version(CORE_PACKAGE_NAME)
            self.current_version_label.setText(self.current_version)
            self.status_label.setText("Ready to check for updates.")
        except importlib.metadata.PackageNotFoundError:
            # Handle case where core package itself might be missing (unlikely if GUI runs)
            self.current_version = "N/A (Not Found)"
            self.current_version_label.setText(f"<i style='color: {ERROR_COLOR};'>{self.current_version}</i>")
            self.status_label.setText("ANPE core package not found.")
            logging.error(f"Core package '{CORE_PACKAGE_NAME}' not found.")
            self.check_update_button.setEnabled(False) # Disable check/update if core missing
            self.check_update_button.setText("Core Missing")
            return # Skip further checks if core is missing
        except Exception as e:
            self.current_version = "N/A (Error)"
            self.current_version_label.setText(f"<i style='color: {ERROR_COLOR};'>{self.current_version}</i>")
            self.status_label.setText(f"Error reading core version: {e}")
            logging.error(f"Error getting current core version: {e}", exc_info=True)
            # Button state handled below

        # Button should always be enabled unless worker running (initial state)
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("Check for Updates") # Ensure initial text

        # --- Fetch Environment Details ---
        # Python Version
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self.python_version_label.setText(self.python_version)

        # spaCy Version
        try:
            self.spacy_version = importlib.metadata.version("spacy")
            self.spacy_version_label.setText(self.spacy_version)
        except importlib.metadata.PackageNotFoundError:
            self.spacy_version = "N/A (Not Found)"
            self.spacy_version_label.setText(f"<i style='color: orange;'>{self.spacy_version}</i>")
        except Exception as e:
            self.spacy_version = "N/A (Error)"
            self.spacy_version_label.setText(f"<i style='color: {ERROR_COLOR};'>{self.spacy_version}</i>")
            logging.error(f"Error getting spacy version: {e}", exc_info=True)

        # Benepar Version
        try:
            self.benepar_version = importlib.metadata.version("benepar")
            self.benepar_version_label.setText(self.benepar_version)
        except importlib.metadata.PackageNotFoundError:
            self.benepar_version = "N/A (Not Found)"
            self.benepar_version_label.setText(f"<i style='color: orange;'>{self.benepar_version}</i>")
        except Exception as e:
            self.benepar_version = "N/A (Error)"
            self.benepar_version_label.setText(f"<i style='color: {ERROR_COLOR};'>{self.benepar_version}</i>")
            logging.error(f"Error getting benepar version: {e}", exc_info=True)

        # NLTK Version
        try:
            self.nltk_version = importlib.metadata.version("nltk")
            self.nltk_version_label.setText(self.nltk_version)
        except importlib.metadata.PackageNotFoundError:
            self.nltk_version = "N/A (Not Found)"
            self.nltk_version_label.setText(f"<i style='color: orange;'>{self.nltk_version}</i>")
        except Exception as e:
            self.nltk_version = "N/A (Error)"
            self.nltk_version_label.setText(f"<i style='color: {ERROR_COLOR};'>{self.nltk_version}</i>")
            logging.error(f"Error getting nltk version: {e}", exc_info=True)

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
            # self.core_action_indicator.setVisible(True) # REMOVED
            # self.core_action_indicator.start() # REMOVED
            self.core_action_indicator.checking() # Set state to CHECKING
            self.check_update_button.setEnabled(False)
            self.latest_version_label.setText("Checking...")
            
            # Connect check signals
            self.worker.check_finished.connect(self.on_check_finished)
            # Connect log signal for check (if worker emits any)
            self.worker.log_message.connect(self._append_core_log_details) 
            self.worker_thread.started.connect(self.worker.run_check)
            # Cleanup connections
            self.worker.check_finished.connect(self.worker_thread.quit)
            self.worker.check_finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            
            self.worker_thread.start()
            
        elif "Update ANPE Core" in button_text: # Make check more robust
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
            # self.core_action_indicator.setVisible(True) # REMOVED
            # self.core_action_indicator.start() # REMOVED
            self.core_action_indicator.start() # Set state to ACTIVE
            self.check_update_button.setEnabled(False)
            
            # Connect update signals
            self.worker.update_progress.connect(self.on_update_progress)
            self.worker.update_finished.connect(self.on_update_finished)
            self.worker.log_message.connect(self._append_core_log_details) # Connect log signal
            self.worker_thread.started.connect(self.worker.run_update)
            # Cleanup connections
            self.worker.update_finished.connect(self.worker_thread.quit)
            self.worker.update_finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            
            self.worker_thread.start()
            
    @pyqtSlot(str, str, str)
    def on_check_finished(self, latest_version, current_version, error_string):
        """Handle the result of the PyPI version check."""
        # self.core_action_indicator.stop() # REMOVED
        # REMOVED: self.core_action_indicator.setVisible(False) # Keep visible for idle glow
        self.worker_thread = None # Allow new actions
        self.worker = None
        
        if error_string:
            self.status_label.setText(f"Error checking for updates: {error_string}")
            self.latest_version_label.setText("Error")
            self.check_update_button.setText("Check for Updates")
            # Button should remain enabled to allow retrying the check
            self.check_update_button.setEnabled(True) 
            self.core_action_indicator.warn() # Set state to WARNING on check error
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
                self.check_update_button.setEnabled(True) # Original logic: enable if update needed
            else: # Up-to-date or latest is N/A
                self.status_label.setText("ANPE core package is up to date.")
                self.check_update_button.setText("Up to Date")
                self.check_update_button.setEnabled(False) # Disable if up to date
            # Set indicator to IDLE on successful check (regardless of update needed)
            self.core_action_indicator.idle() # Set state to IDLE on success

    @pyqtSlot(int, str)
    def on_update_progress(self, value, message):
        """Update status label during update. Value is ignored for indicator."""
        self.status_label.setText(message) # Just update the status label

    @pyqtSlot(bool, str)
    def on_update_finished(self, success, message):
        """Handle completion of the update process."""
        # self.core_action_indicator.stop() # REMOVED
        # REMOVED: self.core_action_indicator.setVisible(False) # Keep visible for idle glow
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
             self.core_action_indicator.idle() # Set state to IDLE on update success
        else:
             # Error message already appended to log in worker
             QMessageBox.warning(self.window(), "Update Failed", message)
             self.status_label.setText(f"<span style='color: {ERROR_COLOR};'>Update failed. See details or logs.</span>")
             # Reset button state to allow re-check/re-try
             self.check_update_button.setText("Check for Updates") 
             self.check_update_button.setEnabled(True)
             self.core_action_indicator.warn() # Set state to WARNING on update failure

    # --- Log Dialog Methods (Adapted from ModelsPage) --- 

    @pyqtSlot(str)
    def _append_core_log_details(self, message: str):
        """Appends a message to the core action log details."""
        self.log_text += message + "\n"
        
        # If log dialog exists and is visible, update it
        if self.log_dialog and self.log_dialog.isVisible():
            self.log_dialog.text_edit.append(message)
    
    @pyqtSlot()
    def _show_core_log_dialog(self):
        """Shows a dialog with the core action log details."""
        logging.debug("CorePage: _show_core_log_dialog called.") # Add logging
        # Create dialog if it doesn't exist
        if not self.log_dialog:
            parent_dialog = self.window()
            self.log_dialog = QDialog(parent_dialog)
            self.log_dialog.setWindowTitle("Core Action Details") # Updated Title
            self.log_dialog.setMinimumSize(600, 300)
            
            # Create layout
            layout = QVBoxLayout(self.log_dialog)
            
            # Create text edit
            self.log_dialog.text_edit = QTextEdit()
            self.log_dialog.text_edit.setReadOnly(True)
            self.log_dialog.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.log_dialog.text_edit.setStyleSheet("""
                QTextEdit { 
                    background-color: #f8f8f8; 
                    border: 1px solid #e0e0e0; 
                    border-radius: 3px; 
                    font-family: Consolas, monaco, monospace; 
                    font-size: 9pt; 
                    color: #333;
                }
            """)
            
            # Set placeholder text
            self.log_dialog.text_edit.setPlaceholderText("Core action log details will be displayed here.")
            
            # Add current log text if any
            if self.log_text:
                self.log_dialog.text_edit.setText(self.log_text)
            
            # Add close button
            close_button = QPushButton("Close") # Changed text
            # REMOVED: clear_button.clicked.connect(self._clear_log)
            close_button.clicked.connect(self.log_dialog.accept) # Connect to accept
            close_button.setFixedWidth(100)
            
            # Add button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch(1)
            button_layout.addWidget(close_button) # Changed variable name
            
            # Add widgets to layout
            layout.addWidget(self.log_dialog.text_edit)
            layout.addLayout(button_layout)
            
            # Position dialog relative to main window
            self._center_dialog_on_parent(self.log_dialog)
        
        # Show the dialog
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()
    
    def _center_dialog_on_parent(self, dialog):
        """Centers a dialog on its parent."""
        parent = dialog.parent()
        if parent:
            parent_geo = parent.geometry()
            dialog_geo = dialog.geometry()
            
            # Calculate center position
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) / 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) / 2
            
            # --- Cast to int early --- 
            x_int = int(x)
            y_int = int(y)
            # --- End Cast ---
            
            # Ensure dialog is within screen bounds
            # Use integer coordinates for screenAt
            screen = QApplication.screenAt(QPoint(x_int, y_int)) 
            if not screen:
                screen = QApplication.primaryScreen()
            
            if screen:
                screen_geo = screen.availableGeometry()
                # Adjust using integer coordinates
                x_int = max(screen_geo.x(), min(x_int, screen_geo.x() + screen_geo.width() - dialog_geo.width()))
                y_int = max(screen_geo.y(), min(y_int, screen_geo.y() + screen_geo.height() - dialog_geo.height()))
            
            dialog.move(x_int, y_int) # Use final integer coordinates

    # --- End Log Panel Handling ---

    def is_worker_running(self) -> bool:
        """Check if the core update worker thread is active."""
        return self.worker_thread and self.worker_thread.isRunning()

    # --- PyPI Link Method ---
    def _open_pypi_page(self):
        """Opens the ANPE PyPI project page in the default web browser."""
        url = QUrl("https://pypi.org/project/anpe/")
        if not QDesktopServices.openUrl(url):
            logging.error(f"Could not open PyPI URL: {url.toString()}")
            QMessageBox.warning(self, "Error", f"Could not open the PyPI project page in your browser:\n{url.toString()}")
    # -----------------------


class AboutPage(QWidget):
    """Displays About information: versions, author, links, acknowledgements."""
    def __init__(self, gui_version: str, core_version: str, parent=None):
        super().__init__(parent)
        self.gui_version = gui_version
        self.core_version = core_version
        self.setObjectName("AboutPage")

        self.gui_update_worker_thread = None
        self.gui_update_worker = None
        self.gui_version_value_label = None       
        self.update_now_button = None           
        self.latest_gui_version_info = None     
        self._first_show = True                 

        # Dedicated status elements
        self.gui_update_status_label = None
        self.gui_update_indicator = None

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 20, 30, 20)

        # --- Header Section (remains the same) ---
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setSpacing(15)
        header_layout.setContentsMargins(0, 0, 0, 10)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        try:
             pixmap = ResourceManager.get_pixmap("app_icon_logo_transparent.png")
        except ImportError:
             logging.warning("ResourceManager not found, using placeholder icon.")
             pixmap = QPixmap(100, 100)
             pixmap.fill(Qt.GlobalColor.gray)
        pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(100, 100)
        header_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_label = QLabel("ANPE Studio")
        title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {PRIMARY_COLOR};")
        title_layout.addWidget(title_label)
        subtitle_label = QLabel(" Another Noun Phrase Extractor Studio")
        subtitle_label.setStyleSheet("font-size: 16px; color: #666666;")
        title_layout.addWidget(subtitle_label)
        header_layout.addWidget(title_container, 1)
        header_layout.setAlignment(title_container, Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(header_widget)

        # --- Info Grid ---
        info_widget = QWidget()
        info_layout = QGridLayout(info_widget) 
        info_layout.setContentsMargins(10, 0, 10, 10)
        info_layout.setSpacing(8)
        info_layout.setColumnStretch(1, 1) 
        label_width = 110

        # GUI Version with inline status and update button
        gui_label_title = QLabel("GUI Version:")
        gui_label_title.setStyleSheet("font-weight: bold;")
        gui_label_title.setFixedWidth(label_width)
        info_layout.addWidget(gui_label_title, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop) 

        gui_version_container = QWidget()
        gui_version_layout = QHBoxLayout(gui_version_container)
        gui_version_layout.setContentsMargins(0,0,0,0)
        gui_version_layout.setSpacing(5) # Reduced spacing for a tighter look

        self.gui_version_value_label = QLabel(self.gui_version) 
        self.gui_version_value_label.setTextFormat(Qt.TextFormat.RichText) 
        gui_version_layout.addWidget(self.gui_version_value_label)

        # Removed self.gui_version_status_indicator from here

        self.update_now_button = QToolButton() 
        try:
            update_icon = ResourceManager.get_icon("external-link.svg")
            if not update_icon.isNull():
                self.update_now_button.setIcon(update_icon)
                self.update_now_button.setIconSize(QSize(16,16)) 
            else:
                logging.warning("Could not load external-link.svg for update_now_button, using text.")
                self.update_now_button.setText("↪") 
        except Exception as e:
            logging.warning(f"Could not load icon for update_now_button: {e}. Using text.")
            self.update_now_button.setText("↪") 
        self.update_now_button.setFixedSize(22, 22) 
        self.update_now_button.setToolTip("Go to download page")
        self.update_now_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_now_button.setStyleSheet("""
            QToolButton { background-color: transparent; border: none; border-radius: 4px; padding: 2px; }
            QToolButton:hover { background-color: #e0e0e0; }
            QToolButton:pressed { background-color: #cccccc; }
        """)
        self.update_now_button.setVisible(False) 
        gui_version_layout.addWidget(self.update_now_button)
        gui_version_layout.addStretch(1) 
        info_layout.addWidget(gui_version_container, 0, 1)

        # Core Version
        core_label_title = QLabel("Core Version:")
        core_label_title.setStyleSheet("font-weight: bold;")
        core_label_title.setFixedWidth(label_width)
        core_value_label = QLabel(self.core_version)
        info_layout.addWidget(core_label_title, 1, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(core_value_label, 1, 1, Qt.AlignmentFlag.AlignLeft)
        author_label_title = QLabel("Author:")
        author_label_title.setStyleSheet("font-weight: bold;")
        author_label_title.setFixedWidth(label_width)
        author_value_label = QLabel("Richard Chen (@rcverse)")
        info_layout.addWidget(author_label_title, 2, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(author_value_label, 2, 1, Qt.AlignmentFlag.AlignLeft)
        license_label_title = QLabel("License:")
        license_label_title.setStyleSheet("font-weight: bold;")
        license_label_title.setFixedWidth(label_width)
        license_value_label = QLabel("GNU General Public License v3")
        info_layout.addWidget(license_label_title, 3, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(license_value_label, 3, 1, Qt.AlignmentFlag.AlignLeft)
        email_label_title = QLabel("Contact:")
        email_label_title.setStyleSheet("font-weight: bold;")
        email_label_title.setFixedWidth(label_width)
        email_value_label = QLabel('<a href="mailto:rcverse6@gmail.com">rcverse6@gmail.com</a>')
        email_value_label.setTextFormat(Qt.TextFormat.RichText)
        email_value_label.setOpenExternalLinks(True)
        info_layout.addWidget(email_label_title, 4, 0, Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(email_value_label, 4, 1, Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(info_widget)

        # --- Separator & Acknowledgements (remains mostly the same) ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)
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
            "We are grateful for the developers of these packages that make ANPE and ANPE Studio possible. "
            "Click 'View License' for more details."
        )
        ack_label = QLabel(ack_text)
        ack_label.setWordWrap(True)
        ack_label.setTextFormat(Qt.TextFormat.RichText)
        ack_label.setStyleSheet("font-size: 11px; color: #555;")
        ack_layout.addWidget(ack_label)
        main_layout.addWidget(ack_widget)

        # --- Button Bar (Project Page & License only) ---
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(10, 10, 10, 0)
        button_layout.setSpacing(10)
        project_page_button = QPushButton("Visit Project Page")
        try:
             project_page_button.setStyleSheet("padding-left: 5px; text-align: left;")
             github_icon = ResourceManager.get_icon("github-mark.svg")
             if not github_icon.isNull():
                  project_page_button.setIcon(github_icon)
                  project_page_button.setIconSize(QSize(16, 16))
             else:
                  logging.warning("Could not load github-mark.svg for About page.")
        except Exception as e:
             logging.error(f"Error loading GitHub icon for About page: {e}")
        project_page_button.clicked.connect(self._visit_project_page)
        button_layout.addWidget(project_page_button)
        license_view_button = QPushButton("View License")
        license_view_button.clicked.connect(self._show_license)
        button_layout.addWidget(license_view_button)
        button_layout.addStretch(1)
        main_layout.addWidget(button_widget)
        
        # --- Dedicated GUI Update Status Area ---
        update_status_area_layout = QHBoxLayout()
        update_status_area_layout.setContentsMargins(10, 10, 10, 5) # Added some margins
        update_status_area_layout.setSpacing(8)

        self.gui_update_indicator = PulsingActivityIndicator()
        self.gui_update_indicator.setFixedSize(18, 18) # Standard size
        self.gui_update_indicator.set_color(PRIMARY_COLOR) # Default blue
        self.gui_update_indicator.idle() # Start idle
        update_status_area_layout.addWidget(self.gui_update_indicator)

        self.gui_update_status_label = QLabel("Click icon or text to check for ANPE Studio updates.")
        self.gui_update_status_label.setStyleSheet("font-size: 9pt; color: #555;")
        self.gui_update_status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        update_status_area_layout.addWidget(self.gui_update_status_label, 1) # Stretch factor for label
        main_layout.addLayout(update_status_area_layout) # Add this to main layout
        
        main_layout.addStretch(1) 

    def connect_signals(self):
        if self.update_now_button:
            self.update_now_button.clicked.connect(self._go_to_release_page)
        
        # Make status label and indicator clickable for manual recheck
        if self.gui_update_status_label:
            self.gui_update_status_label.mousePressEvent = lambda event: self.run_gui_update_check(manual_check=True)
        if self.gui_update_indicator:
            self.gui_update_indicator.mousePressEvent = lambda event: self.run_gui_update_check(manual_check=True)
            self.gui_update_indicator.setCursor(Qt.CursorShape.PointingHandCursor) # Make indicator also look clickable

    def showEvent(self, event):
        super().showEvent(event) 
        if self._first_show:
            logging.debug("AboutPage: showEvent - first show, triggering automatic update check.")
            # Initial state for dedicated status area
            if self.gui_update_status_label: self.gui_update_status_label.setText("Checking for updates...")
            if self.gui_update_indicator: self.gui_update_indicator.checking()
            QTimer.singleShot(200, lambda: self.run_gui_update_check(manual_check=False))
            self._first_show = False

    def run_gui_update_check(self, manual_check=True):
        logging.debug(f"AboutPage: run_gui_update_check called. manual_check={manual_check}")

        if self.gui_update_worker_thread and self.gui_update_worker_thread.isRunning():
            logging.warning("AboutPage: GUI update check already in progress.")
            if self.gui_update_status_label: self.gui_update_status_label.setText("Update check already in progress...")
            if self.gui_update_indicator: self.gui_update_indicator.checking()
            return

        # Reset UI elements related to update status
        self.gui_version_value_label.setText(self.gui_version) # Reset version label text
        if self.update_now_button: self.update_now_button.setVisible(False)
        if self.gui_update_status_label: self.gui_update_status_label.setText("Checking for updates...")
        if self.gui_update_indicator: 
            self.gui_update_indicator.set_color(PRIMARY_COLOR) # Ensure blue for checking
            self.gui_update_indicator.checking()
        
        if self.gui_update_worker:
            self.gui_update_worker.deleteLater()
        if self.gui_update_worker_thread:
            self.gui_update_worker_thread.quit()
            self.gui_update_worker_thread.wait()
            self.gui_update_worker_thread.deleteLater()

        self.gui_update_worker = GuiUpdateCheckWorker()
        self.gui_update_worker_thread = QThread(self)
        self.gui_update_worker.moveToThread(self.gui_update_worker_thread)

        self.gui_update_worker.finished.connect(self.on_gui_update_check_finished)
        self.gui_update_worker_thread.started.connect(self.gui_update_worker.run_check)
        self.gui_update_worker.finished.connect(self.gui_update_worker_thread.quit)
        self.gui_update_worker.finished.connect(self.gui_update_worker.deleteLater)
        self.gui_update_worker_thread.finished.connect(self.gui_update_worker_thread.deleteLater)
        self.gui_update_worker.finished.connect(lambda: setattr(self, 'gui_update_worker', None))
        self.gui_update_worker_thread.finished.connect(lambda: setattr(self, 'gui_update_worker_thread', None))

        self.gui_update_worker_thread.start()

    @pyqtSlot(dict, str)
    def on_gui_update_check_finished(self, result: dict, error_string: str):
        logging.debug(f"AboutPage: on_gui_update_check_finished. Result: {result}, Error: '{error_string}'")
        self.gui_version_value_label.setText(self.gui_version)
        if self.update_now_button: self.update_now_button.setVisible(False) 

        if error_string:
            if error_string == "No releases found.":
                if self.gui_update_status_label: self.gui_update_status_label.setText("No releases published on GitHub yet.")
                if self.gui_update_indicator: 
                    self.gui_update_indicator.set_color(PRIMARY_COLOR) # Blue
                    self.gui_update_indicator.idle()
                logging.debug("AboutPage: No releases found.")
                self.latest_gui_version_info = {} 
            else:
                if self.gui_update_status_label: self.gui_update_status_label.setText(f"<span style='color:{ERROR_COLOR};'>Error checking for updates.</span> Click to retry.")
                if self.gui_update_indicator: 
                    self.gui_update_indicator.set_color(ERROR_COLOR) # Red
                    self.gui_update_indicator.warn() # Pulsing red/orange
                logging.error(f"AboutPage: Update check failed: {error_string}")
            return

        if not result or 'tag_name' not in result:
            if self.gui_update_status_label: self.gui_update_status_label.setText("Could not retrieve valid update information. Click to retry.")
            if self.gui_update_indicator: 
                self.gui_update_indicator.set_color(ERROR_COLOR) # Red
                self.gui_update_indicator.warn()
            logging.warning("AboutPage: No valid update information in result.")
            self.latest_gui_version_info = {}
            return

        self.latest_gui_version_info = result 
        latest_version_tag = result.get('tag_name', 'N/A')
        current_version_str = str(self.gui_version).lstrip('v')
        latest_version_str = latest_version_tag.lstrip('v')
        is_update_available = False

        if latest_version_str != 'N/A' and current_version_str != 'N/A':
            try:
                from packaging.version import parse as parse_version
                is_update_available = parse_version(latest_version_str) > parse_version(current_version_str)
            except ImportError:
                is_update_available = latest_version_str > current_version_str
            except Exception as e: 
                logging.error(f"Error comparing versions: {e}")
                if self.gui_update_status_label: self.gui_update_status_label.setText(f"<span style='color:{ERROR_COLOR};'>Version comparison error.</span> Click to retry.")
                if self.gui_update_indicator: 
                    self.gui_update_indicator.set_color(ERROR_COLOR)
                    self.gui_update_indicator.warn()
                return

        if is_update_available:
            release_name = result.get('name', latest_version_tag)
            if self.gui_update_status_label: 
                self.gui_update_status_label.setText(f"<span style='color:{PRIMARY_COLOR};'>Update available: {release_name}.</span> Click icon above to download.")
            if self.gui_update_indicator: 
                self.gui_update_indicator.set_color(PRIMARY_COLOR) # Blue
                self.gui_update_indicator.start() # Pulsing blue (active state)
            self.gui_version_value_label.setText(f"{self.gui_version} <font color='{PRIMARY_COLOR}'>(Update: {release_name} available!)</font>")
            if self.update_now_button: self.update_now_button.setVisible(True)
            logging.info(f"AboutPage: Update available - {release_name}")
        else:
            if self.gui_update_status_label: self.gui_update_status_label.setText("ANPE Studio is up to date.")
            if self.gui_update_indicator: 
                self.gui_update_indicator.set_color(PRIMARY_COLOR) # Blue
                self.gui_update_indicator.idle()
            logging.info(f"AboutPage: ANPE Studio is up to date.")
            
    # ... (_go_to_release_page, is_worker_running, _show_license, _visit_project_page) ...

    def _go_to_release_page(self):
        """Opens the GitHub release page for the latest update."""
        if self.latest_gui_version_info and isinstance(self.latest_gui_version_info, dict):
            release_url = self.latest_gui_version_info.get('html_url')
            if release_url:
                release_name = self.latest_gui_version_info.get('name', self.latest_gui_version_info.get('tag_name', 'N/A'))
                reply = QMessageBox.information(
                    self.window(),
                    "Go to Download Page",
                    f"You are about to visit the download page for ANPE Studio <b>{release_name}</b>.<br><br>"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl(release_url))
            else:
                logging.warning("AboutPage: _go_to_release_page called but no html_url in latest_gui_version_info.")
                QMessageBox.warning(self.window(), "Error", "Could not find the download page URL.")
        else:
            logging.warning("AboutPage: _go_to_release_page called but no update info available.")
            # This case should ideally not happen if the button is only visible when info is present.
            # Might re-trigger a check or show an error.
            self.run_gui_update_check(manual_check=True) # Re-check if button was clicked inappropriately

    def is_worker_running(self) -> bool:
        """Check if the GUI update worker thread is active."""
        # Check if thread object exists and then if it's running
        return bool(self.gui_update_worker_thread and self.gui_update_worker_thread.isRunning())

    def _show_license(self):
        """Show the license dialog."""
        # Need LicenseDialog - assume it's importable or handle error
        try:
            from anpe_studio.widgets.license_dialog import LicenseDialog
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
        QDesktopServices.openUrl(QUrl("https://github.com/rcverse/anpe-studio"))


# --- Main Dialog Class ---

class SettingsDialog(QDialog):
    """Dialog window for managing ANPE settings."""

    # Signal emitted when an action might require the main window to re-check things
    models_changed = pyqtSignal() 
    # Signal emitted if model usage preference changes
    model_usage_changed = pyqtSignal() 
    restart_application_requested = pyqtSignal() # ADDED FOR RESTART FUNCTIONALITY

    def __init__(self, parent=None, model_status=None):
        super().__init__(parent)
        logging.debug(f"SettingsDialog.__init__: Received model_status = {model_status}") # LOGGING
        self.model_status = model_status # Store the passed status
        self.setWindowTitle("ANPE Settings")
        # Set minimum size, but let initial size be determined by layout
        self.setMinimumSize(700, 600) 
        # self.resize(800, 700) # REMOVED - Let layout determine initial size
        # self.initial_size = None # REMOVED

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

        # Install event filter to capture Alt key presses/releases globally within the dialog
        self.installEventFilter(self)

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
        
        # --- Use QHBoxLayout instead of QSplitter --- 
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0) # No space between nav and pages
        content_layout.setContentsMargins(0,0,0,0)

        # Left Pane: Navigation List
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0) # No margins for the container
        nav_layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180) # Adjust width as needed
        self.nav_list.setIconSize(QSize(16, 16)) # <<< SET ICON SIZE
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
        content_layout.addWidget(nav_widget) # Add nav to layout

        # Right Pane: Stacked Pages
        self.pages_stack = QStackedWidget()
        self.pages_stack.setStyleSheet("QStackedWidget > QWidget { background-color: white; }") # Ensure pages have white background

        # Create and add pages (Pass initial status to ModelsPage)
        self.models_page = ModelsPage(self, model_status=self.model_status) # Use self.model_status
        self.core_page = CorePage(self)
        # Pass version info to AboutPage
        try:
            from anpe_studio.version import __version__ as gui_version
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

        content_layout.addWidget(self.pages_stack, 1) # Add pages to layout, give stretch factor 1

        # Navigation width is fixed by self.nav_list.setFixedWidth(180) above
        # Stretch factor for pages_stack handles expansion in QHBoxLayout

        main_layout.addLayout(content_layout) # Add the new layout to the main layout

    def connect_signals(self):
        """Connect signals for navigation and page updates."""
        self.nav_list.currentRowChanged.connect(self.pages_stack.setCurrentIndex)

        # Connect signals from ModelsPage to SettingsDialog signals
        self.models_page.models_changed.connect(self.models_changed.emit)
        self.models_page.model_usage_changed.connect(self.model_usage_changed.emit)

    # --- Event Filter Implementation --- 
    def eventFilter(self, source, event):
        """Filters events globally within the dialog, specifically for Alt key changes."""
        update_needed = False
        alt_state_hint = None
        
        # Check if the event is a key press or release
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Alt:
                update_needed = True
                alt_state_hint = True # Alt is now pressed
        elif event.type() == QEvent.Type.KeyRelease:
            # Check if the key is Alt and not an auto-repeat release
            if event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat(): 
                update_needed = True
                alt_state_hint = False # Alt is now released

        # If an update is needed and the correct page is visible, call the update function
        if update_needed:
            if self.models_page and self.pages_stack.currentWidget() == self.models_page:
                # Pass the determined state hint
                self.models_page._update_dynamic_button_state(alt_pressed_hint=alt_state_hint)
                # Don't consume the event

        # Call the base class implementation for standard event processing
        return super().eventFilter(source, event)

    def closeEvent(self, event):
        """Prevent closing the dialog if a background task is running."""
        model_worker_active = False
        core_worker_active = False
        about_page_worker_active = False

        if self.models_page and hasattr(self.models_page, 'is_worker_running') and callable(self.models_page.is_worker_running):
            try:
                model_worker_active = self.models_page.is_worker_running()
            except Exception as e:
                logging.error(f"Error checking ModelsPage worker status: {e}")
                model_worker_active = False

        if self.core_page and hasattr(self.core_page, 'is_worker_running') and callable(self.core_page.is_worker_running):
            try:
                core_worker_active = self.core_page.is_worker_running()
            except Exception as e:
                logging.error(f"Error checking CorePage worker status: {e}")
                core_worker_active = False
        
        if self.about_page and hasattr(self.about_page, 'is_worker_running') and callable(self.about_page.is_worker_running):
            try:
                about_page_worker_active = self.about_page.is_worker_running()
            except Exception as e:
                # Log the error but don't assume worker is active, to prevent blocking close indefinitely
                logging.error(f"Error checking AboutPage worker status in closeEvent: {e}")
                about_page_worker_active = False # Default to false on error here

        if model_worker_active or core_worker_active or about_page_worker_active:
            logging.warning("Attempted to close SettingsDialog while worker thread is running.")
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "A background operation (model install/update/clean or GUI update check) is currently running.\n"
                "Please wait for it to complete before closing this window.",
                QMessageBox.StandardButton.Ok
            )
            event.ignore()  # Prevent the window from closing
        else:
            logging.debug("SettingsDialog close event accepted.")
            # Optional: Add any other cleanup needed before closing?
            event.accept()  # Allow the window to close