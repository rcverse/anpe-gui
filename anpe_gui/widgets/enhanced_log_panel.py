"""
Enhanced log panel widget with filtering, clear, and copy capabilities.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QComboBox, QPushButton, QLabel, QApplication,
                             QMessageBox, QFileDialog, QFrame)
from PyQt6.QtCore import Qt, pyqtSlot, QUrl, QSize
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QBrush, QFont, QDesktopServices
import logging # Import logging for level constants
import platform # For system info
import sys      # For Python version
import importlib.metadata # For package versions
from datetime import datetime # For timestamp
import os       # For path operations
from anpe_gui.theme import get_scroll_bar_style
from anpe_gui.resource_manager import ResourceManager # Keep for now, might be used elsewhere

class EnhancedLogPanel(QWidget):
    """Enhanced log panel with filtering and copy functionality."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_entries = [] # Store all entries for filtering
        self._current_filter_level = logging.INFO # Default filter level
        self.setup_ui()
        
    def setup_ui(self):
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        
        # Header
        self.header_layout = QHBoxLayout()
        
        self.title_label = QLabel("Log Output")
        self.title_label.setStyleSheet("font-weight: bold;")
        
        self.filter_label = QLabel("Filter Level:")
        
        self.filter_combo = QComboBox()
        # Add levels using standard logging names and map to values
        self.log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        self.filter_combo.addItems(self.log_levels.keys())
        self.filter_combo.setCurrentText("INFO") # Default filter
        self.filter_combo.currentTextChanged.connect(self.update_filter)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip("Clear the log display")
        self.clear_button.clicked.connect(self.clear_log)
        self.clear_button.setProperty("secondary", True)
        
        self.export_button = QPushButton("Export")
        self.export_button.setToolTip("Export logs and system info to a file for reporting.")
        self.export_button.clicked.connect(self.prompt_export)
        self.export_button.setProperty("secondary", True)
        
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.filter_label)
        self.header_layout.addWidget(self.filter_combo)
        self.header_layout.addWidget(self.clear_button)
        self.header_layout.addWidget(self.export_button)
        
        self.layout.addLayout(self.header_layout)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # Ensure scroll bars are always visible and styled
        self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.log_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log_text.setStyleSheet(get_scroll_bar_style())
        
        self.layout.addWidget(self.log_text, 1) # Give stretch factor
        
        # Log level color mapping
        self.level_colors = {
            logging.DEBUG: QColor(100, 100, 100), # Gray
            logging.INFO: QColor(0, 0, 0),        # Black
            logging.WARNING: QColor(200, 120, 0), # Dark Orange
            logging.ERROR: QColor(200, 0, 0),     # Dark Red
            logging.CRITICAL: QColor(128, 0, 128) # Purple
        }

    @pyqtSlot(str, int) # Slot accepts message (str) and level (int)
    def add_log_entry(self, message, level):
        """Add a log entry with a specific level."""
        entry = {"level": level, "message": message}
        self._log_entries.append(entry)
        
        # Append to display only if it passes the current filter
        if self.should_display(entry):
            self.append_to_display(entry)

    def append_to_display(self, entry):
        """Append formatted entry to the QTextEdit."""
        level = entry["level"]
        message = entry["message"]
        level_name = logging.getLevelName(level)
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Format based on level
        log_format = QTextCharFormat()
        log_format.setForeground(QBrush(self.level_colors.get(level, QColor("black"))))
        if level >= logging.ERROR:
            log_format.setFontWeight(QFont.Weight.Bold)
        
        # Insert level name first (bold/colored)
        level_format = QTextCharFormat()
        level_format.setForeground(QBrush(self.level_colors.get(level, QColor("black"))))
        level_format.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"[{level_name}] ", level_format)
        
        # Insert message with standard formatting for the level
        cursor.insertText(message + "\n", log_format)
        
        # Auto-scroll to bottom
        self.log_text.ensureCursorVisible()

    def update_filter(self, level_name):
        """Update the displayed logs based on the selected filter level."""
        self._current_filter_level = self.log_levels.get(level_name, logging.INFO)
        self.log_text.clear()
        for entry in self._log_entries:
            if self.should_display(entry):
                self.append_to_display(entry)

    def should_display(self, entry):
        """Check if the entry's level meets the current filter level."""
        return entry["level"] >= self._current_filter_level

    def clear_log(self):
        """Clear the log display and the stored entries."""
        self._log_entries.clear()
        self.log_text.clear()

    def prompt_export(self):
        """Show a confirmation dialog before exporting logs and system info."""
        confirm_msg = QMessageBox(self.window())
        confirm_msg.setIcon(QMessageBox.Icon.Information)
        confirm_msg.setWindowTitle("Confirm Log Export")
        confirm_msg.setText(
            "This will gather log entries and system information "
            "(OS, Python, ANPE versions, etc.) into a single file."
        )
        confirm_msg.setInformativeText(
            "This file can be helpful for diagnosing issues or reporting bugs.\n\n"
            "Do you want to proceed?"
        )
        confirm_msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirm_msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        ret = confirm_msg.exec()
        
        if ret == QMessageBox.StandardButton.Yes:
            self.export_log_file()
        else:
            logging.debug("Log export cancelled by user.")

    def export_log_file(self):
        """Gather info, ask for save location, and write the log file."""
        try:
            system_info = self._gather_system_info()
            
            # Prepare log content
            log_content_parts = [
                "========================================",
                "        ANPE GUI Log Export",
                "========================================",
                f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "\n--- System Information ---",
                system_info,
                "\n--- Log Entries ---"
            ]
            
            # Append all log entries, regardless of current filter
            for entry in self._log_entries:
                level_name = logging.getLevelName(entry["level"])
                log_content_parts.append(f"[{level_name}] {entry['message']}")
            
            full_log_content = "\n".join(log_content_parts)
            
            # Suggest filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suggested_filename = f"anpe_gui_log_{timestamp}.log"
            
            # Ask for save location
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Log File As...",
                suggested_filename,
                "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
            )
            
            if save_path:
                try:
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(full_log_content)
                    logging.info(f"Log file exported successfully to: {save_path}")
                    self._show_export_success_dialog(save_path)
                except Exception as e:
                    logging.error(f"Error writing log file to {save_path}: {e}", exc_info=True)
                    QMessageBox.critical(
                        self, 
                        "Export Error", 
                        f"Failed to write log file.\nError: {e}"
                    )
            else:
                logging.info("Log export save operation cancelled.")
                
        except Exception as e:
            logging.error(f"Error during log export preparation: {e}", exc_info=True)
            QMessageBox.critical(
                self, 
                "Export Error", 
                f"An unexpected error occurred during export preparation.\nError: {e}"
            )

    def _gather_system_info(self) -> str:
        """Collects system, Python, and package information."""
        info_parts = []
        try:
            # OS Info
            info_parts.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
            info_parts.append(f"Architecture: {platform.machine()} ({platform.architecture()[0]})")
            
            # Python Info
            info_parts.append(f"Python Version: {sys.version}")
            info_parts.append(f"Python Executable: {sys.executable}")
            
            # ANPE GUI Version
            try:
                from anpe_gui.version import __version__ as gui_version
                info_parts.append(f"ANPE GUI Version: {gui_version}")
            except ImportError:
                info_parts.append("ANPE GUI Version: N/A (Could not import)")
                
            # ANPE Core Version
            try:
                core_version = importlib.metadata.version("anpe")
                info_parts.append(f"ANPE Core Version: {core_version}")
            except importlib.metadata.PackageNotFoundError:
                info_parts.append("ANPE Core Version: N/A (Not installed or found)")
            except Exception as e:
                info_parts.append(f"ANPE Core Version: Error ({e})")

            # Other Relevant Packages
            for pkg in ["spacy", "benepar", "nltk", "PyQt6"]:
                try:
                    version = importlib.metadata.version(pkg)
                    info_parts.append(f"{pkg} Version: {version}")
                except importlib.metadata.PackageNotFoundError:
                    info_parts.append(f"{pkg} Version: N/A (Not installed or found)")
                except Exception as e:
                     info_parts.append(f"{pkg} Version: Error ({e})")

            return "\n".join(info_parts)
        except Exception as e:
            logging.error(f"Failed to gather all system info: {e}", exc_info=True)
            info_parts.append(f"\nError gathering info: {e}")
            return "\n".join(info_parts)

    def _show_export_success_dialog(self, file_path: str):
        """Displays a standard dialog after successful log export."""
        msg_box = QMessageBox(self.window())
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Export Successful")
        # Use plain text format for the path for consistency
        msg_box.setText(f"Log file saved successfully to:\n{file_path}")
        
        # Add custom "View Folder" button and standard "OK" button
        btn_view_folder = msg_box.addButton("View Folder", QMessageBox.ButtonRole.ActionRole)
        btn_ok = msg_box.addButton(QMessageBox.StandardButton.Ok)
        
        msg_box.setDefaultButton(btn_ok)
        msg_box.exec()
        
        # Check if "View Folder" was clicked
        if msg_box.clickedButton() == btn_view_folder:
            self._open_containing_folder(file_path)

    def _open_containing_folder(self, file_path: str):
        """Opens the folder containing the specified file path."""
        folder_path = os.path.dirname(file_path)
        url = QUrl.fromLocalFile(folder_path)
        if not QDesktopServices.openUrl(url):
             logging.warning(f"Could not open folder: {folder_path}")
             QMessageBox.warning(self, "Error", f"Could not open the folder:\n{folder_path}")

    # --- Removed unused methods ---
    # def _open_github_issues(self):
    # def _open_email_client(self, attachment_path: str | None = None):
    # --- End Export Functionality --- 