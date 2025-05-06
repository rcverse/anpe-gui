import os
import sys
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel, QSizePolicy,
    QHBoxLayout, QScrollArea, QWidget, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap, QFont

# Use relative import for utils
from ..installer_core_macos import _get_bundled_resource_path_macos
# Get logger instance
logger = logging.getLogger(__name__)

# Assume styles might be defined elsewhere or define basic ones here
# from ..styles import PRIMARY_BUTTON_STYLE, LINK_LABEL_STYLE, INFO_LABEL_STYLE

# Basic Style Constants (adjust colors/fonts as needed)
PRIMARY_COLOR = "#005A9C" # Example primary color
BORDER_COLOR = "#D0D0D0"
BACKGROUND_COLOR = "#FFFFFF"
TEXT_COLOR = "#333333"
SECONDARY_TEXT_COLOR = "#666666"
LINK_COLOR = PRIMARY_COLOR

# Define button style template with a placeholder
_BUTTON_STYLE_TEMPLATE = """
QPushButton {
    background-color: __PRIMARY_COLOR_PLACEHOLDER__;
    color: white;
    border: none;
    padding: 8px 16px;
    font-size: 14px;
    border-radius: 4px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #00447a; /* Darker shade on hover */
}
QPushButton:pressed {
    background-color: #003158; /* Even darker when pressed */
}
"""
# Replace the placeholder with the actual color
BUTTON_STYLE = _BUTTON_STYLE_TEMPLATE.replace("__PRIMARY_COLOR_PLACEHOLDER__", PRIMARY_COLOR)

LINK_STYLE = f"color: {LINK_COLOR}; text-decoration: none;"
INFO_STYLE = f"color: {SECONDARY_TEXT_COLOR}; font-size: 13px;"

