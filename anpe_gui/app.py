#!/usr/bin/env python3
"""
Main entry point for the ANPE GUI application.
"""

import sys
import os
from pathlib import Path
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, pyqtSlot, QObject, Qt # Added Qt
from PyQt6.QtGui import QFont # Original import
from anpe_gui.main_window import MainWindow
# from anpe_gui.splash_screen import SplashScreen # Original
from anpe_gui.splash_screen_alt import AltSplashScreen # USE THE ALTERNATIVE SPLASH
from anpe_gui.theme import apply_theme
from anpe_gui.resource_manager import ResourceManager


# Variable to hold the main window instance
main_window_instance = None

def main():
    """Launch the main application."""
    global main_window_instance # Allow modification of the global variable
    
    # Configure High-DPI scaling via environment variables
    # These must be set before QApplication is created
    # Note: In PyQt6, high-DPI scaling is enabled by default
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    # QT_SCALE_FACTOR can be used to manually set scaling if needed 
    # os.environ["QT_SCALE_FACTOR"] = "1.5" # Only enable if needed
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("ANPE GUI")
    app.setOrganizationName("ANPE")
    
    # REMOVED: Initialize resource manager (no longer needed)
    # ResourceManager.initialize()
    
    # Adjust default font slightly based on screen DPI
    screen = app.primaryScreen()
    if screen:
        dpi = screen.logicalDotsPerInch()
        default_font = app.font()
        
        # On high-DPI screens, adjust the font size to be more readable
        if dpi > 120:  # Regular screens are typically 96-108 DPI; 4K screens are usually 150+ DPI
            dpi_scale_factor = min(dpi / 96.0, 1.5)  # Don't scale larger than 1.5x
            font_size_pt = max(9, round(9 * dpi_scale_factor))
            default_font.setPointSize(font_size_pt)
            app.setFont(default_font)
            print(f"Adjusted font size for high-DPI display: {font_size_pt}pt (DPI: {dpi})")
    
    apply_theme(app)

    # --- SplashScreen Setup & Initialization --- 
    # splash = SplashScreen() # Original
    splash = AltSplashScreen() # Use the new alternative splash screen
    
    # --- Slot to handle completion of splash screen initialization --- 
    @pyqtSlot(object) # Decorator to mark as a slot accepting an object (the status dict)
    def on_initialization_complete(status_dict):
        """Creates and shows the main window after splash initialization is done."""
        global main_window_instance
        logging.info(f"APP: SplashScreen initialization complete. Status: {status_dict}")
        
        if main_window_instance is None:
            print("APP: Creating MainWindow instance...")
            main_window_instance = MainWindow(model_status=status_dict)
            print("APP: MainWindow instance created.")
        
        if main_window_instance:
            print("APP: Fading in MainWindow...")
            main_window_instance.fade_in()
        
        # Fade out splash screen AFTER main window is potentially shown
        print("APP: Fading out SplashScreen...")
        splash.fade_out()

    # --- Connect Splash Signal --- 
    splash.initialization_complete.connect(on_initialization_complete)
    print("APP: Connected splash initialization_complete signal.")

    # --- Show the splash screen BEFORE starting initialization ---
    splash.fade_in()

    # --- Start Splash Initialization (this runs the background check) --- 
    splash.start_initialization()
    print("APP: Splash initialization started (includes fade-in).")

    # --- Start Event Loop --- 
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 