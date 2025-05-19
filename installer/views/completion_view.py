from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QSizePolicy, QSpacerItem, QHBoxLayout, QFrame,
    QTextEdit, QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor, QTextCursor
import os
import re
import datetime
import logging

from ..utils import get_resource_path
from ..styles import PRIMARY_BUTTON_STYLE, TITLE_LABEL_STYLE, INFO_LABEL_STYLE, SECONDARY_BUTTON_STYLE, LOG_TEXT_AREA_STYLE

class CompletionViewWidget(QWidget):
    """Widget for the completion screen of the setup wizard (Windows version)."""
    # Signals emitted when the final button is clicked
    shortcut_requested = pyqtSignal(bool)
    launch_requested = pyqtSignal(bool)
    preserve_log_requested = pyqtSignal(bool)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the completion view."""
        # --- DEBUGGING PRINT ---
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Entering CompletionViewWidget.__init__")
        super().__init__(parent)
        self._setup_ui()
        self._log_content = ""  # Store log content for export
        self._error_message = ""  # Store extracted error message
        # Set initial state (e.g., assuming success until told otherwise)
        # self.set_success_state(True)
        self.logger.debug("Leaving CompletionViewWidget.__init__")

    def _setup_ui(self):
        """Set up the user interface elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 15, 25, 15)  # Reduced margins
        layout.setSpacing(10)  # Reduced spacing between elements

        # --- Header with Logo and Title ---
        header_layout = QHBoxLayout()
        
        # Logo (reduced size for better space usage)
        logo_label = QLabel()
        logo_path = get_resource_path("assets/app_icon_logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # High-DPI support
            screen = QApplication.primaryScreen()
            dpr = screen.devicePixelRatio() if screen else 1.0
            target_size = int(96 * dpr)
            scaled_pixmap = pixmap.scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            scaled_pixmap.setDevicePixelRatio(dpr)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setFixedSize(96, 96)
        header_layout.addWidget(logo_label)
        
        # Status Title
        self.status_title = QLabel("Setup Status") # Placeholder text
        self.status_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # Ensure left alignment
        self.status_title.setStyleSheet(TITLE_LABEL_STYLE) # Apply the centralized style
        header_layout.addWidget(self.status_title)  # Remove stretch factor
        header_layout.addStretch(1) # Add stretch after the title
        
        layout.addLayout(header_layout)
        
        # Add spacing instead of separator
        layout.addSpacing(15)

        # --- Info Text ---
        self.info_text = QLabel("Details about the setup process outcome...") # Placeholder
        self.info_text.setWordWrap(True)
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.info_text.setStyleSheet("font-size: 15px; color: #333333; font-family: 'Segoe UI', Arial, sans-serif; line-height: 140%;")
        layout.addWidget(self.info_text)
        
        # --- Error Highlight Label (only shown on failure) ---
        self.error_highlight = QLabel()
        self.error_highlight.setWordWrap(True)
        self.error_highlight.setStyleSheet("""
            font-size: 13px; 
            color: #DD3333; 
            background-color: #FFEEEE; 
            padding: 12px; 
            border-radius: 6px;
            border-left: 4px solid #DD3333;
            margin: 8px 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        self.error_highlight.setVisible(False)
        layout.addWidget(self.error_highlight)
        
        # --- Log Viewer (only shown on failure) ---
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 12, 0, 0)
        log_layout.setSpacing(8)
        
        # Add log header and Export button on the same line
        log_header_layout = QHBoxLayout()
        
        log_header = QLabel("Setup Log:")
        log_header.setStyleSheet("font-weight: bold; color: #444444; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;")
        log_header_layout.addWidget(log_header)
        
        log_header_layout.addStretch()
        
        # Export log button - moved to the header line
        export_button = QPushButton("Export Log")
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #1A88E1;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        export_button.setFixedSize(90, 26)  # Make button slightly larger
        export_button.clicked.connect(self._export_log)
        log_header_layout.addWidget(export_button)
        
        log_layout.addLayout(log_header_layout)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFont(QFont("Consolas", 9))
        self.log_viewer.setStyleSheet("""
            background-color: #F8F8F8; 
            border: 1px solid #E0E0E0;
            border-radius: 5px;
            padding: 8px;
            selection-background-color: #0078D7;
            selection-color: white;
        """)
        self.log_viewer.setMinimumHeight(120)  # Increased height slightly
        self.log_viewer.setMaximumHeight(180)  # Increased maximum height
        log_layout.addWidget(self.log_viewer)
        
        layout.addWidget(self.log_container)
        self.log_container.setVisible(False)
        
        # --- Reporting Instructions (only shown on failure) ---
        self.report_container = QWidget()
        report_layout = QVBoxLayout(self.report_container)
        report_layout.setContentsMargins(0, 10, 0, 5)
        report_layout.setSpacing(5)
        
        report_label = QLabel("Report this issue:")
        report_label.setStyleSheet("font-weight: bold; color: #444444; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;")
        report_layout.addWidget(report_label)
        
        # Put reporting links and note on the same line
        links_layout = QHBoxLayout()
        
        github_link = QLabel('<a href="https://github.com/rcverse/anpe-studio/issues">GitHub Issue</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setStyleSheet("font-size: 13px; font-family: 'Segoe UI', Arial, sans-serif;")
        links_layout.addWidget(github_link)
        
        links_layout.addWidget(QLabel("•"))
        
        email_link = QLabel('<a href="mailto:rcverse6@gmail.com">Email</a>')
        email_link.setOpenExternalLinks(True)
        email_link.setStyleSheet("font-size: 13px; font-family: 'Segoe UI', Arial, sans-serif;")
        links_layout.addWidget(email_link)
        
        links_layout.addSpacing(20)  # Add more spacing before the note
        
        # Add the note on the same line
        report_note = QLabel("Please include the exported log file with your report.")
        report_note.setStyleSheet("font-size: 12px; font-style: italic; color: #666666; font-family: 'Segoe UI', Arial, sans-serif;")
        links_layout.addWidget(report_note)
        
        links_layout.addStretch()
        report_layout.addLayout(links_layout)
        
        layout.addWidget(self.report_container)
        self.report_container.setVisible(False)

        # Add flexible space
        layout.addStretch(1)

        # --- Options (Windows Specific, shown on success) ---
        self.options_container = QWidget()
        options_layout = QVBoxLayout(self.options_container)
        options_layout.setSpacing(12)
        options_layout.setContentsMargins(0, 5, 0, 5)
        
        options_title = QLabel("Installation Options")
        options_title.setStyleSheet("font-weight: bold; color: #444444; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;")
        options_layout.addWidget(options_title)
        
        self.shortcut_checkbox = QCheckBox("Create Desktop/Start Menu Shortcut")
        self.shortcut_checkbox.setChecked(True) # Default to checked
        self.shortcut_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                spacing: 10px; /* Space between indicator and text */
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 3px;
            }
            /* Removed ::indicator styling to allow default checkmark */
        """)
        options_layout.addWidget(self.shortcut_checkbox)

        self.launch_checkbox = QCheckBox("Launch ANPE now")
        self.launch_checkbox.setChecked(True) # Default to checked
        self.launch_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                spacing: 10px; /* Space between indicator and text */
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 3px;
            }
            /* Removed ::indicator styling to allow default checkmark */
        """)
        options_layout.addWidget(self.launch_checkbox)

        # Added checkbox for preserving the log
        self.preserve_log_checkbox = QCheckBox("Preserve installation log file")
        self.preserve_log_checkbox.setChecked(False) # Default to unchecked
        self.preserve_log_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                spacing: 10px; /* Space between indicator and text */
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 3px;
            }
        """)
        options_layout.addWidget(self.preserve_log_checkbox)
        
        # Add options with spacing
        layout.addWidget(self.options_container)
        layout.addSpacing(20)

        # --- Complete/Close Button ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.complete_button = QPushButton("Complete") # Text changes based on state
        self.complete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.complete_button.setObjectName("CompleteButton")
        self.complete_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1A88E1;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        self.complete_button.clicked.connect(self._handle_complete)
        
        button_layout.addWidget(self.complete_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addSpacing(8)  # Small margin at the bottom

        # Hide options initially, shown by set_success_state
        self.options_container.setVisible(False)

    def set_success_state(self, success: bool, log_content: str = "", error_message: str = None):
        """Configure the view based on the setup outcome."""
        self.logger.debug(f"Entering set_success_state(success={success}, log_len={len(log_content)}, error='{error_message}')")
        self._log_content = log_content
        # Store the error message passed from the main window
        self._error_message = error_message if error_message else "" 

        if success:
            self.logger.debug("Configuring view for SUCCESS state.")
            self.status_title.setText("Setup Complete!")
            self.status_title.setStyleSheet("font-size: 26px; font-weight: bold; color: #0078D7; font-family: 'Segoe UI', Arial, sans-serif;")
            self.info_text.setText(
                "ANPE Studio has been successfully installed and is ready to use.\n\n"
                "Feedbacks are welcome! Please report any issues or suggestions to rcverse6@gmail.com."
            )
            self.options_container.setVisible(True)
            self.complete_button.setText("Complete")
            self.complete_button.setStyleSheet("""
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: bold;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #1A88E1;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
            """)
            self.logger.debug("Set options container visible, button text to 'Complete'.")
            
            # Hide error components
            self.log_container.setVisible(False)
            self.report_container.setVisible(False)
            self.error_highlight.setVisible(False)
            self.logger.debug("Hid log container, report container, and error highlight.")
        else:
            self.logger.debug("Configuring view for FAILURE state.")
            self.status_title.setText("Setup Failed")
            self.status_title.setStyleSheet("font-size: 26px; font-weight: bold; color: #DD3333; font-family: 'Segoe UI', Arial, sans-serif;")
            self.info_text.setText("An error occurred during the installation process. We apologize for the inconvenience.")
            self.options_container.setVisible(False)
            self.complete_button.setText("Close")
            self.complete_button.setStyleSheet("""
                QPushButton {
                    background-color: #DD3333;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: bold;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #E84C4C;
                }
                QPushButton:pressed {
                    background-color: #C72F2F;
                }
            """)
            self.logger.debug("Set options container hidden, button text to 'Close'.")
            
            # Extract and display the error (use the passed message first, then try extracting)
            display_error = self._error_message if self._error_message else self._extract_error_from_log(log_content)
            if display_error:
                self.logger.debug(f"Displaying error message: '{display_error}'")
                self.error_highlight.setText(f"Error details: {display_error}")
                self.error_highlight.setVisible(True)
            else:
                 self.logger.debug("No specific error message to display in highlight.")
                 self.error_highlight.setVisible(False)
            
            # Show log components with size constraints
            if log_content:
                self.logger.debug("Setting log content in log viewer.")
                # Trim log content if too long
                if len(log_content) > 5000:
                    shortened_log = log_content[:2000] + "\n...[log trimmed]...\n" + log_content[-2000:]
                    self.log_viewer.setText(shortened_log)
                else:
                    self.log_viewer.setText(log_content)
                self.log_viewer.moveCursor(QTextCursor.MoveOperation.Start)
                self.log_container.setVisible(True)
                self.logger.debug("Log container set visible.")
            else:
                self.logger.debug("No log content provided, hiding log container.")
                self.log_container.setVisible(False)
            
            # Show reporting instructions
            self.report_container.setVisible(True)
            self.logger.debug("Report container set visible.")
        self.logger.debug("Leaving set_success_state.")

    def _extract_error_from_log(self, log_content: str) -> str:
        """Extract the most relevant error message from log content."""
        self.logger.debug("Attempting to extract error from log content.")
        if not log_content:
            self.logger.debug("No log content to extract error from.")
            return ""
            
        # Look for common error patterns
        error_patterns = [
            # Look for lines with ERROR, CRITICAL, Failed, etc.
            r'ERROR: (.*?)(?:\n|$)',
            r'CRITICAL: (.*?)(?:\n|$)',
            r'CRITICAL ERROR: (.*?)(?:\n|$)',
            r'Error: (.*?)(?:\n|$)',
            r'Failed: (.*?)(?:\n|$)',
            r'Exception: (.*?)(?:\n|$)',
            # Look for Python exceptions
            r'([A-Za-z]+Error: .*?)(?:\n|$)',
            r'([A-Za-z]+Exception: .*?)(?:\n|$)',
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, log_content)
            if matches:
                # Return the first significant error message
                for match in matches:
                    if len(match) > 5:  # Ensure it's not just a short message
                        return match.strip()
        
        return "No specific error details found. Please check the log for more information."

    def _export_log(self):
        """Export the log to a file."""
        if not self._log_content:
            QMessageBox.warning(self, "Export Failed", "No log content available to export.")
            return
            
        # Suggest a filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"anpe_setup_log_{timestamp}.txt"
        
        # Open save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Log File",
            default_filename,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self._log_content)
                QMessageBox.information(
                    self, 
                    "Log Exported", 
                    f"Log file has been exported to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    f"Failed to export log file: {str(e)}"
                )

    def _handle_complete(self):
        """Emit signals based on checkbox states and request closing."""
        self.logger.debug(f"_handle_complete called. options_container.isVisible(): {self.options_container.isVisible()}")

        # Shortcut checkbox
        if self.shortcut_checkbox.isVisible():
            checked_state = self.shortcut_checkbox.isChecked()
            self.logger.debug(f"Shortcut checkbox is visible, checked: {checked_state}. Emitting shortcut_requested.")
            self.shortcut_requested.emit(checked_state)
        else:
            self.logger.debug("Shortcut checkbox is not visible.")

        # Launch checkbox
        if self.launch_checkbox.isVisible():
            checked_state = self.launch_checkbox.isChecked()
            self.logger.debug(f"Launch checkbox is visible, checked: {checked_state}. Emitting launch_requested.")
            self.launch_requested.emit(checked_state)
        else:
            self.logger.debug("Launch checkbox is not visible.")

        # Preserve log checkbox - TARGET OF INVESTIGATION
        preserve_log_cb_visible = self.preserve_log_checkbox.isVisible()
        # Use info level for this specific log to make it stand out for debugging this issue.
        self.logger.info(f"Preserve log checkbox - Visible: {preserve_log_cb_visible}")
        if preserve_log_cb_visible:
            checked_state = self.preserve_log_checkbox.isChecked()
            self.logger.info(f"Preserve log checkbox - Checked: {checked_state}. Emitting preserve_log_requested.")
            self.preserve_log_requested.emit(checked_state)
        else:
            self.logger.info("Preserve log checkbox is NOT visible. Not emitting preserve_log_requested.")

        self.logger.debug("Emitting close_requested signal.")
        self.close_requested.emit()

