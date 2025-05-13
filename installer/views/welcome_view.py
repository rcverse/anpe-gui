import sys
import os
import ctypes
import logging # Added for debugging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QHBoxLayout,
    QSizePolicy, QFileDialog, QSpacerItem, QRadioButton, QButtonGroup, QFrame,
    QMessageBox, QToolTip # Added QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QMouseEvent

# Import the helper function and the dialog
from .license_dialog import LicenseDialog # Relative import for view
# Use relative import for utils
from ..utils import get_resource_path
from ..styles import PRIMARY_BUTTON_STYLE, BROWSE_BUTTON_STYLE, TITLE_LABEL_STYLE, INFO_LABEL_STYLE, LINK_LABEL_STYLE

# Get logger instance (configured in utils.py)
logger = logging.getLogger()

# Subclass QLabel to make it clickable for the license link
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to view license details")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        else:
            super().mousePressEvent(event)

class WelcomeViewWidget(QWidget):
    """Widget for the welcome screen of the setup wizard (Windows version)."""
    # Signal arguments: install_path (str)
    setup_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize the welcome view."""
        super().__init__(parent)
        self._license_dialog = None # Hold reference to dialog
        # Store notes text for reuse in the popup
        self._storage_text = (
            "<b>Storage (~1.8 GB):</b> ANPE Studio uses powerful NLP libraries like spaCy and Benepar. "
            "These require large pre-trained models (data files) and depend on frameworks like PyTorch, "
            "which are also substantial in size, leading to the large total footprint."
        )
        self._env_text = (
            "<b>Environment:</b> This installer creates a dedicated, isolated Python environment for ANPE. "
            "This prevents conflicts with other Python installations you might have. "
            "Advanced users comfortable with Python can alternatively clone the "
            "<a href='https://github.com/rcverse/anpe-studio'>GitHub repository</a> and run "
            "<code>pip install -r requirements.txt</code> in their own environment, potentially saving disk space."
        )
        self._internet_text = (
            "<b>Installation:</b> An active internet connection is needed during setup to download "
            "these large libraries and models. The download and setup process may take several minutes "
            "depending on your connection speed."
        )
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20) # Add some padding
        layout.setSpacing(15)

        # --- Logo ---
        logo_label = QLabel()
        # Use the imported get_resource_path directly
        try:
            logo_path = get_resource_path('assets/app_icon_logo.png')
            logger.debug(f"Checking for logo at path: {logo_path}") # Log the path being checked
            if os.path.exists(logo_path):
                logger.debug(f"Logo path exists.")
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    logger.debug(f"Logo pixmap loaded successfully.")
                    logo_label.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    logger.warning(f"Failed to load logo pixmap from {logo_path}. pixmap.isNull() is True.")
                    logo_label.setText("[Logo Load Error]")
                    logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    print(f"Warning: Failed to load logo pixmap from {logo_path}", file=sys.stderr)
            else:
                logger.warning(f"Logo file not found at resolved path: {logo_path}")
                logo_label.setText("[Logo Not Found]")
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                print(f"Warning: Logo file not found at {logo_path}", file=sys.stderr)
        except Exception as e:
             logger.error(f"Error loading logo: {e}", exc_info=True) # Log exception details
             logo_label.setText("[Logo Error]")
             logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             print(f"Error resolving logo path: {e}", file=sys.stderr)

        logo_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(logo_label)

        # --- Welcome Text ---
        title_label = QLabel("Welcome to ANPE Studio Setup")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #0078D7; font-family: 'Segoe UI', Arial, sans-serif;")
        layout.addWidget(title_label)
        
        # Add spacing instead of separator
        layout.addSpacing(15)

        # --- Installation Path (Windows Specific) ---
        path_label = QLabel("Install ANPE Studio to:")
        path_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #444444; font-family: 'Segoe UI', Arial, sans-serif;")
        layout.addWidget(path_label)

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                selection-background-color: #0078D7;
            }
            QLineEdit:focus {
                border: 1px solid #0078D7;
            }
        """)
        
        # Automatically determine appropriate installation path based on admin privileges
        is_admin = self._is_admin()
        if is_admin:
            default_path = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), "ANPE")
        else:
            default_path = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser("~\\AppData\\Local")), "ANPE")
        
        self.path_edit.setText(default_path)
        self.path_edit.textChanged.connect(self._validate_inputs) # Validate on change
        path_layout.addWidget(self.path_edit)

        browse_button = QPushButton("Browse...")
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_button.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 8px 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #E5E5E5;
                border: 1px solid #BBBBBB;
            }
            QPushButton:pressed {
                background-color: #D0D0D0;
            }
        """)
        browse_button.clicked.connect(self._browse_directory)
        path_layout.addWidget(browse_button)
        layout.addLayout(path_layout)
        
        # --- Path Info Line (with Help Icon) ---
        path_info_layout = QHBoxLayout() # Layout for the info text + help icon
        path_info_layout.setSpacing(5)

        # Modified explanation about installation location
        path_info_label = QLabel("Requires ~1.8GB disk space and an internet connection during setup.")
        path_info_label.setStyleSheet("font-size: 13px; color: #555555; font-family: 'Segoe UI', Arial, sans-serif;")
        path_info_layout.addWidget(path_info_label)

        # Replace emoji with styled QPushButton
        help_button = QPushButton("?")
        help_button.setFixedSize(20, 20)  # Smaller size
        help_button.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;  /* Medium gray */
                border-radius: 10px;
                border: none;
                color: white;
                font-weight: bold;
                font-size: 11px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #ABABAB;  /* Lighter gray on hover */
            }
            QPushButton:pressed {
                background-color: #808080;  /* Darker gray when pressed */
            }
        """)
        
        # Create rich tooltip with all the installation information
        tooltip_text = (
            "<div style='width: 300px; font-family: Segoe UI;'>"
            "<p>Storage: Requires ~1.8GB disk space for NLP libraries (spaCy, Benepar) "
            "and their dependencies like PyTorch needed for neural network processing.</p>"
            "<p>Internet: Active connection needed during setup to download ~1.5GB of dependencies. "
            "Installation time varies with connection speed.</p>"
            "</div>"
        )
        
        help_button.setToolTip(tooltip_text)
        help_button.setCursor(Qt.CursorShape.PointingHandCursor)
        help_button.clicked.connect(self._show_tooltip)  # Connect click to show tooltip
        path_info_layout.addWidget(help_button)

        path_info_layout.addStretch() # Push icon to the right if needed, or keep compact
        layout.addLayout(path_info_layout) # Add this layout below the path input
        
        # --- Environment Information Section --- (simplified styling)
        layout.addSpacing(8)
        
        env_info_layout = QVBoxLayout()
        env_info_layout.setContentsMargins(0, 0, 0, 0)
        env_info_layout.setSpacing(6)
        
        env_info_label = QLabel("Setup notes:")
        env_info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #444444; font-family: 'Segoe UI', Arial, sans-serif;")
        env_info_layout.addWidget(env_info_label)
        
        env_details = QLabel(
            "• This installer will create a self-contained Python environment and will not interfere with existing Python installations.<br>"
            "• For those who know Python: You can clone the <a href='https://github.com/rcverse/anpe-studio'>GitHub repository</a> and use it with your own Python installation"
        )
        env_details.setStyleSheet("font-size: 13px; color: #555555; font-family: 'Segoe UI', Arial, sans-serif; line-height: 140%;")
        env_details.setWordWrap(True)
        env_details.setOpenExternalLinks(True)  # This makes the links clickable and open in browser
        env_details.setTextFormat(Qt.TextFormat.RichText)  # Enable rich text with HTML
        env_info_layout.addWidget(env_details)
        
        layout.addLayout(env_info_layout)
        layout.addSpacing(5)

        # --- License Agreement ---
        license_layout = QHBoxLayout()
        license_layout.addStretch(1)  # Add stretch at the beginning to center
        
        # Create a single QLabel with rich text and link
        self.license_label = QLabel(
            "By continuing, you agree to the <a href='show_license'>software license agreement</a>."
        )
        self.license_label.setTextFormat(Qt.TextFormat.RichText)
        self.license_label.setOpenExternalLinks(False) # Important: Don't open external links
        self.license_label.linkActivated.connect(self._handle_license_link) # Connect signal
        self.license_label.setStyleSheet("font-size: 13px; color: #555555; font-family: 'Segoe UI', Arial, sans-serif;") # Basic style
        
        # Optionally style the link part (Qt's default link color is often blue)
        # You might need more complex styling if you want specific link colors
        
        license_layout.addWidget(self.license_label)
        license_layout.addStretch(1)  # Add stretch at the end to center
        
        layout.addLayout(license_layout)

        layout.addSpacerItem(QSpacerItem(20, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- Setup Button ---
        self.setup_button = QPushButton("Setup")
        self.setup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_button.setObjectName("SetupButton")  # For potential styling
        self.setup_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1A88E1;
            }
            QPushButton:pressed {
                background-color: #006CC1;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #888888;
            }
        """)
        self.setup_button.clicked.connect(self._on_setup_clicked)
        layout.addWidget(self.setup_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)

        # --- Debugging: Log MEIPASS structure if frozen ---
        self._log_meipass_structure()
        # --- End Debugging ---

    # --- Debugging Function ---
    def _log_meipass_structure(self):
        """Logs the MEIPASS directory structure if running frozen."""
        if hasattr(sys, '_MEIPASS'):
            meipass_path = sys._MEIPASS
            logger.info(f"--- MEIPASS Directory Structure ({meipass_path}) ---")
            try:
                for root, dirs, files in os.walk(meipass_path):
                    level = root.replace(meipass_path, '').count(os.sep)
                    indent = ' ' * 4 * (level)
                    logger.info(f'{indent}{os.path.basename(root)}/')
                    subindent = ' ' * 4 * (level + 1)
                    for f in files:
                        logger.info(f'{subindent}{f}')
                logger.info("--- End MEIPASS Structure ---")
            except Exception as e:
                logger.error(f"Error walking MEIPASS directory: {e}")
        else:
            logger.info("Not running frozen, skipping MEIPASS structure log.")
    # --- End Debugging Function ---

    def _browse_directory(self):
        """Open a directory selection dialog."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Installation Directory",
            self.path_edit.text() # Start browsing from current path
        )
        if directory: # If user selected a directory (didn't cancel)
            self.path_edit.setText(directory)
            self._validate_inputs() # Re-validate after path change

    def _validate_inputs(self):
        """Enable the setup button only if path is non-empty and valid."""
        install_path = self.path_edit.text().strip()
        
        # Basic validation - path must not be empty
        path_valid = bool(install_path)
        
        # Check if parent directory exists or can be created
        if path_valid:
            try:
                parent_dir = os.path.dirname(os.path.abspath(install_path))
                
                # Check if parent directory exists
                if not os.path.exists(parent_dir):
                    try:
                        # Try temporarily creating it to check permissions
                        os.makedirs(parent_dir, exist_ok=True)
                        os.rmdir(parent_dir)  # Clean up if we created it just for testing
                    except (PermissionError, OSError):
                        path_valid = False
                
                # If target exists, check if it's writable
                if os.path.exists(install_path):
                    if not os.access(install_path, os.W_OK):
                        path_valid = False
                else:
                    # Check if we can write to the parent directory
                    if not os.access(parent_dir, os.W_OK):
                        path_valid = False
            except Exception:
                path_valid = False
                
        self.setup_button.setEnabled(path_valid)

    def _on_setup_clicked(self):
        """Emit the setup_requested signal when the setup button is clicked."""
        install_path = self.path_edit.text().strip()
        
        # Final validation before emitting the signal
        try:
            # Convert to absolute path
            abs_path = os.path.abspath(install_path)
            parent_dir = os.path.dirname(abs_path)
            
            # Ensure parent directory exists or can be created
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                
            # Check write permissions by attempting to create a test file
            if os.path.exists(abs_path):
                test_dir = abs_path
            else:
                test_dir = parent_dir
                
            test_file = os.path.join(test_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
            # If we got here, the path is valid and writable
            print(f"Setup requested: Path='{abs_path}'")
            self.setup_requested.emit(abs_path)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Invalid Installation Path",
                f"Cannot install to the selected location:\n{install_path}\n\nError: {str(e)}"
            )

    def _show_license_dialog(self):
        """Show the license agreement dialog."""
        # Create dialog if it doesn't exist or reuse if already created (optional)
        if self._license_dialog is None:
            self._license_dialog = LicenseDialog(self) # Pass self as parent
        self._license_dialog.exec()

    def _handle_license_link(self, link):
        """Handle clicks on the license link."""
        # Check if the link clicked is the one we defined
        if link == 'show_license':
            self._show_license_dialog()

    def _is_admin(self):
        """Check if the current user has administrator privileges on Windows."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    # --- Add method to show tooltip when button is clicked ---
    def _show_tooltip(self):
        """Show the tooltip when the help button is clicked."""
        # Get the sender (the help button)
        button = self.sender()
        # Show tooltip at the position just below the button
        tooltip_pos = button.mapToGlobal(button.rect().bottomLeft())
        # Get tooltip text from the button
        tooltip_text = button.toolTip()
        # Display the tooltip
        QToolTip.showText(tooltip_pos, tooltip_text, button)

