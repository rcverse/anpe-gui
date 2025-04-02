"""
Step indicator widget for workflow visualization.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtProperty, QPropertyAnimation, QEasingCurve


class StepIndicator(QFrame):
    """
    Widget to indicate a step in a workflow process.
    Shows a step number with a title and can be marked as active/inactive.
    """
    
    def __init__(self, title, active=False, parent=None):
        """
        Initialize the step indicator.
        
        Args:
            title: Title of the step
            active: Whether the step is active
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Set object name for styling
        self.setObjectName("StepIndicator")
        
        # Set up properties
        self._active = active
        self.setProperty("active", active)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create title label
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        
        # Set minimum size
        self.setMinimumSize(150, 50)
        
        # Apply initial style
        self.update_style()
    
    @pyqtProperty(bool)
    def active(self):
        """Get the active state."""
        return self._active
    
    @active.setter
    def active(self, value):
        """Set the active state and update styles."""
        if self._active != value:
            self._active = value
            self.setProperty("active", value)
            self.update_style()
    
    def update_style(self):
        """Update the widget style based on active state."""
        # Force style sheet update
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
    
    def animate_activation(self, active):
        """
        Animate the activation state change.
        
        Args:
            active: Whether to animate to active or inactive state
        """
        self.active = active
        
        # Create animation for size change
        if active:
            # Grow slightly when activated
            animation = QPropertyAnimation(self, b"maximumHeight")
            animation.setDuration(200)
            animation.setStartValue(self.height())
            animation.setEndValue(self.height() + 10)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
        else:
            # Shrink back to normal when deactivated
            animation = QPropertyAnimation(self, b"maximumHeight")
            animation.setDuration(200)
            animation.setStartValue(self.height())
            animation.setEndValue(self.height() - 10)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start() 