# Example usage (for testing the view directly)
if __name__ == '__main__':
    import sys
    import logging # Added import for logging
    from PyQt6.QtWidgets import QApplication, QPushButton, QHBoxLayout

    # --- Basic logging setup for test script --- 
    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)])
    logger = logging.getLogger(__name__) # Get a logger for this test script
    logger.info("Starting CompletionViewWidget test script...")
    # --- End logging setup ---

    app = QApplication(sys.argv)
    container = QWidget()
    main_layout = QVBoxLayout(container)

    completion_view = CompletionViewWidget()
    main_layout.addWidget(completion_view)

    # Add buttons to test state changes
    button_layout = QHBoxLayout()
    success_button = QPushButton("Set Success")
    fail_button = QPushButton("Set Failure")
    button_layout.addWidget(success_button)
    button_layout.addWidget(fail_button)
    main_layout.addLayout(button_layout)

    # Add a test log for the failure case
    test_log = """
2023-10-15 14:49:32,123 - anpe.setup_models - INFO - Starting model setup
2023-10-15 14:49:35,246 - anpe.setup_models - INFO - Checking spaCy model
2023-10-15 14:49:40,357 - anpe.setup_models - INFO - Downloading spaCy model: en_core_web_md
2023-10-15 14:49:50,489 - anpe.setup_models - ERROR - Failed to download model: Connection error
2023-10-15 14:49:51,123 - anpe.setup_models - CRITICAL - ConnectionError: Failed to establish a connection to the model repository
2023-10-15 14:49:52,246 - anpe.setup_models - INFO - Model setup process failed
    """

    success_button.clicked.connect(lambda: completion_view.set_success_state(True))
    fail_button.clicked.connect(lambda: completion_view.set_success_state(False, test_log))

    # Connect signals to print output
    completion_view.shortcut_requested.connect(lambda checked: print(f"Shortcut requested: {checked}"))
    completion_view.launch_requested.connect(lambda checked: print(f"Launch requested: {checked}"))
    completion_view.preserve_log_requested.connect(lambda checked: print(f"Preserve log requested: {checked}"))
    completion_view.close_requested.connect(lambda: print("Close requested"))

    container.resize(550, 450) # Increased default size
    container.show()
    completion_view.set_success_state(True) # Start in success state for demo

    sys.exit(app.exec())
