from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap, QIcon
import os

from ..utils import get_resource_path

# Task statuses
class TaskStatus:
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3

class TaskItem(QFrame):
    """A widget representing a single task with status indicator."""
    
    def __init__(self, task_name: str, parent=None):
        """Initialize a task item."""
        super().__init__(parent)
        self._task_name = task_name
        self._status = TaskStatus.PENDING
        self._setup_ui()
        self.update_status(TaskStatus.PENDING)
        
    def _setup_ui(self):
        """Set up the user interface for this task item."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(10)
        
        # Status indicator icon
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(16, 16)
        layout.addWidget(self.status_icon)
        
        # Task description label
        self.task_label = QLabel(self._task_name)
        self.task_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.task_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.task_label)
        
    def update_status(self, status: int):
        """Update the task's status and visual appearance."""
        self._status = status
        
        # Clear previous icon/text
        self.status_icon.clear()
        self.status_icon.setStyleSheet("") # Clear any fallback styles

        # Update label style based on status
        if status == TaskStatus.PENDING:
            self.task_label.setStyleSheet("color: #888888; font-weight: normal; font-size: 14px;") # Grey out pending
        elif status == TaskStatus.PROCESSING:
            self.task_label.setStyleSheet("color: #005A9C; font-weight: bold; font-size: 14px;")
            # Maybe add a spinner/busy indicator later?
        elif status == TaskStatus.COMPLETED:
            self.task_label.setStyleSheet("color: #3B7D23; font-weight: normal; font-size: 14px;") # Green text for success
            # Load success icon using QPixmap
            success_icon_path = get_resource_path("assets/success.png") # Use PNG
            if os.path.exists(success_icon_path):
                pixmap = QPixmap(success_icon_path)
                if not pixmap.isNull():
                     self.status_icon.setPixmap(pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    # Fallback if PNG load fails
                    self.status_icon.setText("✓")
                    self.status_icon.setStyleSheet("color: #3B7D23; font-weight: bold;")
            else:
                # Fallback if icon not found
                self.status_icon.setText("✓")
                self.status_icon.setStyleSheet("color: #3B7D23; font-weight: bold;")
        elif status == TaskStatus.FAILED:
            # Special case: Model check 'failure' is expected if not installed
            original_text = self.task_label.text()
            if "checking model presence" in original_text.lower():
                self.task_label.setText("Models need installation")
                self.task_label.setStyleSheet("color: #888888; font-weight: normal; font-size: 14px;") # Neutral (like PENDING)
                self.status_icon.clear() # No icon for this state
                return # Skip the rest of the FAILED styling

            # Apply standard FAILED styling for other failures
            self.task_label.setStyleSheet("color: #DD3333; font-weight: normal; font-size: 14px;") # Red text for fail
            
            # Prefix with "Failed: " if not already done
            if not original_text.startswith("Failed: "):
                 self.task_label.setText(f"Failed: {original_text}")

            # Load error icon using QPixmap
            error_icon_path = get_resource_path("assets/error.png") # Use PNG
            if os.path.exists(error_icon_path):
                pixmap = QPixmap(error_icon_path)
                if not pixmap.isNull():
                    self.status_icon.setPixmap(pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                     # Fallback if PNG load fails
                    self.status_icon.setText("✗")
                    self.status_icon.setStyleSheet("color: #DD3333; font-weight: bold;")
            else:
                # Fallback if icon not found
                self.status_icon.setText("✗")
                self.status_icon.setStyleSheet("color: #DD3333; font-weight: bold;")
        
        # Update the task text based on status
        if status == TaskStatus.PENDING:
            pass  # Keep original text
        elif status == TaskStatus.PROCESSING:
            # Change "Install" to "Installing", etc.
            text = self.task_label.text()
            if text.lower().startswith("install "):
                self.task_label.setText(f"Installing {text[8:]}")
            elif text.lower().startswith("set up "):
                self.task_label.setText(f"Setting up {text[7:]}")
            elif text.lower().startswith("configure "):
                self.task_label.setText(f"Configuring {text[10:]}")
            elif text.lower().startswith("download "):
                self.task_label.setText(f"Downloading {text[9:]}")
            elif text.lower().startswith("validate "):
                self.task_label.setText(f"Validating {text[9:]}")
            elif text.lower().startswith("upgrade "):
                self.task_label.setText(f"Upgrading {text[8:]}")
            elif text.lower().startswith("copy "):
                self.task_label.setText(f"Copying {text[5:]}")
        elif status == TaskStatus.COMPLETED:
            # Change "Installing" to "Installed", etc.
            text = self.task_label.text()
            if text.lower().startswith("installing "):
                self.task_label.setText(f"Installed {text[11:]}")
            elif text.lower().startswith("setting up "):
                self.task_label.setText(f"Set up {text[11:]}")
            elif text.lower().startswith("configuring "):
                self.task_label.setText(f"Configured {text[12:]}")
            elif text.lower().startswith("downloading "):
                self.task_label.setText(f"Downloaded {text[12:]}")
            elif text.lower().startswith("validating "):
                self.task_label.setText(f"Validated {text[11:]}")
            elif text.lower().startswith("upgrading "):
                self.task_label.setText(f"Upgraded {text[10:]}")
            elif text.lower().startswith("copying "):
                self.task_label.setText(f"Copied {text[8:]}")
        elif status == TaskStatus.FAILED:
            # Prefix with "Failed: " except for specific cases
            text = self.task_label.text()
            if not text.startswith("Failed: "):
                # Don't mark "Checking model presence" as failed since this is expected
                if "checking model presence" in text.lower():
                    self.task_label.setText("Models need installation")
                else:
                    self.task_label.setText(f"Failed: {text}")

class TaskListWidget(QWidget):
    """A widget displaying a list of tasks with their completion status."""
    
    def __init__(self, parent=None):
        """Initialize the task list widget."""
        super().__init__(parent)
        self._tasks = {}  # Maps task_id to TaskItem
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the user interface."""
        # Use a simple VBoxLayout with no scrolling
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.layout.setSpacing(5)
        self.layout.addStretch(1)  # Push content to top
        
    def add_task(self, task_id: str, task_name: str) -> str:
        """Add a task to the list."""
        task_item = TaskItem(task_name)
        self._tasks[task_id] = task_item
        
        # Add to layout before the stretch
        self.layout.insertWidget(self.layout.count() - 1, task_item)
        
        return task_id
    
    @pyqtSlot(str, int)
    def update_task_status(self, task_id: str, status: int):
        """Update the status of a specific task."""
        if task_id in self._tasks:
            self._tasks[task_id].update_status(status)
            
    def clear_tasks(self):
        """Remove all tasks from the list."""
        for task_item in self._tasks.values():
            task_item.deleteLater()
        self._tasks.clear()
        
        # Remove all widgets except the stretch
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() 