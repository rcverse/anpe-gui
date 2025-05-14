from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPalette, QColor, QFont, QIcon

class CustomTitleBar(QWidget):
    """A modern, elegant custom title bar widget for frameless windows."""

    # Signals for window control
    minimize_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, title: str, parent=None, accent_color="#0078D7"):
        """
        Initialize the custom title bar.
        
        Args:
            title: The title text to display
            parent: Parent widget
            accent_color: Main color theme for the title bar (default: Windows blue)
        """
        super().__init__(parent)
        self._title = title
        self._accent_color = accent_color
        self._mouse_pressed = False
        self._mouse_press_pos = QPoint()
        self._window_pos = QPoint()

        # Set up appearance
        self.setAutoFillBackground(True)
        self._update_background_color()
        self.setFixedHeight(40)  # Slightly taller for a more modern look
        
        # Apply drop shadow effect for depth
        if parent:
            try:
                shadow = QGraphicsDropShadowEffect()
                shadow.setBlurRadius(15)
                shadow.setColor(QColor(0, 0, 0, 50))
                shadow.setOffset(0, 2)
                parent.setGraphicsEffect(shadow)
            except Exception as e:
                print(f"Warning: Could not apply shadow effect: {e}")
        
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface elements."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)  # More left padding for title
        layout.setSpacing(8)

        # Window Icon (optional - uncomment if you have an icon)
        # self.icon_label = QLabel()
        # icon_pixmap = QPixmap("path/to/icon.png").scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        # self.icon_label.setPixmap(icon_pixmap)
        # layout.addWidget(self.icon_label)
        # layout.addSpacing(8)

        # Title Label with improved typography
        self.title_label = QLabel(self._title)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.title_label.setStyleSheet(f"""
            color: #333333; 
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 11pt;
        """)
        layout.addWidget(self.title_label)

        # Control buttons container (for consistent styling)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Minimize Button - modern style with proper alignment
        self.minimize_button = QPushButton("—")  # Em dash looks better than underscore
        self.minimize_button.setFixedSize(34, 34)
        self.minimize_button.setStyleSheet(self._get_button_style("minimize"))
        self.minimize_button.clicked.connect(self.minimize_requested.emit)
        self.minimize_button.setToolTip("Minimize")
        button_layout.addWidget(self.minimize_button)

        # Close Button - modern style with proper X symbol
        self.close_button = QPushButton("✕")  # Unicode multiplication sign
        self.close_button.setFixedSize(34, 34)
        self.close_button.setStyleSheet(self._get_button_style("close"))
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.setToolTip("Close")
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _get_button_style(self, button_type):
        """Get the stylesheet for a specific button type."""
        base_style = """
            QPushButton { 
                border: none; 
                background-color: transparent; 
                font-family: 'Segoe UI', Arial;
                font-size: 10pt; 
                font-weight: bold; 
                color: #555555; 
                border-radius: 0px;
            }
        """
        
        if button_type == "minimize":
            return base_style + """
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.1); }
                QPushButton:pressed { background-color: rgba(0, 0, 0, 0.15); }
            """
        elif button_type == "close":
            return base_style + """
                QPushButton:hover { background-color: #E81123; color: white; }
                QPushButton:pressed { background-color: #F1707A; color: white; }
            """
        return base_style

    def set_title(self, title: str):
        """Update the window title text."""
        self._title = title
        self.title_label.setText(title)

    def set_accent_color(self, color: str):
        """Change the accent color of the title bar."""
        self._accent_color = color
        self._update_background_color()

    def _update_background_color(self):
        """Sets the background color of the title bar."""
        palette = self.palette()
        # Subtle gradient effect using background-color stylesheet
        self.setStyleSheet(f"""
            CustomTitleBar {{
                background-color: #f8f8f8;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border-bottom: none;
                border-image: linear-gradient(to right, #e0e0e0, #d0d0d0, #e0e0e0) 0 0 1 0 stretch;
            }}
        """)
        # The palette is still needed for compatibility
        palette.setColor(QPalette.ColorRole.Window, QColor("#f8f8f8"))
        self.setPalette(palette)

    # --- Window Dragging Logic with improved handling ---
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if press is on the title area, not on buttons
            child_widget = self.childAt(event.pos())
            if (child_widget is None or 
                child_widget == self.title_label or 
                (hasattr(self, 'icon_label') and child_widget == self.icon_label)):
                self._mouse_pressed = True
                self._mouse_press_pos = event.globalPosition().toPoint()
                self._window_pos = self.window().pos()
                # Change cursor to indicate dragging
                self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events for window dragging."""
        if self._mouse_pressed:
            delta = event.globalPosition().toPoint() - self._mouse_press_pos
            self.window().move(self._window_pos + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events to end dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_pressed = False
            # Restore cursor
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def changeEvent(self, event):
        """Handle window state changes (active/inactive)."""
        if event.type() == event.Type.ActivationChange:
            if self.window().isActiveWindow():
                self.title_label.setStyleSheet("""
                    color: #333333; 
                    font-weight: bold;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 11pt;
                """)
            else:
                self.title_label.setStyleSheet("""
                    color: #777777; 
                    font-weight: bold;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 11pt;
                """)
        super().changeEvent(event)

# Example usage (for testing the title bar directly)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.resize(500, 300)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # Enable for shadow effects

            central_widget = QWidget()
            central_widget.setObjectName("centralWidget")
            central_widget.setStyleSheet("""
                #centralWidget {
                    background-color: #f5f5f5;
                    border-radius: 5px;
                }
            """)
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(0,0,0,0)
            main_layout.setSpacing(0)

            self.title_bar = CustomTitleBar("Elegant Custom Title Bar", self)
            main_layout.addWidget(self.title_bar)

            # Add some content below the title bar
            content_widget = QWidget()
            content_widget.setStyleSheet("""
                background-color: #f5f5f5; 
                border: 1px solid #e0e0e0; 
                border-top: none;
                border-bottom-left-radius: 5px;
                border-bottom-right-radius: 5px;
            """)
            content_layout = QVBoxLayout(content_widget)
            
            content_label = QLabel("Window Content Area")
            content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_label.setStyleSheet("color: #555; font-family: 'Segoe UI'; font-size: 14px; padding: 20px;")
            content_layout.addWidget(content_label)
            
            main_layout.addWidget(content_widget, 1) # Make it stretch

            # Connect title bar signals
            self.title_bar.minimize_requested.connect(self.showMinimized)
            self.title_bar.close_requested.connect(self.close)

    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
