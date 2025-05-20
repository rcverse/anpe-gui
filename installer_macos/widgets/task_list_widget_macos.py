from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap, QIcon
import os
import logging

# CORRECTED IMPORT: Use macOS specific resource finder
from ..installer_core_macos import _get_bundled_resource_path_macos 

# Get logger instance for this module
logger = logging.getLogger(__name__) 

# Task statuses (can be shared or redefined)
class TaskStatus:
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3
    NEEDS_ACTION = 4  # New status for tasks requiring further action

class TaskItemMacOS(QWidget): # Renamed
    """A widget representing a single task with status indicator (macOS styled)."""
    
    def __init__(self, task_name: str, parent=None):
        """Initialize a task item."""
        super().__init__(parent)
        # Remove frame-specific style setting
        # self.setFrameStyle(QFrame.Shape.NoFrame)
        # Set background to match container explicitly 
        self.setStyleSheet("background: #F7F7F7;") 
        self._task_name = task_name
        self._status = TaskStatus.PENDING
        self._setup_ui()
        self.update_status(TaskStatus.PENDING, "")
        
    def _setup_ui(self):
        """Set up the user interface for this task item."""
        # self.setFrameStyle(QFrame.Shape.NoFrame) # Moved to __init__
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5) # Keep minimal margins
        layout.setSpacing(10)
        
        # Status indicator icon
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(16, 16)
        layout.addWidget(self.status_icon)
        
        # Task description label
        self.task_label = QLabel(self._task_name)
        self.task_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Use macOS system font
        self.task_label.setStyleSheet("font-size: 13px; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; background-color: transparent; border: none;")
        layout.addWidget(self.task_label)
        
    def update_status(self, status: int, status_text: str):
        """Update the task's status and visual appearance, using provided text."""
        self._status = status
        
        # Clear previous icon/text
        self.status_icon.clear()
        self.status_icon.setStyleSheet("") # Clear any fallback styles

        # Define base style for macOS
        base_style = "font-size: 13px; font-family: 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; background-color: transparent; border: none;"

        # Update label style based on status
        if status == TaskStatus.PENDING:
            self.task_label.setStyleSheet(f"color: #888888; font-weight: normal; {base_style}") # Grey out pending
        elif status == TaskStatus.PROCESSING:
            self.task_label.setStyleSheet(f"color: #005A9C; font-weight: bold; {base_style}")
            # Maybe add a spinner/busy indicator later?
        elif status == TaskStatus.COMPLETED:
            self.task_label.setStyleSheet(f"color: #3B7D23; font-weight: normal; {base_style}") # Green text for success
            # Load success icon using QPixmap (ensure assets are accessible)
            try:
                # Pass only the filename
                success_icon_path_obj = _get_bundled_resource_path_macos("success.png") 
                success_icon_path = str(success_icon_path_obj) if success_icon_path_obj else None
                if success_icon_path and os.path.exists(success_icon_path):
                    pixmap = QPixmap(success_icon_path)
                    if not pixmap.isNull():
                        self.status_icon.setPixmap(pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    else:
                        self.status_icon.setText("✓"); self.status_icon.setStyleSheet("color: #3B7D23; font-weight: bold;")
                else:
                    self.status_icon.setText("✓"); self.status_icon.setStyleSheet("color: #3B7D23; font-weight: bold;")
            except Exception: # Fallback if get_resource_path fails
                self.status_icon.setText("✓"); self.status_icon.setStyleSheet("color: #3B7D23; font-weight: bold;")
                
        elif status == TaskStatus.NEEDS_ACTION:
            # Use black text to make it stand out from pending tasks
            self.task_label.setStyleSheet(f"color: #333333; font-weight: normal; {base_style}")
            
            # Add an info icon or special indicator if desired
            try:
                # Try to use info.png icon if available
                info_icon_path_obj = _get_bundled_resource_path_macos("info.png")
                info_icon_path = str(info_icon_path_obj) if info_icon_path_obj else None
                if info_icon_path and os.path.exists(info_icon_path):
                    pixmap = QPixmap(info_icon_path)
                    if not pixmap.isNull():
                        self.status_icon.setPixmap(pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    else:
                        # Text fallback if icon load fails
                        self.status_icon.setText("i")
                        self.status_icon.setStyleSheet("color: #005A9C; font-weight: bold;")
                else:
                    # Text fallback if icon not found
                    self.status_icon.setText("i")
                    self.status_icon.setStyleSheet("color: #005A9C; font-weight: bold;")
            except Exception: # Fallback if get_resource_path fails
                self.status_icon.setText("i")
                self.status_icon.setStyleSheet("color: #005A9C; font-weight: bold;")
                
            # ONLY set text if status_text is provided and different from current
            if status_text and self.task_label.text() != status_text:
                logger.debug(f"TaskItem {self._task_name}: Setting label text to '{status_text}'")
                self.task_label.setText(status_text)
                
        elif status == TaskStatus.FAILED:
            original_text = self.task_label.text()
            # Special case check (adjust if needed)
            if "checking model presence" in original_text.lower() or "check" in self._task_name.lower(): 
                 self.task_label.setText("Models need installation")
                 # Use NEEDS_ACTION styling instead of custom styling
                 self.update_status(TaskStatus.NEEDS_ACTION, "Models need installation")
                 return # Skip the rest of the FAILED styling

            # Apply standard FAILED styling for other failures
            self.task_label.setStyleSheet(f"color: #DD3333; font-weight: normal; {base_style}") 
            # --- Update task text --- 
            logger.debug(f"TaskItem {self._task_name}: Received update_status(status={status}, status_text='{status_text}')")
            
            # ONLY set text if status_text is provided and different from current
            if status_text and self.task_label.text() != status_text:
                logger.debug(f"TaskItem {self._task_name}: Setting label text from signal to '{status_text}'")
                self.task_label.setText(status_text)
            elif status_text:
                 logger.debug(f"TaskItem {self._task_name}: Label text already matches signal '{status_text}', not setting.")
            else:
                 logger.debug(f"TaskItem {self._task_name}: status_text empty, not changing label text ('{self.task_label.text()}').")

class TaskListWidgetMacOS(QWidget): # Renamed
    """A widget displaying a list of tasks with macOS styling."""
    
    def __init__(self, parent=None):
        """Initialize the task list widget."""
        super().__init__(parent)
        # Explicitly make this widget transparent and borderless
        self._tasks = {}  # Maps task_id to TaskItemMacOS
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the user interface."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5) # Keep minimal margins
        self.layout.setSpacing(0) # Set spacing to 0 to remove gaps
        self.layout.addStretch(1)  # Push content to top
        
    def add_task(self, task_id: str, task_name: str) -> str:
        """Add a task to the list."""
        task_item = TaskItemMacOS(task_name) # Use renamed TaskItemMacOS
        self._tasks[task_id] = task_item
        self.layout.insertWidget(self.layout.count() - 1, task_item)
        return task_id
    
    @pyqtSlot(str, int, str) # Update signature to accept text
    def update_task_status(self, task_id: str, status: int, status_text: str):
        """Update the status and text of a specific task."""
        if task_id in self._tasks:
            self._tasks[task_id].update_status(status, status_text)
            
    def clear_tasks(self):
        """Remove all tasks from the list."""
        # (Keep existing logic)
        for task_item in self._tasks.values():
            task_item.deleteLater()
        self._tasks.clear()
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() 