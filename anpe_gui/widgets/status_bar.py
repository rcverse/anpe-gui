# anpe_gui/widgets/status_bar.py
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QProgressBar, 
                             QLabel, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation, QEasingCurve, QByteArray
from PyQt6.QtGui import QPalette, QColor
# Import necessary theme colors
from ..theme import PRIMARY_COLOR, SUCCESS_COLOR, BORDER_COLOR
# Import our new activity indicator
from .activity_indicator import PulsingActivityIndicator, STATE_IDLE, STATE_ACTIVE, STATE_WARNING, STATE_ERROR, STATE_CHECKING # Import states

class StatusBar(QWidget):
    """
    Global status bar with progress indicator and text status.
    Displays beneath the log panel and provides feedback for all operations.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self._progress_animation = None # Initialize animation attribute
        
    def setup_ui(self):
        # Main layout
        self.layout = QHBoxLayout(self)
        # Add vertical margins (left/right 5, top/bottom 5)
        self.layout.setContentsMargins(5, 3, 5, 3) # Adjusted margins (left, top, right, bottom)
        
        # Status label for text updates
        self.status_label = QLabel("Ready")
        
        # Create the pulsing activity indicator FIRST
        self.activity_indicator = PulsingActivityIndicator(self)
        self.activity_indicator.setFixedSize(24, 24) # Match progress bar height approx
        self.activity_indicator.idle() # Start in idle state
        self.activity_indicator.show() # Make sure it's visible

        # Progress bar (still used for determinate progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True) # Show percentage for better feedback
        self.progress_bar.setFixedHeight(22) # Consistent height
        self.progress_bar.setObjectName("AnimatedProgressBar")
        self.progress_bar.setFormat("Waiting for tasks")
        
        # Use a responsive width for the progress bar (20% of available width)
        self.progress_bar.setMinimumWidth(250)
        self.progress_bar.setSizePolicy(
            QSizePolicy.Policy.Minimum, 
            QSizePolicy.Policy.Fixed
        )
        
        # Add separator line
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.VLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        
        # Add widgets to main layout
        self.layout.addWidget(self.status_label)
        self.layout.addStretch()
        self.layout.addWidget(self.separator)
        # Add indicator AND progress bar
        self.layout.addWidget(self.activity_indicator)
        self.layout.addWidget(self.progress_bar)
        
        # Set initial state
        self.set_idle_state()
    
    def set_idle_state(self):
        """Set progress bar and indicator to idle state."""
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Waiting for tasks")
        self.progress_bar.show() # Ensure progress bar is visible
        
        # Set indicator to idle state
        self.activity_indicator.idle()
        self.activity_indicator.show()
        
        # Apply idle styling to progress bar
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                text-align: center;
                color: #666666;
                font-weight: normal;
                background-color: #f5f5f5;
                height: 22px;
            }}
            QProgressBar::chunk {{
                background-color: #dddddd; /* Light gray for idle state */
                border-radius: 2px;
                margin: 0px;
            }}
        """)

    @pyqtSlot(str)
    def showMessage(self, message, timeout=0, status_type='info'):
        """Update the status message, set its style property, and update indicator."""
        self.status_label.setText(message)
        # Set the 'status' property for MainWindow's stylesheet to apply
        self.status_label.setProperty('status', status_type)
        # Force style re-evaluation
        self.style().unpolish(self.status_label)
        self.style().polish(self.status_label)
        
        # Update indicator based on status_type (only for non-progress states)
        if status_type in ['ready', 'success', 'info']:
            self.activity_indicator.idle()
        elif status_type == 'warning':
            self.activity_indicator.warn()
        elif status_type in ['error', 'failed']:
            self.activity_indicator.error()
        # 'busy' and 'checking' states handled by start_progress/update_progress/set_checking

    @pyqtSlot(int, str)
    def update_progress(self, value, message=None):
        """Update the progress bar, its styling, activate indicator, and optionally the status message."""
        self.progress_bar.show()
        self.activity_indicator.show() # Ensure indicator is visible alongside progress bar
        # Start activity indicator animation in 'active' state
        self.activity_indicator.start()
            
        # Set progress bar format based on value
        if value == 100:
            self.progress_bar.setFormat("Completing...")
        else:
            self.progress_bar.setFormat("%p%")
        
        # Update progress bar - cap at 95% for visual consistency
        self.progress_bar.setRange(0, 100) # Ensure determinate mode
        
        # Stop any existing animation
        if self._progress_animation and self._progress_animation.state() == QPropertyAnimation.State.Running:
            self._progress_animation.stop()
            
        # Create and configure the animation
        self._progress_animation = QPropertyAnimation(self.progress_bar, b"value", self)
        self._progress_animation.setDuration(400)  # Animation duration in milliseconds
        self._progress_animation.setStartValue(self.progress_bar.value()) # Start from current value
        self._progress_animation.setEndValue(value) # Animate to the new value
        self._progress_animation.setEasingCurve(QEasingCurve.Type.InOutQuad) # Smooth easing
        self._progress_animation.finished.connect(self._clear_animation_reference) # Clear reference on finish
        self._progress_animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped) # Start animation

        # Change text visibility based on progress
        self.progress_bar.setTextVisible(True)
        
        # Apply style based on progress state - always use PRIMARY_COLOR
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                text-align: center;
                color: #333333;
                font-weight: bold;
                background-color: #f5f5f5;
                height: 22px;
            }}
            QProgressBar::chunk {{
                background-color: #8EACC0; /* Light Morandi blue */
                border-radius: 2px;
                margin: 0px;
            }}
        """)

        if message:
            # Set status message with 'busy' type while progress is active
            self.showMessage(message, status_type='busy') # showMessage doesn't set busy state for indicator

    def stop_progress(self, message="Complete", status_type='success'):
        """Stop the progress/activity indicator and update status, showing Completing->Complete."""
        # Ensure progress bar is visible for the final animation
        self.progress_bar.show()
        self.activity_indicator.show()
        
        # Trigger animation to 100% and show "Completing..."
        self.update_progress(100) 

        # Use a short delay to allow "Completing..." to render before changing to "Complete"
        QTimer.singleShot(100, lambda: self._finalize_stop_progress(message, status_type))

    def _finalize_stop_progress(self, message, status_type):
        """Internal method called after a short delay to set final state and indicator."""
        # Set final format
        self.progress_bar.setFormat("Complete")
        
        # Update status message with the final status type
        # showMessage will now also update the indicator based on the final status_type
        self.showMessage(message, status_type=status_type)
        
        # We don't reset to idle immediately here, let showMessage handle the final indicator state.
        # The idle state is set after a longer delay.
        QTimer.singleShot(3000, self.set_idle_state)

    def clear_progress(self):
        """Reset indicators to idle state."""
        self.set_idle_state()
        
        # Reset status label to default 'ready' state (calls showMessage which handles indicator)
        self.showMessage("ANPE Ready", status_type='ready')

    def set_checking(self):
        """Set the status bar to indicate a background check is in progress."""
        self.activity_indicator.show()
        self.progress_bar.hide() # Hide progress bar during checking state
        self.showMessage("Checking model status...", status_type='busy') # Use busy style for label
        self.activity_indicator.checking() # Set indicator to checking state

    @pyqtSlot()
    def _clear_animation_reference(self):
        """Slot to clear the animation reference when it finishes."""
        self._progress_animation = None 