"""
Completion view for macOS setup

This module provides the completion screen for the macOS setup wizard,
with styling and functionality optimized for macOS.
"""

import os
import re
import datetime
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QSizePolicy, QSpacerItem,
    QHBoxLayout, QFrame, QTextEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor, QTextCursor

# CORRECTED IMPORT: Use macOS specific resource finder
from ..installer_core_macos import _get_bundled_resource_path_macos

# Get logger instance
logger = logging.getLogger()

# Import ClickableLabel from WelcomeView (or define it here if preferred)
# Assuming it's available via relative import is slightly fragile
# For simplicity, let's assume we can import it or redefine if needed.
from .welcome_view_macos import ClickableLabel

class CompletionViewWidget(QWidget):
    """Widget for the completion screen of the setup wizard (macOS version)."""
    # Renamed signal
    launch_requested = pyqtSignal(bool) # Emit success status

    def __init__(self, parent=None):
        """Initialize the completion view."""
        super().__init__(parent)
        self._setup_ui()
        self._log_content = ""  # Store log content for export
        self._error_message = ""  # Store extracted error message
        self._success = False # Store success state

    def _setup_ui(self):
        """Set up the user interface elements."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30) # Adjusted margins
        main_layout.setSpacing(10) # Reduced spacing

        # --- Header --- (Centering Logo and Title Block - consistent style)
        header_centering_layout = QHBoxLayout()
        header_centering_layout.addStretch(1) # Left stretch
        header_content_layout = QVBoxLayout() # Vertical layout for logo and text
        header_content_layout.setSpacing(5)
        logo_container_layout = QHBoxLayout()
        logo_container_layout.addStretch(1)
        logo_label = QLabel()
        logo_path_obj = _get_bundled_resource_path_macos("app_icon_logo.png")
        if logo_path_obj and logo_path_obj.is_file():
            pixmap = QPixmap(str(logo_path_obj))
            logo_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            logo_label.setText("[Logo]")
        logo_container_layout.addWidget(logo_label)
        logo_container_layout.addStretch(1)
        header_content_layout.addLayout(logo_container_layout)
        self.status_title = QLabel("Setup Complete")
        self.status_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_title.setStyleSheet("font-size: 24px; font-weight: 600; color: #1a1a1a; font-family: 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif;")
        header_content_layout.addWidget(self.status_title)
        header_centering_layout.addLayout(header_content_layout)
        header_centering_layout.addStretch(1) # Right stretch
        main_layout.addLayout(header_centering_layout)
        main_layout.addSpacing(15) # Space after header

        # --- Main Info Text (Centered) ---
        info_centering_layout = QHBoxLayout()
        info_centering_layout.addStretch(1)
        self.info_text = QLabel("ANPE GUI is ready for using.")
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_text.setWordWrap(False)
        self.info_text.setMinimumWidth(350)
        self.info_text.setStyleSheet("font-size: 14px; color: #3c3c3c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; line-height: 140%;")
        info_centering_layout.addWidget(self.info_text)
        info_centering_layout.addStretch(1)
        main_layout.addLayout(info_centering_layout)
        main_layout.addSpacing(15)

        # --- Success Container (modified style, centered) ---
        self.success_container_centering_layout = QHBoxLayout()
        self.success_container_centering_layout.addStretch(1)
        self.success_container = QFrame()
        self.success_container.setFixedWidth(650)
        self.success_container.setStyleSheet("""
            QFrame { background-color: #e6f4ea; border-radius: 10px; border: none; }
        """)
        success_layout = QVBoxLayout(self.success_container)
        success_layout.setContentsMargins(20, 20, 20, 20)
        success_message = QLabel("You can now launch ANPE GUI to start extracting noun phrases.")
        success_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_message.setWordWrap(True)
        success_message.setStyleSheet("font-size: 13px; color: #2e7d32; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; background-color: transparent; border: none;")
        success_layout.addWidget(success_message)
        self.success_container_centering_layout.addWidget(self.success_container)
        self.success_container_centering_layout.addStretch(1)
        main_layout.addLayout(self.success_container_centering_layout)
        self.success_container.setVisible(True) # Show by default, hide on error

        # --- Uninstall Info Label (Centered, below success container) ---
        uninstall_info_centering_layout = QHBoxLayout()
        uninstall_info_centering_layout.addStretch(1)
        self.uninstall_info_label = QLabel()
        self.uninstall_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.uninstall_info_label.setWordWrap(True)
        self.uninstall_info_label.setOpenExternalLinks(False) # No links here
        self.uninstall_info_label.setStyleSheet("""
            font-size: 12px; color: #4A4A4A; /* Slightly muted color */
            font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
            background-color: #F3F3F3; /* Subtle background */
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 10px;
            line-height: 130%;
        """)
        # Set a fixed width to control its appearance within the centered layout
        self.uninstall_info_label.setFixedWidth(600)
        uninstall_info_centering_layout.addWidget(self.uninstall_info_label)
        uninstall_info_centering_layout.addStretch(1)
        main_layout.addLayout(uninstall_info_centering_layout)
        main_layout.addSpacing(15) # Added spacing after uninstall_info_label
        self.uninstall_info_label.setVisible(False) # Hidden by default

        # --- Error Highlight Frame (Centered when visible) ---
        self.error_container_centering_layout = QHBoxLayout()
        self.error_container_centering_layout.addStretch(1)
        self.error_container = QFrame()
        self.error_container.setFixedWidth(650)
        self.error_container.setStyleSheet("""
            QFrame { background-color: #fdecea; border-radius: 10px; border: none; }
        """)
        error_layout = QVBoxLayout(self.error_container)
        error_layout.setContentsMargins(20, 20, 20, 20)
        error_layout.setSpacing(8)
        error_header = QHBoxLayout()
        error_title = QLabel("Setup Error")
        error_title.setStyleSheet("font-weight: 600; color: #b71c1c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; font-size: 15px; background-color: transparent; border: none;")
        error_header.addWidget(error_title)
        error_header.addStretch()
        error_layout.addLayout(error_header)
        self.error_highlight = QLabel()
        self.error_highlight.setWordWrap(True)
        self.error_highlight.setStyleSheet("font-size: 13px; color: #5a5a5a; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; line-height: 140%; background-color: transparent; border: none;")
        error_layout.addWidget(self.error_highlight)
        self.error_container_centering_layout.addWidget(self.error_container)
        self.error_container_centering_layout.addStretch(1)
        main_layout.addLayout(self.error_container_centering_layout)
        self.error_container.setVisible(False) # Hide by default

        # --- Log Viewer (Centered when visible, slightly restyled) ---
        self.log_container_centering_layout = QHBoxLayout()
        self.log_container_centering_layout.addStretch(1)
        self.log_container = QFrame()
        self.log_container.setFixedWidth(550)
        self.log_container.setStyleSheet("""
            QFrame { background-color: #f0f0f0; border-radius: 10px; border: none; }
        """)
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(20, 15, 20, 15)
        log_layout.setSpacing(8)
        log_header_layout = QHBoxLayout()
        log_header = QLabel("Details")
        log_header.setStyleSheet("font-weight: 500; color: #4c4c4c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; font-size: 14px; background-color: transparent; border: none;")
        log_header_layout.addWidget(log_header)
        log_header_layout.addStretch()
        export_button = QPushButton("Export Log")
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setStyleSheet("QPushButton { background-color: #e9e9e9; color: #3c3c3c; border: none; border-radius: 6px; padding: 5px 10px; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; font-size: 12px; font-weight: 500;} QPushButton:hover { background-color: #dcdcdc; } QPushButton:pressed { background-color: #d0d0d0; }")
        export_button.clicked.connect(self._export_log)
        log_header_layout.addWidget(export_button)
        log_layout.addLayout(log_header_layout)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFont(QFont("Menlo", 11))
        self.log_viewer.setStyleSheet("background-color: #ffffff; border: 1px solid #dcdcdc; border-radius: 6px; padding: 8px; selection-background-color: #007AFF; selection-color: white;")
        self.log_viewer.setMinimumHeight(140)
        log_layout.addWidget(self.log_viewer)
        self.log_container_centering_layout.addWidget(self.log_container)
        self.log_container_centering_layout.addStretch(1)
        main_layout.addLayout(self.log_container_centering_layout)
        self.log_container.setVisible(False) # Hide by default

        # --- Feedback Section (Always Visible) ---
        feedback_layout = QHBoxLayout()
        feedback_layout.addStretch(1)
        feedback_label = ClickableLabel("Feedback is welcome! Report issues or suggest features on <a href=\"https://github.com/rcverse/anpe-gui/issues\">GitHub</a>.")
        feedback_label.setStyleSheet("font-size: 12px; color: #6c6c6c; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;")
        feedback_label.setOpenExternalLinks(True)
        feedback_layout.addWidget(feedback_label)
        feedback_layout.addStretch(1)
        main_layout.addLayout(feedback_layout)

        # Add flexible space before buttons
        main_layout.addStretch(1)

        # --- Footer with buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch(1) # Push buttons to the right

        # Final button (Launch or Close)
        self.final_button = QPushButton("Launch ANPE GUI") # Default to Launch
        self.final_button.setDefault(True)
        self.final_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF; color: white; border: none; border-radius: 6px;
                padding: 8px 16px; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px; font-weight: 500; min-width: 100px;
            }
            QPushButton:hover { background-color: #0070E0; }
            QPushButton:pressed { background-color: #0062C7; }
            QPushButton#closeButton {
                 background-color: #e9e9e9; color: #3c3c3c;
            }
             QPushButton#closeButton:hover { background-color: #dcdcdc; }
            QPushButton#closeButton:pressed { background-color: #d0d0d0; }
        """)
        self.final_button.clicked.connect(self._handle_final_action)
        button_layout.addWidget(self.final_button)
        main_layout.addLayout(button_layout)

    def set_success_state(self, success: bool, log_content: str = "", error_message: str = None):
        """Set the state of the view based on success or failure."""
        self._log_content = log_content
        self._success = success

        if success:
            self.status_title.setText("Setup Complete")
            self.info_text.setText("ANPE GUI is now ready for use.")
            self.success_container.setVisible(True)
            self.error_container.setVisible(False)
            self.log_container.setVisible(False) # Keep log hidden on success
            
            # Set and show uninstall info
            self.uninstall_info_label.setText(
                "<b>Tips for Uninstall:</b> A utility script named <code>clean_anpe.sh</code> is available in the "
                "<code>/Extras</code> folder inside the downloaded <code>.dmg</code> file. "
                "To use it, open the <code>.dmg</code>, scroll down to find the folder and script, then in Terminal, "
                "type <code>sh </code>, drag the script file into the Terminal window, and press Enter. "
                "This will help remove the application and its related data."
            )
            self.uninstall_info_label.setVisible(True)
            
            self.final_button.setText("Launch ANPE GUI")
            self.final_button.setObjectName("") # Reset object name for styling
            self.final_button.setStyleSheet(self.final_button.styleSheet()) # Re-apply default style
        else:
            self.status_title.setText("Setup Failed")
            self.info_text.setText("Unfortunately, the setup process encountered an error.")
            self.success_container.setVisible(False)
            self.error_container.setVisible(True)
            self.log_container.setVisible(True) # Show log on error
            self.uninstall_info_label.setVisible(False) # Hide on error

            if error_message:
                self._error_message = error_message
            elif log_content:
                self._error_message = self._extract_error_from_log(log_content)
            else:
                self._error_message = "An unknown error occurred during setup."

            self.error_highlight.setText(self._error_message)
            self.log_viewer.setText(log_content)
            self.final_button.setText("Close")
            # Use object name to apply specific 'close' button style from stylesheet
            self.final_button.setObjectName("closeButton")
            self.final_button.setStyleSheet(self.final_button.styleSheet())

    def _extract_error_from_log(self, log_content: str) -> str:
        """Extract a meaningful error message from the log content."""
        # Define patterns using standard strings with doubled backslashes
        error_patterns = [
            'ERROR: (.*?)(?:\\n|$)', # Look for lines starting with ERROR:
            'Exception: (.*?)(?:\\n|$)',
            'Failed to (.*?)(?:\\n|$)',
            # Doubled backslashes for traceback regex
            'Traceback \\(most recent call last\\):(?:\\n.*?)+?(\\w*Error: .*?)(?:\\n|$)' 
        ]
        for pattern in error_patterns:
            # Using re.IGNORECASE | re.DOTALL for matching
            matches = re.findall(pattern, log_content, re.IGNORECASE | re.DOTALL)
            if matches:
                # Get the last captured group (the error message part)
                last_match = matches[-1]
                # If the pattern captured multiple groups (like traceback), ensure we get the right one
                if isinstance(last_match, tuple):
                    last_match = last_match[-1] # Assume error message is last group
                
                last_match = str(last_match).strip().replace('\n', ' ')
                # Try to remove excessive path info if present
                last_match = re.sub('in [/\\.\\w]+:', '', last_match)
                # Limit length
                return last_match[:300] + ('...' if len(last_match) > 300 else '')

        # Fallback: Look for last lines containing 'error'
        error_lines = [line.strip() for line in log_content.split('\n') if 'error' in line.lower()]
        if error_lines:
             last_line = error_lines[-1]
             return last_line[:300] + ('...' if len(last_line) > 300 else '')

        return "An unknown error occurred. Please check the exported log for details."

    def _export_log(self):
        """Export the log content to a file."""
        if not self._log_content:
            QMessageBox.warning(self, "Export Failed", "No log content available to export.")
            return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"anpe_setup_log_{timestamp}.txt"
        downloads_path = os.path.expanduser("~/Downloads")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Log", os.path.join(downloads_path, default_filename),
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self._log_content)
                QMessageBox.information(self, "Log Exported", f"Log file saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to save log file: {str(e)}")

    def _handle_final_action(self):
        """Handle the final button click (Launch or Close)."""
        # Emit the renamed signal, passing the success state
        self.launch_requested.emit(self._success)

    # Compatibility methods (Update or remove if adapter pattern is gone)
    def get_finish_button(self):
        """Get the final button (compatibility)."""
        return self.final_button

    def set_title_text(self, text):
        """Set the title text (compatibility)."""
        self.status_title.setText(text)

    def set_message_text(self, text):
        """Set the message text (compatibility)."""
        self.info_text.setText(text) 