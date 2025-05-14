"""
Alternative Splash screen for the ANPE Studio application, featuring a centered
activity indicator behind a transparent logo.
"""

import os
import time
import logging
from PyQt6.QtWidgets import (QWidget, QApplication, QLabel, QVBoxLayout, 
                             QHBoxLayout, QFrame, QSizePolicy, QStackedLayout, QProgressBar) # Added QProgressBar
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QRegion, QPainterPath, QPen
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QCoreApplication, QPropertyAnimation, QEasingCurve, QPoint, QRect, QSize, QObject, pyqtSlot, QRectF, pyqtProperty, QThread # Added QThread
from PyQt6.QtSvg import QSvgRenderer # Added for SVG rendering

# Import necessary components from the project
from anpe_studio.widgets.activity_indicator import PulsingActivityIndicator, STATE_IDLE, STATE_ACTIVE, STATE_CHECKING, STATE_ERROR, STATE_WARNING, STATE_LOADING # Added STATE_LOADING
from anpe_studio.theme import PRIMARY_COLOR, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR, DISABLED_COLOR # Changed LIGHT_GREY to DISABLED_COLOR
from anpe_studio.version import __version__ as gui_version
from anpe_studio.workers.status_worker import ModelStatusChecker
from anpe_studio.resource_manager import ResourceManager

# Attempt to import ANPE core version (still needed for display)
try:
    from anpe import __version__ as core_version
except ImportError:
    core_version = "N/A"


