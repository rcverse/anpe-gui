"""
Splash screen for the ANPE GUI application.
"""

import os
import time
import logging # Added logging
from PyQt6.QtWidgets import (QSplashScreen, QApplication, QProgressBar, 
                             QLabel, QVBoxLayout, QWidget)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QBrush, QRegion, QPainterPath, QPen
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QCoreApplication, QPropertyAnimation, QEasingCurve, QPointF, pyqtProperty, QRect, QRectF, QThread, QObject, pyqtSlot # Added QThread, QObject, pyqtSlot
from anpe_gui.theme import PRIMARY_COLOR  # Import the primary color
from anpe_gui.version import __version__ as gui_version  # Import GUI version directly from version.py

# Attempt to import ExtractorInitializer (might fail if ANPE isn't installed)
try:
    from anpe_gui.main_window import ExtractorInitializer # Import from MainWindow module
    INITIALIZER_AVAILABLE = True
except ImportError as e:
    INITIALIZER_AVAILABLE = False
    logging.warning(f"Could not import ExtractorInitializer for splash screen: {e}")
    # Define a dummy if needed, though we might just skip the check
    class ExtractorInitializer(QObject):
        initialized = pyqtSignal(object)
        error = pyqtSignal(str)
        def run(self): self.error.emit("ANPE Core not available")

try:
    from anpe import __version__ as core_version  # Import core version
except ImportError:
    core_version = "N/A"  # Fallback if core version can't be imported


