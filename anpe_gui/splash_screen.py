"""
Splash screen for the ANPE GUI application.
"""

import os
import time
from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer


class SplashScreen(QSplashScreen):
    """
    Custom splash screen with loading animation for the ANPE GUI application.
    """
    
    def __init__(self, banner_path=None):
        """
        Initialize the splash screen.
        
        Args:
            banner_path: Path to the banner image. If None, tries to locate it automatically.
        """
        # Find the banner image
        if banner_path is None:
            # Try to locate the banner in standard locations
            possible_paths = [
                "pics/banner.png",  # From project root
                "../pics/banner.png",  # One level up
                "../../pics/banner.png",  # Two levels up
                os.path.join(os.path.dirname(__file__), "../pics/banner.png"),  # Relative to this file
                os.path.join(os.path.dirname(__file__), "../../pics/banner.png"),  # Relative to this file
                "c:/Users/b162274/Desktop/ANPE_public/pics/banner.png"  # Absolute path (if known)
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    banner_path = path
                    break
        
        # Use the banner or create a blank pixmap if not found
        if banner_path and os.path.exists(banner_path):
            pixmap = QPixmap(banner_path)
        else:
            # Create a fallback banner if image not found
            pixmap = QPixmap(600, 200)
            pixmap.fill(QColor("#1a5276"))  # Fill with primary color
            
            # Create a painter to add text
            painter = QPainter(pixmap)
            painter.setPen(QColor("white"))
            font = QFont("Arial", 24, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "ANPE\nAnother Noun Phrase Extractor")
            painter.end()
        
        super().__init__(pixmap)
        
        # Initialization properties
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | 
                           Qt.WindowType.FramelessWindowHint)
        self.loading_progress = 0
        self.loading_steps = ["Loading UI...", 
                             "Initializing extractors...", 
                             "Setting up components...", 
                             "Starting application..."]
        self.current_step = 0
        
        # Center the splash screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())
    
    def drawContents(self, painter):
        """
        Draw the splash screen contents.
        
        Args:
            painter: QPainter to use for drawing
        """
        # Draw the base pixmap
        super().drawContents(painter)
        
        # Draw loading progress
        message = self.loading_steps[min(self.current_step, len(self.loading_steps) - 1)]
        
        # Draw loading bar background
        bar_width = self.width() - 40
        bar_height = 20
        bar_x = 20
        bar_y = self.height() - 40
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 50))  # Translucent black
        painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, 5, 5)
        
        # Draw loading bar progress
        progress_width = int(bar_width * (self.loading_progress / 100))
        painter.setBrush(QColor("#3498db"))  # Accent color
        painter.drawRoundedRect(bar_x, bar_y, progress_width, bar_height, 5, 5)
        
        # Draw loading text
        painter.setPen(QColor("white"))
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(bar_x, bar_y - 10, message)
        painter.drawText(bar_x + bar_width - 40, bar_y + bar_height + 15, 
                        f"{self.loading_progress}%")
    
    def start_loading_animation(self, app, main_window_callback):
        """
        Start the loading animation, then show the main window when complete.
        
        Args:
            app: QApplication instance
            main_window_callback: Function to create and show the main window
        """
        self.show()
        app.processEvents()
        
        # Define animation update function
        def update_progress():
            # Update progress
            if self.loading_progress < 100:
                step_increment = 100 / len(self.loading_steps)
                
                # Advance to next step if needed
                if self.loading_progress >= (self.current_step + 1) * step_increment:
                    self.current_step += 1
                
                # Regular increment
                self.loading_progress += 1
                self.repaint()
                app.processEvents()
                
                # Continue timer
                QTimer.singleShot(30, update_progress)
            else:
                # Open main window when loading completes
                self.finish(main_window_callback())
        
        # Start the progress updates
        QTimer.singleShot(200, update_progress)
        
        return self 