# Subclass QLabel for clickable links with proper cursor
class ClickableLink(QLabel):
    def __init__(self, text, url=None, callback=None, parent=None):
        super().__init__(text, parent)
        self.url = url
        self.callback = callback
        self.setStyleSheet(LINK_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Open link" if url else "Show details")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.url:
                QDesktopServices.openUrl(QUrl(self.url))
            elif self.callback:
                self.callback()
        else:
            super().mousePressEvent(event)

class LicenseDialog(QDialog):
    """A dialog to display the application license with improved styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ANPE License Information")
        self._full_license_dialog = None # To avoid recreating
        self._setup_ui()
        # self.resize(650, 550) # REMOVED: Allow auto-sizing
        # Set minimum width, height will adjust
        self.setMinimumWidth(650)
        self.setStyleSheet(f"QDialog {{ background-color: {BACKGROUND_COLOR}; }}")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # --- Header ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        # Logo
        logo_label = QLabel()
        try:
            # Use the correct resource finder and only the filename
            logo_path_obj = _get_bundled_resource_path_macos('app_icon_logo.png') # MODIFIED
            if logo_path_obj and logo_path_obj.is_file(): # Check if path is valid file
                pixmap = QPixmap(str(logo_path_obj))
                logo_label.setPixmap(pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                # Fallback if logo not found
                logo_label.setText("?")
                logo_label.setFixedSize(50, 50)
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                logo_label.setStyleSheet(f"background-color: #f0f0f0; border-radius: 25px; font-size: 24px; color: {SECONDARY_TEXT_COLOR};")
                logger.warning(f"Logo 'app_icon_logo.png' not found using resource finder.") # Use logger
        except Exception as e:
             logo_label.setText("Err")
             logo_label.setFixedSize(50, 50)
             logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             logo_label.setStyleSheet(f"background-color: #fee; border-radius: 25px; font-size: 18px; color: red;")
             logger.error(f"Error loading logo: {e}", exc_info=True) # Use logger

        header_layout.addWidget(logo_label)

        # Title and Subtitle
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_label = QLabel("ANPE License Information")
        title_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_COLOR};")
        title_vbox.addWidget(title_label)

        subtitle_label = QLabel("Open Source Software under GNU GPL v3")
        subtitle_label.setStyleSheet(INFO_STYLE)
        title_vbox.addWidget(subtitle_label)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # --- Separator ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"border-color: {BORDER_COLOR};")
        main_layout.addWidget(separator)

        # --- Description (Added directly to main_layout) ---
        description = QLabel(
            "ANPE is free software built upon the principles of open collaboration. It is licensed "
            "under the <b>GNU General Public License version 3 (GPLv3)</b> "
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px; line-height: 1.4;")
        main_layout.addWidget(description) # Add to main layout

        # --- License Summary Section (Using Labels) ---
        summary_section_layout = QVBoxLayout() # Layout for this section
        summary_section_layout.setSpacing(8) # Smaller spacing within this section

        summary_title = QLabel("Key License Points:")
        summary_title.setStyleSheet(f"font-weight: bold; color: {TEXT_COLOR}; font-size: 15px; margin-top: 15px; margin-bottom: 5px;")
        summary_section_layout.addWidget(summary_title)

        # Freedoms
        freedoms_title = QLabel("<b> Your Freedoms with ANPE (GPLv3):</b>")
        freedoms_title.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
        summary_section_layout.addWidget(freedoms_title)

        freedoms_list = [
            "<b>Use:</b> Run the software for any purpose.",
            "<b>Study:</b> Examine the source code and change it.",
            "<b>Share:</b> Redistribute exact copies.",
            "<b>Modify & Share:</b> Distribute your modified versions. If you distribute modified versions, they must also be licensed under the GPLv3"
        ]
        for item in freedoms_list:
            label = QLabel(f"<ul style='margin-left: 0; padding-left: 20px;'><li style='margin-bottom: 3px;'>{item}</li></ul>")
            label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px;")
            summary_section_layout.addWidget(label)

        # Dependencies
        deps_title = QLabel("<b> Core Dependencies & Licenses:</b>")
        deps_title.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
        summary_section_layout.addWidget(deps_title)

        deps_list = [
            "<b>PyQt6:</b> <code>GPL v3</code> / Commercial",
            "<b>spaCy:</b> <code>MIT License</code>",
            "<b>Benepar:</b> <code>Apache License 2.0</code>",
            "<b>NLTK:</b> <code>Apache License 2.0</code>",
            "<i>(And others - see project documentation)</i>"
        ]
        deps_style = """
            QLabel {
                color: __TEXT_COLOR__;
                font-size: 13px;
            }
            code {
                 background-color: #e8eaf6;
                 padding: 1px 3px;
                 border-radius: 3px;
                 font-family: monospace;
            }
        """.replace("__TEXT_COLOR__", TEXT_COLOR)

        for item in deps_list:
            label = QLabel(f"<ul style='margin-left: 0; padding-left: 20px;'><li style='margin-bottom: 3px;'>{item}</li></ul>")
            label.setStyleSheet(deps_style)
            summary_section_layout.addWidget(label)

        # Add the whole summary section layout to the main layout
        main_layout.addLayout(summary_section_layout)

        # Add vertical stretch to push buttons to bottom
        main_layout.addStretch(1)

        # --- Separator before buttons ---
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        separator2.setStyleSheet(f"border-color: {BORDER_COLOR};")
        main_layout.addWidget(separator2)

        # --- Buttons --- 
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push buttons to the right

        # View Full License Button (New)
        view_license_button = QPushButton("View Full License")
        # Use a slightly different style for secondary button?
        # For now, use the same style as OK
        view_license_button.setStyleSheet(BUTTON_STYLE) 
        view_license_button.clicked.connect(self._show_full_license)
        button_layout.addWidget(view_license_button)

        # OK Button
        ok_button = QPushButton("OK")
        ok_button.setStyleSheet(BUTTON_STYLE)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        main_layout.addLayout(button_layout)

    def _show_full_license(self):
        """Show the full license text in a separate styled dialog."""
        if self._full_license_dialog is None:
            self._full_license_dialog = QDialog(self)
            self._full_license_dialog.setWindowTitle("GNU General Public License v3")
            self._full_license_dialog.resize(750, 600)
            self._full_license_dialog.setStyleSheet(f"QDialog {{ background-color: {BACKGROUND_COLOR}; }}")

            layout = QVBoxLayout(self._full_license_dialog)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(15)

            license_title = QLabel("GNU General Public License v3 (Full Text)")
            license_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {TEXT_COLOR};")
            layout.addWidget(license_title)

            license_text_edit = QTextEdit()
            license_text_edit.setReadOnly(True)
            license_text_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #fdfdfd;
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 4px;
                    padding: 10px;
                    color: {TEXT_COLOR};
                    font-family: monospace; /* Use monospace for license text */
                    font-size: 12px;
                    line-height: 1.4;
                }}
            """)

            license_text = "Error: Could not load license text."
            try:
                # Use the correct resource finder and only the filename
                license_path_obj = _get_bundled_resource_path_macos('LICENSE.installer.txt') # MODIFIED
                if license_path_obj and license_path_obj.is_file():
                    try:
                        with open(license_path_obj, 'r', encoding='utf-8') as f:
                            license_text = f.read()
                    except Exception as e:
                        license_text = f"Error reading license file: {e}"
                        logger.error(f"Error reading license file {license_path_obj}: {e}", exc_info=True)
                else:
                    license_text = f"License file not found using resource finder for 'LICENSE.installer.txt'"
                    logger.warning(license_text)
            except Exception as e:
                logger.error(f"Error resolving license path for 'LICENSE.installer.txt': {e}", exc_info=True)

            license_text_edit.setText(license_text)
            layout.addWidget(license_text_edit)

            # Add close button
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            close_button = QPushButton("Close")
            close_button.setStyleSheet(BUTTON_STYLE)
            close_button.clicked.connect(self._full_license_dialog.accept) # Use accept for dialogs
            button_layout.addWidget(close_button)
            layout.addLayout(button_layout)

        # Ensure the dialog is raised and activated
        self._full_license_dialog.show()
        self._full_license_dialog.raise_()
        self._full_license_dialog.activateWindow()
