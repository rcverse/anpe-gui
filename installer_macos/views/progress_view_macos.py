"""
Progress view for macOS setup

This module provides the progress screen for the macOS setup wizard,
with styling and functionality optimized for macOS.
"""

import os
import re
import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QHBoxLayout,
    QSizePolicy, QSpacerItem, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor
from PyQt6.QtWidgets import QApplication

from ..widgets.task_list_widget_macos import TaskListWidgetMacOS, TaskStatus
from ..installer_core_macos import _get_bundled_resource_path_macos

# Get logger instance
logger = logging.getLogger()

class ProgressViewWidget(QWidget):
    """Widget for displaying progress during setup stages (macOS version)."""

    # Signal emitted when cancellation is confirmed
    cancel_requested = pyqtSignal()

    def __init__(self, title: str, parent=None):
        """Initialize the progress view."""
        super().__init__(parent)
        self._title = title
        self._tasks = {}
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI elements."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(10)

        # --- Header --- (Centering Logo and Title Block)
        header_centering_layout = QHBoxLayout()
        header_centering_layout.addStretch(1) # Left stretch

        header_content_layout = QVBoxLayout() # Vertical layout for logo and text
        header_content_layout.setSpacing(5)

        # Logo (Optional)
        logo_label = QLabel()
        # Pass only filename
        logo_path_obj = _get_bundled_resource_path_macos("app_icon_logo.png") 
        if logo_path_obj and logo_path_obj.is_file():
            pixmap = QPixmap(str(logo_path_obj))
            # High-DPI support
            screen = QApplication.primaryScreen()
            dpr = screen.devicePixelRatio() if screen else 1.0
            target_size = int(64 * dpr)
            scaled_pixmap = pixmap.scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            scaled_pixmap.setDevicePixelRatio(dpr)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setFixedSize(64, 64)
        else:
            logo_label.setText("ANPE")
            logo_label.setStyleSheet("font-size: 20px; font-weight: 500; font-family: 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;")
        logo_container_layout = QHBoxLayout()
        logo_container_layout.addStretch(1)
        logo_container_layout.addWidget(logo_label)
        logo_container_layout.addStretch(1)
        header_content_layout.addLayout(logo_container_layout)

        # Title and description (centered)
        title_label = QLabel(self._title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: 500; color: #000000; font-family: 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif; background-color: transparent; border: none;")
        header_content_layout.addWidget(title_label)

        explanation_text = ""
        if "Environment" in self._title:
            explanation_text = "Setting up a dedicated Python environment with required dependencies."
        elif "Language Models" in self._title:
            explanation_text = "Downloading and installing the language models needed for text analysis."

        if explanation_text:
            explanation_label = QLabel(explanation_text)
            explanation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Removed max-width
            explanation_label.setWordWrap(True) # Ensure word wrap
            explanation_label.setStyleSheet("font-size: 13px; color: #494949; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; background-color: transparent; border: none;")
            header_content_layout.addWidget(explanation_label)

        header_centering_layout.addLayout(header_content_layout)
        header_centering_layout.addStretch(1) # Right stretch
        main_layout.addLayout(header_centering_layout)

        # Increase space after header block
        main_layout.addSpacing(20) 

        # --- Task List (Centered) ---
        task_container_centering_layout = QHBoxLayout()
        task_container_centering_layout.addStretch(1)

        self._task_list = TaskListWidgetMacOS()
        if self._tasks:
            for task_id, task_name in self._tasks.items():
                self._task_list.add_task(task_id, task_name)

        task_container = QFrame()
        task_container.setFixedWidth(650) # Changed width to 650
        task_container.setStyleSheet("""
            QFrame {
                background-color: #F7F7F7;
                border-radius: 8px;
                border: 1px solid #E5E5E5;
            }
        """)
        task_container_layout = QVBoxLayout(task_container)
        task_container_layout.setContentsMargins(15, 15, 15, 15)
        task_container_layout.addWidget(self._task_list)

        task_container_centering_layout.addWidget(task_container)
        task_container_centering_layout.addStretch(1)
        main_layout.addLayout(task_container_centering_layout)

        main_layout.addSpacing(10)

        # --- Progress Layout (Bar and Status - Centered) ---
        progress_centering_layout = QHBoxLayout()
        progress_centering_layout.addStretch(1)

        progress_content_layout = QVBoxLayout()
        progress_content_layout.setSpacing(8)
        progress_content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center vertically within its space

        # Status Label (centered)
        self._status_label = QLabel("Preparing...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True) # Ensure word wrap
        self._status_label.setStyleSheet("font-size: 13px; color: #494949; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; background-color: transparent; border: none;")
        progress_content_layout.addWidget(self._status_label)

        # Progress bar (centered, fixed width)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setFixedWidth(450) # Give fixed width
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #EBEBEB;
                /* Alignment handled by layout */
            }
            QProgressBar::chunk {
                background-color: #0D6EFD; /* Keep blue for now */
                border-radius: 4px;
            }
        """)
        progress_content_layout.addWidget(self._progress_bar, 0, Qt.AlignmentFlag.AlignCenter) # Center horizontally

        progress_centering_layout.addLayout(progress_content_layout)
        progress_centering_layout.addStretch(1)
        main_layout.addLayout(progress_centering_layout)

        main_layout.addSpacing(10)

        # --- Details/Log Section with toggle (Button Centered) ---
        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center contents

        # Details toggle button (centered)
        details_button_layout = QHBoxLayout()
        details_button_layout.addStretch(1)
        # Set initial text to Hide Details
        self._details_button = QPushButton("Hide Details") 
        self._details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._details_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 0.5px solid #CCCCCC;
                border-radius: 5px;
                padding: 5px 10px;
                font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
                font-size: 12px;
                color: #494949;
            }
            QPushButton:hover {
                background-color: #F5F5F5;
            }
            QPushButton:pressed {
                background-color: #EBEBEB;
            }
        """)
        self._details_button.clicked.connect(self._toggle_details)
        details_button_layout.addWidget(self._details_button)
        details_button_layout.addStretch(1)
        details_layout.addLayout(details_button_layout)

        # Log text area (centered, fixed width)
        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setFixedWidth(650) # Increased width
        self._log_area.setFont(QFont("Menlo", 11))
        self._log_area.setStyleSheet("""
            background-color: #F8F8F8;
            border: 1px solid #E0E0E0;
            border-radius: 6px;
            padding: 8px;
            selection-background-color: #0D6EFD;
            selection-color: white;
        """)
        # Decrease min/max height
        self._log_area.setMinimumHeight(120) 
        self._log_area.setMaximumHeight(180) 
        self._log_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        # Set log area visible by default
        self._log_area.setVisible(True) 
        # Center log area horizontally
        log_area_centering_layout = QHBoxLayout()
        log_area_centering_layout.addStretch(1)
        log_area_centering_layout.addWidget(self._log_area)
        log_area_centering_layout.addStretch(1)
        details_layout.addLayout(log_area_centering_layout)

        main_layout.addWidget(details_container)

        # Add flexible space before buttons
        main_layout.addStretch(1)

        # --- Footer with buttons (Cancel bottom-right, red, confirmation) ---
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)  # Push buttons to the right

        # Cancel button (red, requires confirmation)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #DC3545; /* Red */
                color: white;
                border: none;
                border-radius: 5px;
                padding: 7px 12px;
                font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #BB2D3B; /* Darker Red */
            }
            QPushButton:pressed {
                background-color: #B02A37; /* Even Darker Red */
            }
        """)
        # Connect to the confirmation handler instead of directly emitting
        self.cancel_button.clicked.connect(self._confirm_cancel)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

    def _confirm_cancel(self):
        """Show confirmation dialog before cancelling."""
        reply = QMessageBox.question(
            self,
            'Confirm Cancel',
            "Are you sure you want to cancel the setup process? Any progress will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # Default to No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("User confirmed cancellation.")
            self.cancel_requested.emit() # Emit the actual cancel signal
        else:
            logger.info("User aborted cancellation.")

    def _toggle_details(self):
        """Show or hide the log area."""
        current_state = self._log_area.isVisible()
        new_state = not current_state

        self._log_area.setVisible(new_state)

        # Update button text
        self._details_button.setText("Hide Details" if new_state else "See Details") # Changed text

    def setup_tasks(self, tasks: dict):
        """Set up the tasks to be displayed."""
        self._tasks = tasks
        # Clear existing tasks if any before adding new ones
        self._task_list.clear_tasks()
        for task_id, task_name in tasks.items():
            self._task_list.add_task(task_id, task_name)

    def setup_tasks_from_worker(self, worker):
        """Set up tasks from a worker instance."""
        tasks_to_setup = {}
        if hasattr(worker, '_tasks'):
            tasks_to_setup = worker._tasks
        elif hasattr(worker, 'tasks'):
            tasks_to_setup = worker.tasks

        if tasks_to_setup:
             self.setup_tasks(tasks_to_setup)
        else:
             logger.warning("Worker provided has no '_tasks' or 'tasks' attribute to setup.")

    @pyqtSlot(str)
    def update_status(self, status: str):
        """Update the status text."""
        self._status_label.setText(status)

    @pyqtSlot(str)
    def append_log(self, message: str):
        """Append a message to the log area."""
        self._log_area.append(message)
        # Auto-scroll to the bottom
        self._log_area.verticalScrollBar().setValue(self._log_area.verticalScrollBar().maximum())

    @pyqtSlot()
    def clear_log(self):
        """Clear the log area."""
        self._log_area.clear()

    @pyqtSlot(int, int)
    def set_progress_range(self, min_val: int, max_val: int):
        """Set the range of the progress bar."""
        self._progress_bar.setRange(min_val, max_val)

    @pyqtSlot(int)
    def set_progress_value(self, value: int):
        """Set the value of the progress bar."""
        self._progress_bar.setValue(value)

    @pyqtSlot(str, int, str)
    def update_task_status(self, task_id: str, status: int, status_text: str = ""):
        """Update the status of a task, using provided text."""
        self._task_list.update_task_status(task_id, status, status_text)

    def _simplify_model_name(self, full_model_name: str) -> str:
        """Simplifies a full model filename like 'en_core_web_sm-3.7.1.tar.gz' to 'en_core_web_sm'."""
        # Regex to capture the base name, e.g., en_core_web_sm from en_core_web_sm-3.7.1.tar.gz
        match = re.match(r'^([a-zA-Z0-9_]+(?:-[a-zA-Z0-9_]+)*)', full_model_name)
        if match:
            return match.group(1)
        # Fallback if regex fails
        if '-' in full_model_name:
            base_name = full_model_name.split('-', 1)[0]
            # Avoid returning just 'en' if model is 'en-core-web-sm' etc. by checking length or presence of underscore
            if len(base_name) > 3 or '_' in base_name: 
                return base_name
        if '.' in full_model_name:
            # Fallback to splitting by dot if hyphen split wasn't satisfactory or applicable
            return full_model_name.split('.', 1)[0]
        return full_model_name

    def _friendly_status_message(self, status: str) -> Optional[str]:
        """
        Robust mapping for status messages: only show known user-friendly messages,
        map/suppress technical/log messages, and always map errors.
        """
        s = status.strip()
        s_lower = s.lower()

        # 1. Error messages
        if s_lower.startswith("error") or any(x in s_lower for x in ["failed", "exception", "traceback"]):
            return "An error occurred during setup. See details."

        # 2. Downloading models
        if s_lower.startswith("downloading language model") or "downloading required models" in s_lower:
            return "Downloading language models..."

        # 3. Extracting models
        if s_lower.startswith("extracting language models"):
            return "Extracting language models..."

        # 4. Suppress technical/log messages
        technical_patterns = [
            r"^running command:",
            r"^executing command:",
            r"^attempting to download",
            r"^from alias",
            r"^/.*",  # absolute file paths
            r"^found python executable:",
            r"^standalone python unpacked to:",
            r"^target installation path:",
            r"^pip bootstrap check",
            r"^sync pip command finished",
            r"^--- stdout ---",
            r"^--- stderr ---",
            r"requirements file",
            r"\.py", r"\.so", r"\.dylib", r"site-packages"
        ]
        for pattern in technical_patterns:
            if re.search(pattern, s_lower):
                return None

        # 5. Whitelist of known user-friendly messages
        whitelist = {
            "validated installation path.",
            "unpacking python environment...",
            "locating python executable...",
            "ensuring pip is available...",
            "installing required build tools...",
            "locating requirements file...",
            "environment setup complete.",
            "starting language model check...",
            "checking language models...",
            "language model setup complete.",
            "all language models ready.",
            "installing application dependencies from macos_requirements.txt...",
            "installing application dependencies...",
            "pip is ready.",
            "setup complete.",
        }
        if s_lower in whitelist:
            return s

        # 6. Fallback: suppress anything else
        return None

    def handle_status_update(self, status: str):
        """Handle a status update by making it more user-friendly."""
        # Rule 1: Model related statuses (handled by _clean_model_status)
        cleaned_model_status = self._clean_model_status(status)
        if cleaned_model_status:
            self.update_status(cleaned_model_status)
            return

        # Rule 2: Hide stderr messages from model setup script from main status
        if "model setup script STDERR:" in status:
            # These messages are often too verbose or cryptic for the main status.
            # They will still appear in the detailed log if logged by the worker.
            return

        # Rule 3: "Executing command:"
        if status.startswith("Executing command:"):
            self.update_status("Running setup script...")
            return
            
        # Rule 4: Common setup messages that might expose paths or be too verbose
        if "creating virtual environment" in status.lower():
            self.update_status("Setting up isolated Python environment...")
            return
        if "installing python" in status.lower() or "setting up python" in status.lower():
             self.update_status("Preparing Python runtime...")
             return
        if "verifying python installation" in status.lower():
            self.update_status("Verifying Python setup...")
            return
        
        # Rule 5: Standalone progress percentages
        if re.fullmatch(r'\s*\d+\s*%?\s*', status.strip()): # Matches "50%" or "50"
            self.update_status(f"Progress: {status.strip()}")
            return

        # Fallback: If no specific rule applies, show the original status.
        self.update_status(status)

    def handle_log_update(self, log_line: str):
        """Handle a log update by appending to the log area."""
        if "%" in log_line and any(x in log_line for x in ["Downloading", "download"]):
            if "100%" in log_line or "0%" in log_line or "50%" in log_line or "75%" in log_line or "25%" in log_line:
                self.append_log(log_line)
        else:
            self.append_log(log_line)

    def add_task_list_widget(self, task_list):
        """Add the task list widget to the view (compatibility)."""
        # Find the centered task container
        container_layout = None
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if isinstance(item, QHBoxLayout):
                 # Check if this QHBoxLayout contains our task container QFrame
                 for j in range(item.count()):
                     inner_item = item.itemAt(j)
                     if isinstance(inner_item.widget(), QFrame) and inner_item.widget().styleSheet().startswith("QFrame {\n                background-color: #F7F7F7;"):
                         container_layout = inner_item.widget().layout()
                         break
            if container_layout:
                break

        if container_layout:
             # Clear the container's layout and add the new task list
            while container_layout.count():
                child = container_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            container_layout.addWidget(task_list)
            self._task_list = task_list # Update internal reference
        else:
             logger.error("Could not find the task container layout to add task list widget.")

    def add_button(self, button):
        """Add a button to the view (compatibility - adds next to Cancel)."""
        # Find the button layout (the layout containing the Cancel button)
        button_layout = None
        for i in range(self.layout().count()):
             item = self.layout().itemAt(i)
             if isinstance(item, QHBoxLayout):
                 # Check if this QHBoxLayout contains our Cancel button
                 for j in range(item.count()):
                     inner_item = item.itemAt(j)
                     if isinstance(inner_item.widget(), QPushButton) and inner_item.widget().text() == "Cancel":
                         button_layout = item
                         break
             if button_layout:
                 break

        if button_layout:
             # Insert button *before* the Cancel button (usually primary action)
             button_layout.insertWidget(button_layout.count() - 1, button)
        else:
             logger.error("Could not find the button layout to add button.")

    def set_title_text(self, text):
        """Set the title text of the view (compatibility)."""
        # Find the title label (assuming it's the first QLabel with large font size)
        title_labels = self.findChildren(QLabel)
        for label in title_labels:
             if label.font().pointSize() > 16: # Heuristic for title
                 label.setText(text)
                 self._title = text # Update internal title
                 break

    def set_status_text(self, text):
        """Set the status text (compatibility)."""
        self.update_status(text) 

    def _clean_model_status(self, status: str) -> Optional[str]:
        """
        Cleans model-related status messages to be more user-friendly.
        Returns a cleaned string if a model pattern is matched, otherwise None.
        """
        # Pattern for "Downloading model file en_core_web_sm-3.7.1.tar.gz ..."
        match_specific_model_download = re.search(r'Downloading model file ([^/\s]+)', status, re.IGNORECASE)
        if match_specific_model_download:
            full_model_name = match_specific_model_download.group(1)
            simplified_name = self._simplify_model_name(full_model_name)
            progress_match = re.search(r'(\d+%?)', status) # Capture progress percentage
            progress_str = f" ({progress_match.group(1)})" if progress_match else ""
            return f"Downloading language model: {simplified_name}{progress_str}"

        # Pattern for generic model download messages like "Downloading [url] to [path]"
        # Ensure "model" is present to be more specific
        if "downloading" in status.lower() and "model" in status.lower():
            progress_match = re.search(r'(\d+%?)', status)
            progress_str = f" ({progress_match.group(1)})" if progress_match else ""
            return f"Downloading language models{progress_str}"

        # Pattern for "Extracting archive" or "Extracting model"
        if "extracting" in status.lower() and ("archive" in status.lower() or "model" in status.lower()):
            return "Extracting language models"

        return None # No model-specific pattern matched 