class SplashScreen(QWidget): # Changed from QSplashScreen to QWidget for custom layout
    """
    Alternative splash screen with a large activity indicator behind the logo
    and a separate status message area below.
    """
    initialization_complete = pyqtSignal(object)
    fade_out_complete = pyqtSignal()

    # Define sizes
    INDICATOR_SIZE = 300 # Size of the pulsing indicator background
    LOGO_SIZE = 280    # Logical size of the logo overlay
    PILLAR_HEIGHT = 40 # New fixed height for capsule shape
    PILLAR_MAX_WIDTH_FACTOR = 0.8 # Pillar width relative to indicator
    
    # Progress animation constants
    PROGRESS_STEP_DURATION = 400  # Duration of animation between steps in ms
    
    # Define initialization steps that correspond to progress percentages
    PROGRESS_STEPS = {
        'start': 0,           # Starting point
        'check_models': 20,   # Checking if models exist
        'spacy_model': 50,    # Loading spaCy model
        'benepar_model': 80,  # Loading benepar model
        'complete': 100       # All done
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Window Setup ---
        self.setWindowFlags(Qt.WindowType.SplashScreen | # Use SplashScreen flag for behavior
                           Qt.WindowType.WindowStaysOnTopHint |
                           Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # Allow transparency
        self.setStyleSheet("background-color: transparent;") # Ensure widget background is clear

        # Overall layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Top Area (Indicator + Logo) ---
        self.top_container = QWidget()
        self.top_container.setFixedSize(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        self.top_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        self.stacked_layout = QStackedLayout(self.top_container)
        self.stacked_layout.setContentsMargins(0,0,0,0)
        self.stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll) # Overlay items

        # Activity Indicator (Background)
        self.activity_indicator = PulsingActivityIndicator()
        self.activity_indicator.setFixedSize(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        self.stacked_layout.addWidget(self.activity_indicator)

        # Logo Label (Foreground)
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Load and set the PNG logo pixmap
        self._load_and_set_logo()
        self.stacked_layout.addWidget(self.logo_label)

        # Progress Bar (Moved out of stack)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8) # Thin progress bar
        self.progress_bar.setTextVisible(False) # Hide percentage text
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        # Set max width - slightly shorter than full width
        self.progress_bar.setMaximumWidth(self.INDICATOR_SIZE + 5)
        # Policy: Expanding horizontally, fixed height
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress_bar.setObjectName("SplashScreenProgressBar") # Assign object name
        
        # Explicitly set the logo label as the current widget to ensure it's on top
        self.stacked_layout.setCurrentWidget(self.logo_label)

        # --- Assemble Main Layout ---
        # Center the top container horizontally
        h_layout_top = QHBoxLayout()
        h_layout_top.addStretch()
        h_layout_top.addWidget(self.top_container)
        h_layout_top.addStretch()

        # Progress bar layout (stretches removed)
        h_layout_progress = QHBoxLayout()
        h_layout_progress.addWidget(self.progress_bar)

        self.main_layout.addLayout(h_layout_top)
        self.main_layout.addLayout(h_layout_progress)
        self.main_layout.addSpacing(10) # Add some padding below the progress bar

        # Calculate new height based on top container, progress bar, and spacing
        progress_bar_height = self.progress_bar.height()
        spacing_above_progress = 0
        spacing_below_progress = 10
        total_height = self.INDICATOR_SIZE + spacing_above_progress + progress_bar_height + spacing_below_progress + 5 # Added extra 5 padding at top maybe?

        self.setFixedSize(self.INDICATOR_SIZE + 40, total_height) # Wider padding

        # --- Initialization State (Copied from original) ---
        self.init_thread = None
        self.init_worker = None
        self.final_init_status = None
        self.activity_indicator.checking() # Start in checking state

        # --- Animation Setup (Copied from original for fade) ---
        self._fade_animation = None
        # --- Animation Setup for Progress Bar ---
        self._progress_animation = None
        self._current_progress = 0

        self.setWindowOpacity(0.0)

        # Center the splash screen
        self._center_on_screen()

    def _load_and_set_logo(self):
        """Loads the PNG logo and sets it on the label, handling HiDPI."""
        try:
            # Use the standard PNG icon
            logo_pixmap = ResourceManager.get_pixmap("app_icon_logo_transparent.png")
            if logo_pixmap.isNull():
                 logging.error("Failed to load app_icon_logo_transparent.png")
                 return

            # Determine device pixel ratio for high-DPI rendering
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else QApplication.primaryScreen().devicePixelRatio()
            
            # Create a properly scaled pixmap if DPR > 1
            if dpr > 1.0:
                physical_logo_size = int(self.LOGO_SIZE * dpr)
                # Scale the loaded pixmap smoothly to the target physical size
                # Use scaled() which returns a new pixmap
                scaled_pixmap = logo_pixmap.scaled(physical_logo_size, physical_logo_size, 
                                                 Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                # Set DPR on the *new* scaled pixmap
                scaled_pixmap.setDevicePixelRatio(dpr)
                final_pixmap = scaled_pixmap
            else:
                # For standard DPI, just use the original pixmap
                final_pixmap = logo_pixmap 
                # Ensure DPR is set even for 1.0 for consistency if needed, though usually implicit
                final_pixmap.setDevicePixelRatio(1.0)

            # Set the prepared pixmap on the label
            self.logo_label.setPixmap(final_pixmap)
            self.logo_label.setFixedSize(self.LOGO_SIZE, self.LOGO_SIZE)
            self.logo_label.setScaledContents(True)
            # Add a left margin to shift the logo visually to the right
            self.logo_label.setContentsMargins(15, 0, 0, 0) # 10px left margin

        except Exception as e:
            logging.error(f"Error loading/setting PNG logo: {e}", exc_info=True)

    def _center_on_screen(self):
        """Center the splash screen on the primary display."""
        if QApplication.primaryScreen():
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.center() - self.rect().center())
        else:
             logging.warning("Could not get primary screen geometry to center splash.")
             # Fallback: center based on available screens? Or just default position.
             pass

    # --- Fade Animations (Copied & Adapted) ---
    def _fade(self, start_value, end_value, duration, on_finish=None):
        """Helper function to create and run fade animation."""
        if self._fade_animation and self._fade_animation.state() == QPropertyAnimation.State.Running:
            self._fade_animation.stop() 

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self) # Parent 'self'
        self._fade_animation.setDuration(duration)
        self._fade_animation.setStartValue(float(start_value))
        self._fade_animation.setEndValue(float(end_value))
        self._fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Ensure previous connections are cleared before connecting new ones
        try:
            self._fade_animation.finished.disconnect()
        except TypeError:
            pass # No connection existed

        if on_finish:
            self._fade_animation.finished.connect(on_finish)
            # Ensure cleanup happens *after* fade finishes
            self._fade_animation.finished.connect(self._cleanup_animation) 

        self._fade_animation.start()

    @pyqtSlot()
    def _cleanup_animation(self):
        # Disconnect the cleanup itself to prevent multiple calls if restarted
        try:
            self._fade_animation.finished.disconnect(self._cleanup_animation)
        except TypeError:
            pass 
        # print("Fade animation finished, cleaning up.") # Debug
        # self._fade_animation = None # Don't nullify immediately, state check might be needed

    def fade_in(self, duration=300):
        """Fade the splash screen in."""
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_() # Try explicitly raising the window
        self.activateWindow() # Try explicitly activating the window
        self._fade(0.0, 1.0, duration)

    def fade_out(self, duration=300):
        """Fade the splash screen out."""
        current_opacity = self.windowOpacity
        self._fade(current_opacity, 0.0, duration, self._on_fade_out_complete)

    @pyqtSlot()
    def _on_fade_out_complete(self):
        """Called when the fade-out animation finishes."""
        logging.debug("Splash fade out complete.")
        self.fade_out_complete.emit()
        self.close() # Close the widget

    # --- Progress Bar Animation ---
    def update_progress(self, step_name):
        """Update progress bar to a specific step."""
        if step_name in self.PROGRESS_STEPS:
            target_value = self.PROGRESS_STEPS[step_name]
            self._animate_progress_to(target_value)
            logging.debug(f"Splash: Progress updated to step '{step_name}' ({target_value}%)")
        else:
            logging.warning(f"Unknown progress step: {step_name}")

    def _animate_progress_to(self, target_value):
        """Animate the progress bar to a specific value."""
        if self._progress_animation and self._progress_animation.state() == QPropertyAnimation.State.Running:
            self._progress_animation.stop()
        
        current_value = self.progress_bar.value()
        if current_value == target_value:
            return  # No need to animate
            
        # Create the animation with a shorter duration
        self._progress_animation = QPropertyAnimation(self.progress_bar, b"value", self)
        self._progress_animation.setDuration(self.PROGRESS_STEP_DURATION)
        self._progress_animation.setStartValue(current_value)
        self._progress_animation.setEndValue(target_value)
        self._progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_animation.start()
        self._current_progress = target_value

    # --- Initialization Logic (Copied & Adapted) ---
    def start_initialization(self):
        """Start the background model check using ModelStatusChecker."""
        self.activity_indicator.loading()  # USE NEW LOADING STATE
        self.progress_bar.setValue(0)  # Reset progress bar value
        self.update_progress('start')  # Start at 0%

        logging.info("Splash: Starting background initialization check...")
        QCoreApplication.processEvents()

        if self.init_thread and self.init_thread.isRunning():
            logging.warning("Splash: Initialization thread already running.")
            return

        try:
            self.init_worker = ModelStatusChecker()
        except Exception as e:
            logging.error(f"Splash: Failed to create ModelStatusChecker: {e}", exc_info=True)
            self._emit_completion({'error': f"Failed to start check: {e}"})
            return

        self.init_thread = QThread(self)
        self.init_worker.moveToThread(self.init_thread)

        # Connect signals
        self.init_thread.started.connect(self.init_worker.run)
        self.init_worker.status_checked.connect(self._on_init_success)
        self.init_worker.error_occurred.connect(self._on_init_error)
        
        # Connect progress signals if available in ModelStatusChecker
        if hasattr(self.init_worker, 'progress_update'):
            self.init_worker.progress_update.connect(self.update_progress)
        else:
            # If no progress signal is available, simulate progress based on start/finish
            self.init_thread.started.connect(lambda: self.update_progress('check_models'))
            self.init_worker.status_checked.connect(lambda _: self.update_progress('complete'))
            
        self.init_worker.status_checked.connect(self.init_thread.quit)
        self.init_worker.error_occurred.connect(self.init_thread.quit)
        self.init_thread.finished.connect(self.init_worker.deleteLater)
        self.init_thread.finished.connect(self.init_thread.deleteLater)
        self.init_thread.finished.connect(self._clear_init_references)

        self.init_thread.start()

    @pyqtSlot()
    def _clear_init_references(self):
        logging.debug("Splash: Clearing init worker and thread references.")
        self.init_worker = None
        self.init_thread = None

    @pyqtSlot(object)
    def _on_init_success(self, status_dict):
        logging.info(f"Splash: Initialization check successful. Status: {status_dict}")
        self.final_init_status = status_dict
        # Update to complete regardless of previous progress
        self.update_progress('complete')
        self._emit_completion(self.final_init_status)

    @pyqtSlot(str)
    def _on_init_error(self, error_message):
        logging.error(f"Splash: Initialization check failed: {error_message}")
        if self._progress_animation and self._progress_animation.state() == QPropertyAnimation.State.Running:
            self._progress_animation.stop()
        self._set_progress_error_style() # Set error style for progress bar
        # Fill the progress bar to indicate completion (with error)
        self.progress_bar.setValue(100)

        error_status = {'spacy_models': [], 'benepar_models': [], 'error': error_message}
        self.final_init_status = error_status
        self.activity_indicator.error() # Switch to red blink on error
        self._emit_completion(self.final_init_status)

    def _emit_completion(self, status):
        logging.debug(f"Splash emitting initialization_complete with status: {status}")
        self.initialization_complete.emit(status)
        # Fade out is triggered externally by app.py

# --- pyqtProperty for opacity animation ---
    def getWindowOpacity(self):
        return super().windowOpacity()

    def setWindowOpacity(self, opacity):
        super().setWindowOpacity(opacity)

    # Define the property
    windowOpacity = pyqtProperty(float, getWindowOpacity, setWindowOpacity)

    def _set_progress_default_style(self):
        """Sets the default style for the progress bar."""
        radius = self.progress_bar.height() // 2
        self.progress_bar.setStyleSheet(f"""
            QProgressBar#SplashScreenProgressBar {{
                background-color: {DISABLED_COLOR};
                border: none;
                border-radius: {radius}px;
                min-height: 8px;
                max-height: 8px;
            }}
            QProgressBar#SplashScreenProgressBar::chunk {{
                background-color: {PRIMARY_COLOR};
                border-radius: {radius}px;
                margin: 0px;
            }}
        """)

    def _set_progress_error_style(self):
        """Sets the error style for the progress bar."""
        radius = self.progress_bar.height() // 2 # Or use fixed 4px if height is problematic
        self.progress_bar.setStyleSheet(f"""
            QProgressBar#SplashScreenProgressBar {{
                background-color: {DISABLED_COLOR};
                border: none;
                border-radius: {radius}px;
                min-height: 8px;
                max-height: 8px;
            }}
            QProgressBar#SplashScreenProgressBar::chunk {{
                background-color: {ERROR_COLOR};
                border-radius: {radius}px;
                margin: 0px;
            }}
        """)

# --- Example Usage (for testing standalone) ---
if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG) # Enable debug logging for test

    app = QApplication(sys.argv)

    # --- Mock ModelStatusChecker for testing ---
    class MockModelStatusChecker(QObject):
        status_checked = pyqtSignal(object)
        error_occurred = pyqtSignal(str)
        progress_update = pyqtSignal(str)  # Add progress signal for testing
        
        def run(self):
            print("Mock checker running...")
            # Simulate steps with delays
            self.progress_update.emit('start')
            QTimer.singleShot(500, lambda: self.progress_update.emit('check_models'))
            QTimer.singleShot(1000, lambda: self.progress_update.emit('spacy_model'))
            QTimer.singleShot(1500, lambda: self.progress_update.emit('benepar_model'))
            QTimer.singleShot(2000, self._finish_success)  # Success after 2s
            # QTimer.singleShot(2000, self._finish_error)  # Simulate error after 2s
            
        def _finish_success(self):
            print("Mock checker success.")
            self.progress_update.emit('complete')
            self.status_checked.emit({'spacy_models': ['en_core_web_sm'], 'benepar_models': ['benepar_en3'], 'error': None})
            
        def _finish_error(self):
            print("Mock checker error.")
            self.error_occurred.emit("Mock Error: Model not found")
            
    # --- Monkey patch the original checker ---
    original_checker = ModelStatusChecker
    ModelStatusChecker = MockModelStatusChecker 
    # --- End Mocking ---

    splash = SplashScreen()

    # Connect signal to fade out splash after init (for testing)
    def handle_complete(status):
        print(f"Test: Init complete: {status}")
        # QTimer.singleShot(500, splash.fade_out) # REMOVED: Don't fade out automatically

    splash.initialization_complete.connect(handle_complete)
    # splash.fade_out_complete.connect(app.quit) # REMOVED: Don't quit automatically

    splash.fade_in()
    splash.start_initialization()

    # Restore original checker if needed (though app quits here)
    # ModelStatusChecker = original_checker 

    sys.exit(app.exec()) 