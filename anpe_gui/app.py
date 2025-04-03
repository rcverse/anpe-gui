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
    app = QApplication(sys.argv)
    app.setApplicationName("ANPE GUI")
    app.setOrganizationName("ANPE")
    
    # apply_theme(app) # Keep styles disabled for now during debugging

    # --- Keep main_window reference initially None --- 
    main_window = None 

    # --- SplashScreen Setup ---
    splash = SplashScreen()

    # --- Slot to Create/Show MainWindow --- 
    def show_main_window_and_close_splash():
        nonlocal main_window 
        if main_window is None: # Create only if it doesn't exist
            print("APP: Creating MainWindow instance...")
            main_window = MainWindow()
            print("APP: MainWindow instance created.")
            # print("APP: Initializing extractor...") # Defer extractor init
            # main_window.initialize_extractor() 
            # print("APP: Extractor initialized.")

        if main_window:
            main_window.show()
            
        if splash:
            splash.close()

    # --- Connect Signal --- 
    splash.loading_finished.connect(show_main_window_and_close_splash)

    # --- Start Splash --- 
    splash.start_loading_animation(app)

    # --- Start Event Loop --- 
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 