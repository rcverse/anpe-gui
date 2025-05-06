"""
Welcome view for macOS setup

This module provides the welcome screen for the macOS setup wizard,
with styling and functionality optimized for macOS.
"""

import sys
import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QHBoxLayout,
    QSizePolicy, QSpacerItem, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QMouseEvent, QFont

from .license_dialog import LicenseDialog
from ..installer_core_macos import _get_bundled_resource_path_macos

# Get logger instance
logger = logging.getLogger()

# Subclass QLabel to make it clickable for the license link
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Tooltip removed, text is now more descriptive
        # self.setToolTip("Click to view license details")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        else:
            super().mousePressEvent(event)

class WelcomeViewWidget(QWidget):
    """Widget for the welcome screen of the setup wizard (macOS version)."""
    # Signal arguments: install_path (str)
    setup_requested = pyqtSignal(str)
    # Add signal for cancellation
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the welcome view."""
        super().__init__(parent)
        self._license_dialog = None
        
        # Store notes text for reuse in the popup
        self._storage_text = (
            "<b>Storage (~1.8 GB):</b> ANPE uses powerful NLP libraries like spaCy and Benepar. "
            "These require large pre-trained models (data files) and depend on frameworks like PyTorch, "
            "which are also substantial in size, leading to the large total footprint."
        )
        self._env_text = (
            "<b>Environment:</b> This installer creates a dedicated, isolated Python environment for ANPE. "
            "This prevents conflicts with other Python installations you might have. "
            "Advanced users comfortable with Python can alternatively clone the "
            "<a href='https://github.com/rcverse/anpe-gui'>GitHub repository</a> and run "
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30) # Adjusted margins
        main_layout.setSpacing(10) # Reduced spacing

        # --- Logo ---
        logo_layout = QHBoxLayout()
        logo_layout.addStretch(1)
        logo_label = QLabel()
        try:
            # Use the corrected resource finder
            logo_path_obj = _get_bundled_resource_path_macos('assets/app_icon_logo.png')
            logo_path = str(logo_path_obj) if logo_path_obj else None
            if logo_path and os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    logo_label.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)) # Slightly smaller
                else: logo_label.setText("[Logo]") # Simple fallback
            else: logo_label.setText("[Logo]")
        except Exception as e:
            logger.error(f"Error loading logo: {e}", exc_info=True)
            logo_label.setText("[Logo]")
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch(1)
        main_layout.addLayout(logo_layout)
        main_layout.addSpacing(5) # Less space after logo

        # --- Welcome Title ---
        title_label = QLabel("Welcome to ANPE GUI Setup")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #1a1a1a; font-family: 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif;")
        main_layout.addWidget(title_label)
        main_layout.addSpacing(15) # Space after title

        # --- ANPE Introduction Text ---
        intro_text = QLabel(
            "ANPE GUI provides a user-friendly interface for extracting noun phrases from text "
            "using the <a href='https://github.com/rcverse/another-noun-phrase-extractor'>ANPE library</a>, "
            "without needing to write any code."
        )
        intro_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro_text.setWordWrap(True)
        intro_text.setOpenExternalLinks(True)
        intro_text.setStyleSheet("font-size: 14px; color: #3c3c3c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; line-height: 140%;")
        main_layout.addWidget(intro_text)
        main_layout.addSpacing(20) # Space before explanation

        # --- Setup Explanation Box --- (Removed separator, integrated info)
        explanation_box = QFrame()
        explanation_box.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0; /* Lighter gray */
                border-radius: 10px; /* More rounded */
                border: none; /* No border */
            }
        """)
        explanation_layout = QVBoxLayout(explanation_box)
        explanation_layout.setContentsMargins(20, 20, 20, 20) # More padding inside box
        explanation_layout.setSpacing(12)

        explanation_header = QLabel("Preparing for First Use")
        explanation_header.setStyleSheet("font-size: 16px; font-weight: 500; color: #1c1c1c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;")
        explanation_layout.addWidget(explanation_header)

        # Use HTML list for better structure and wrapping
        explanation_body = QLabel(
            "To run ANPE GUI, we need to set up a few things first:"
            "<ul>"
            "<li>A dedicated <b>Python environment</b> will be created.</li>"
            "<li>Required <b>language models</b> and dependencies (~1.8 GB) will be downloaded.</li>"
            "</ul>"
            "<p>This process requires an active internet connection and may take <b>several minutes</b> depending on your speed. "
            "Components will be installed in <code>~/Library/Application Support/ANPE GUI/</code>.</p>"
        )
        explanation_body.setWordWrap(True)
        explanation_body.setStyleSheet("font-size: 13px; color: #4c4c4c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; line-height: 150%;")
        # Ensure Rich Text is enabled
        explanation_body.setTextFormat(Qt.TextFormat.RichText)
        explanation_layout.addWidget(explanation_body)

        # Add the styled box to the main layout
        main_layout.addWidget(explanation_box)

        # --- License Agreement ---
        license_link_layout = QHBoxLayout()
        license_link_layout.addStretch(1)
        license_link = ClickableLabel("By continuing, you agree to the <a href='#'>software license agreement</a>.")
        license_link.setStyleSheet("font-size: 12px; color: #6c6c6c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;")
        license_link.clicked.connect(self._show_license_dialog)
        license_link_layout.addWidget(license_link)
        license_link_layout.addStretch(1)
        main_layout.addLayout(license_link_layout)

        # Add flexible space before buttons
        main_layout.addStretch(1)

        # --- Footer with buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch(1) # Push buttons to the right

        # macOS-style buttons (styles updated slightly)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e9e9e9;
                color: #3c3c3c;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #dcdcdc; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """)
        self.cancel_button.clicked.connect(self._emit_cancel_request)
        button_layout.addWidget(self.cancel_button)

        # Continue button (primary)
        self.continue_button = QPushButton("Continue")
        self.continue_button.setDefault(True)
        self.continue_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF; /* Apple Blue */
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #0070E0; }
            QPushButton:pressed { background-color: #0062C7; }
            QPushButton:disabled {
                background-color: #a0a0a0;
                color: #e0e0e0;
            }
        """)
        self.continue_button.clicked.connect(self._on_setup_clicked)
        button_layout.addWidget(self.continue_button)

        main_layout.addLayout(button_layout)

    def _show_license_dialog(self):
        """Show the license dialog."""
        if not self._license_dialog:
            self._license_dialog = LicenseDialog(self)
        self._license_dialog.exec()
    
    def _on_setup_clicked(self):
        """Handle the setup button click."""
        self.setup_requested.emit("") # Path determined later
    
    def set_welcome_text(self, title_text, info_text):
        """Set the welcome text (compatibility). May not map perfectly to new layout."""
        try:
            self.findChild(QLabel, "title_label").setText(title_text) # Assumes objectName is set
            # Find a suitable label for info_text - might need adjustment
            # This is brittle; direct access is better if adapter pattern is removed.
            self.findChildren(QLabel)[2].setText(info_text) # Example: Third label
        except AttributeError:
             logger.warning("Could not set welcome text via compatibility method.")
    
    def get_start_button(self):
        """Get the start button (compatibility)."""
        return self.continue_button 

    def _emit_cancel_request(self):
        """Emit the cancel_requested signal."""
        self.cancel_requested.emit() 