class SplashScreen(QSplashScreen):
    """
    Custom splash screen with banner, progress bar, and actual initialization.
    """
    # Emits the final status dictionary or None on error when check is done
    initialization_complete = pyqtSignal(object)
    
    # Signal emitted when fade-out is complete and the splash can truly close (Kept from previous logic)
    fade_out_complete = pyqtSignal()
    
    def __init__(self, banner_path=None):
        """
        Initialize the splash screen using the provided banner or fallback.
        """
        # Create a custom banner instead of loading from file
        pixmap = self._create_custom_banner()
        
        super().__init__(pixmap)
        self.pixmap_height = pixmap.height()
        self.pixmap_width = pixmap.width()
        
        # Window flags
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | 
                           Qt.WindowType.FramelessWindowHint)
        
        # --- Define border radius before using it ---
        self.border_radius = 10 # Define radius for consistency
        
        # Setup content widget below banner
        self.setup_content_area()
        
        # Set fixed size for the entire splash window
        content_height = self.content_widget.sizeHint().height()
        total_height = self.pixmap_height + content_height
        self.setFixedSize(self.pixmap_width, total_height)
        
        # Initialization state
        self.init_thread = None
        self.init_worker = None
        self.final_init_status = None # To store the result
        self.status_label.setText("Initializing...")

        # Animation setup
        self._fade_animation = None
        self.setWindowOpacity(0.0) # Start fully transparent for fade-in

        # Center the splash screen
        self._center_on_screen()

    def _create_custom_banner(self):
        """Create a custom banner with logo on left and text on right."""
        width, height = 560, 200  # Wider banner for better spacing
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)  # Start with transparent background
        
        # Create high-quality painter with anti-aliasing
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        # Elegant background with subtle gradient
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor("#f9f9f9"))  # Light color start
        gradient.setColorAt(1, QColor("#f0f0f0"))  # Slightly darker end
        painter.fillRect(0, 0, width, height, QBrush(gradient))
        
        # Clear separation - left side for logo, right side for text
        logo_section_width = 220  # Dedicated width for logo
        text_section_width = width - logo_section_width
        
        # Left side: Logo only
        from anpe_gui.resource_manager import ResourceManager
        
        # Load the PNG with higher resolution for better quality
        logo = ResourceManager.get_pixmap("app_icon.png")
        
        # Get device pixel ratio for high DPI displays
        device_pixel_ratio = QApplication.primaryScreen().devicePixelRatio()
        
        # Scale logo to appropriate size while maintaining aspect ratio
        # Multiply by device pixel ratio to ensure crisp display on high DPI screens
        logo_size = 160
        target_size = int(logo_size * device_pixel_ratio)
        
        # Only scale down, not up to avoid pixelation
        if logo.width() > target_size or logo.height() > target_size:
            logo = logo.scaled(target_size, target_size, 
                            Qt.AspectRatioMode.KeepAspectRatio, 
                            Qt.TransformationMode.SmoothTransformation)
        
        # Set the device pixel ratio to ensure proper rendering
        # This is a crucial step for high DPI displays
        if device_pixel_ratio > 1.0:
            logo.setDevicePixelRatio(device_pixel_ratio)
            
        # Calculate display size (adjusted for device pixel ratio)
        display_size = logo_size
        
        # Center the logo in the left section
        logo_x = (logo_section_width - display_size) // 2
        logo_y = (height - display_size) // 2
        
        # Draw the pixmap at the calculated position
        painter.drawPixmap(logo_x, logo_y, display_size, display_size, logo)
        
        # Add a subtle separator line between logo and text
        separator_x = logo_section_width
        painter.setPen(QPen(QColor(220, 220, 220), 1))  # Lighter color for separator
        painter.drawLine(separator_x, 40, separator_x, height - 40)
        
        # Right side: Text content - nothing else
        text_start_x = logo_section_width + 30  # Start text with padding after separator
        
        # Draw main title "ANPE" using PRIMARY_COLOR
        primary_color = QColor(PRIMARY_COLOR)
        title_gradient = QLinearGradient(text_start_x, 0, text_start_x + 200, 0)
        title_gradient.setColorAt(0, primary_color.lighter(110))  # Slightly lighter version
        title_gradient.setColorAt(1, primary_color)  # Primary color
        
        # Use system fonts with better fallbacks for sharper text
        title_font = QFont()
        title_font.setFamily("Segoe UI")
        title_font.setPointSize(48)
        title_font.setWeight(QFont.Weight.Bold)
        if not QFont(title_font).exactMatch():
            title_font.setFamily("Arial")
            if not QFont(title_font).exactMatch():
                title_font.setFamily(title_font.defaultFamily())
            
        painter.setFont(title_font)
        # Use QPen with width 1.5 for slightly bolder, crisper text
        painter.setPen(QPen(QBrush(title_gradient), 1.5))
        
        # Draw title in its own region with proper vertical centering
        title_rect = QRect(text_start_x, 40, text_section_width - 40, 80)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, "ANPE")
        
        # Draw subtitle with proper spacing below the title - LIGHTER COLOR
        subtitle_font = QFont()
        subtitle_font.setFamily("Segoe UI")
        subtitle_font.setPointSize(14)
        subtitle_font.setWeight(QFont.Weight.Normal)
        if not QFont(subtitle_font).exactMatch():
            subtitle_font.setFamily("Arial")
            if not QFont(subtitle_font).exactMatch():
                subtitle_font.setFamily(subtitle_font.defaultFamily())
                
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#666666"))  # Darker gray for better contrast and readability
        
        # Subtitle in its own region below the title
        subtitle_rect = QRect(text_start_x, 105, text_section_width - 40, 30)
        painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, 
                        "Another Noun Phrase Extractor")
        
        # Add version info with improved rendering
        version_font = QFont()
        version_font.setFamily("Segoe UI")
        version_font.setPointSize(9)  # Smaller font size
        version_font.setWeight(QFont.Weight.Normal)  # Lighter weight
        
        if not QFont(version_font).exactMatch():
            version_font.setFamily("Arial")
            if not QFont(version_font).exactMatch():
                version_font.setFamily(version_font.defaultFamily())
                
        painter.setFont(version_font)
        painter.setPen(QColor("#777777"))  # Lighter color
        
        version_rect = QRect(text_start_x, 155, text_section_width - 40, 20)
        version_text = f"GUI v{gui_version} | Core v{core_version}"
        painter.drawText(version_rect, Qt.AlignmentFlag.AlignLeft, version_text)
        
        # Add author credit with improved rendering
        credit_font = QFont()
        credit_font.setFamily("Segoe UI")
        credit_font.setPointSize(8)  # Smaller font size
        credit_font.setWeight(QFont.Weight.Normal)
        
        if not QFont(credit_font).exactMatch():
            credit_font.setFamily("Arial")
            if not QFont(credit_font).exactMatch():
                credit_font.setFamily(credit_font.defaultFamily())
                
        painter.setFont(credit_font)
        painter.setPen(QColor("#888888"))  # Lighter color
        
        credit_rect = QRect(text_start_x, 175, text_section_width - 40, 20)
        painter.drawText(credit_rect, Qt.AlignmentFlag.AlignLeft, "@rcverse")
        
        painter.end()
        return pixmap

    def setup_content_area(self):
        """Set up the widget holding progress bar and status text with improved styles."""
        self.content_widget = QWidget(self)
        # Set background to white. Removed rounded bottom corners.
        self.content_widget.setStyleSheet(f"""
            background-color: white; 
            border-bottom-left-radius: 0px; /* Ensure square */
            border-bottom-right-radius: 0px; /* Ensure square */
            border-top-left-radius: 0px; 
            border-top-right-radius: 0px;
        """) 
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(25, 10, 25, 15) # Reduced top/bottom margins
        self.content_layout.setSpacing(5) # Reduced spacing

        # Status label
        self.status_label = QLabel("Loading...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use a slightly larger, darker font
        self.status_label.setStyleSheet("color: #444; font-size: 10pt;")

        self.content_layout.addWidget(self.status_label)

        # Position the content widget below the pixmap
        # Adjust height calculation since progress bar is removed
        self.content_widget.adjustSize() # Recalculate size based on content (just the label now)
        content_height_hint = self.content_widget.sizeHint().height()
        self.content_widget.setGeometry(0, self.pixmap_height, 
                                      self.pixmap_width, content_height_hint)

    def _center_on_screen(self):
        """Center the splash screen on the primary display."""
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())

    # Override drawContents to prevent default drawing over our content widget
    def drawContents(self, painter):
        pass # We handle drawing via the content widget

    def showMessage(self, message, alignment=Qt.AlignmentFlag.AlignLeft, color=QColor("black")):
        """Display a message (overrides QSplashScreen method)."""
        # Use our custom label instead
        self.status_label.setText(message)
        # self.repaint() # Not needed as label updates automatically

    # Removed set_progress method - progress will be handled by init logic

    def _fade(self, start_value, end_value, duration, on_finish=None):
        """Helper function to create and run fade animation."""
        if self._fade_animation:
            self._fade_animation.stop() # Stop existing animation

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(duration)
        self._fade_animation.setStartValue(float(start_value)) # Ensure float
        self._fade_animation.setEndValue(float(end_value))     # Ensure float
        self._fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        if on_finish:
            # Disconnect previous connections to avoid multiple calls
            try:
                self._fade_animation.finished.disconnect() 
            except TypeError: # No connection exists
                pass 
            self._fade_animation.finished.connect(on_finish)
            
        self._fade_animation.start()

    def fade_in(self, duration=300):
        """Fade the splash screen in."""
        self.setWindowOpacity(0.0) # Ensure starting point
        self.show() # Make it visible before animating opacity
        self._fade(0.0, 1.0, duration)

    def fade_out(self, duration=300):
        """Fade the splash screen out."""
        # Ensure we start from full opacity for the fade-out effect
        current_opacity = self.windowOpacity()
        # Connect the fade animation's finished signal to actually close the window
        self._fade(current_opacity, 0.0, duration, self._on_fade_out_complete) 

    def _on_fade_out_complete(self):
        """Called when the fade-out animation finishes."""
        logging.debug("Splash fade out complete.")
        self.fade_out_complete.emit() # Emit signal *before* closing
        self.close() # Actually close the window now
        self._fade_animation = None # Clean up animation object

    # --- Initialization Logic --- 

    def start_initialization(self):
        """
        Starts the actual initialization process in a background thread.
        """
        self.fade_in() # Show splash with fade-in
        QCoreApplication.processEvents() # Process events to ensure it's shown
        
        # Set initial status message
        self.showMessage("Initializing ANPE...")

        if not INITIALIZER_AVAILABLE:
            logging.error("ExtractorInitializer not available. Skipping ANPE check.")
            # Handle case where ANPE core check cannot run
            # Create a default error status
            error_status = {
                'spacy_models': [], 'benepar_models': [], 'nltk_present': False,
                'error': "ANPE core library not found or import failed."
            }
            # Emit completion signal with error status after a short delay
            QTimer.singleShot(1000, lambda: self._emit_completion(error_status))
            return

        # Proceed with background check
        self.init_thread = QThread()
        self.init_worker = ExtractorInitializer()
        self.init_worker.moveToThread(self.init_thread)
        
        # Connect worker signals to splash screen slots
        self.init_worker.initialized.connect(self._on_init_success)
        self.init_worker.error.connect(self._on_init_error)
        self.init_thread.started.connect(self.init_worker.run)
        
        # Clean up thread when worker finishes or errors out
        self.init_worker.initialized.connect(self.init_thread.quit)
        self.init_worker.error.connect(self.init_thread.quit)
        self.init_thread.finished.connect(self.init_thread.deleteLater)
        self.init_worker.initialized.connect(self.init_worker.deleteLater) # Clean up worker
        self.init_worker.error.connect(self.init_worker.deleteLater) # Clean up worker

        logging.debug("Splash Screen: Starting initialization thread.")
        self.init_thread.start()

    @pyqtSlot(object) # Receives the status dictionary 
    def _on_init_success(self, status_dict):
        """Slot called when the background initialization check completes successfully."""
        logging.info(f"Splash Screen: Initialization check successful. Status: {status_dict}")
        self.final_init_status = status_dict
        self.showMessage("ANPE initialization successful.") # Refined message
        self._emit_completion(self.final_init_status)
        
    @pyqtSlot(str)
    def _on_init_error(self, error_message):
        """Slot called when the background initialization check fails."""
        logging.error(f"Splash Screen: Initialization check failed: {error_message}")
        # Create a status dictionary representing the error
        error_status = {
            'spacy_models': [], 'benepar_models': [], 'nltk_present': False,
            'error': error_message
        }
        self.final_init_status = error_status
        self.showMessage(f"Initialization failed: {error_message.split(':')[0]}...") # Show short error
        self._emit_completion(self.final_init_status)

    def _emit_completion(self, status):
        """Emits the final signal and prepares for fade-out (but doesn't start it yet)."""
        logging.debug(f"Splash screen emitting initialization_complete with status: {status}")
        self.initialization_complete.emit(status)
        # The fade_out will be triggered externally by the main application logic
        # after the main window is created and shown.
