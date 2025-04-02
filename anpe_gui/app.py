#!/usr/bin/env python3
"""
Main entry point for the ANPE GUI application.
"""

import sys
from PyQt6.QtWidgets import QApplication
from anpe_gui.main_window import MainWindow
from anpe_gui.splash_screen import SplashScreen
from anpe_gui.theme import apply_theme

def main():
    """Launch the main application."""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("ANPE GUI")
    app.setOrganizationName("ANPE")
    
    # Apply the theme
    apply_theme(app)
    
    # Show splash screen
    splash = SplashScreen()
    
    # Start loading animation and create main window when complete
    def create_main_window():
        window = MainWindow()
        window.show()
        return window
    
    splash.start_loading_animation(app, create_main_window)
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 