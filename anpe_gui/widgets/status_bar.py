# anpe_gui/widgets/status_bar.py
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QProgressBar, 
                             QLabel, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer

class StatusBar(QWidget):
    """
    Global status bar with progress indicator and text status.
    Displays beneath the log panel and provides feedback for all operations.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # Main layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 2, 5, 2)  # Slim margins for compact design
        
        # Status label for text updates
        self.status_label = QLabel("Ready")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False) # Text inside bar often looks cluttered
        self.progress_bar.setFixedHeight(16)  # Make it compact
        
        # Use a fixed width for the progress bar
        self.progress_bar.setFixedWidth(200)
        
        # Add separator line
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.VLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        
        # Add widgets to layout
        self.layout.addWidget(self.status_label)
        self.layout.addStretch()
        self.layout.addWidget(self.separator)
        self.layout.addWidget(self.progress_bar)
        
        # Set fixed height for the entire status bar
        self.setFixedHeight(24)
        
        # Add top border for visual separation
        self.setStyleSheet("""
            StatusBar {
                border-top: 1px solid #ccc;
                background-color: #f5f5f5;
            }
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 3px;
                background: white;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db; /* Blue color from theme */
                border-radius: 2px;
            }
        """)
        
        # Hide progress bar initially
        self.progress_bar.hide()
        self.separator.hide()
        
    @pyqtSlot(str)
    def showMessage(self, message, timeout=0):
        """Update the status message. Mimics QStatusBar API."""
        self.status_label.setText(message)
        # QTimer could be used here for timeout if needed, but often not required
        # for simple status updates. QStatusBar manages its own timeouts.
        # If implementing timeout: QTimer.singleShot(timeout, lambda: self.clearMessage()) 
        # self.clearMessage() would reset status_label.setText("Ready")

    @pyqtSlot(int, str)
    def update_progress(self, value, message=None):
        """Update the progress bar and optionally the status message."""
        if not self.progress_bar.isVisible():
            self.progress_bar.show()
            self.separator.show()
            
        self.progress_bar.setRange(0, 100) # Ensure determinate mode
        self.progress_bar.setValue(value)
        
        if message:
            self.status_label.setText(message)
            
    def start_progress(self, message="Processing..."):
        """Start an indeterminate progress operation."""
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.progress_bar.show()
        self.separator.show()
        self.status_label.setText(message)
        
    def stop_progress(self, message="Complete"):
        """Stop the progress bar and update status."""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(message)
        
        # Hide progress after a delay
        QTimer.singleShot(3000, self.clear_progress)
        
    def clear_progress(self):
        """Clear the progress bar and reset status."""
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.separator.hide()
        self.status_label.setText("Ready") 