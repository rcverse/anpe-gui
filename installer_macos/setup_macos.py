#!/usr/bin/env python3
"""
ANPE GUI Setup for macOS

This is the main entry point for the macOS setup wizard.
It manages the installation of Python, dependencies, and models for ANPE GUI.
"""

import sys
import os
import logging
import argparse
import time
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QStackedWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QThread, QProcess

# --- Add project root to sys.path --- 
# This allows importing main_macos when run as python -m installer.setup_macos
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Import macOS-specific views
from installer_macos.views.welcome_view_macos import WelcomeViewWidget
from installer_macos.views.progress_view_macos import ProgressViewWidget
from installer_macos.views.completion_view_macos import CompletionViewWidget

# Import workers with their correct class names
from installer_macos.workers.env_setup_worker_macos import EnvironmentSetupWorkerMacOS as SetupEnvironmentWorker
from installer_macos.workers.model_setup_worker_macos import ModelSetupWorkerMacOS as DownloadModelsWorker

# Import the macOS-specific resource finder
from installer_macos.installer_core_macos import _get_bundled_resource_path_macos, find_standalone_python_executable_macos

# Helper to find the main script within the bundle
# from main_macos import _get_main_script_path_macos

def setup_logging():
    """
    Set up logging for the macOS installer.
    Creates log file in the user's Library/Logs directory.
    Returns the logger instance.
    """
    # Create log directory in user's Library/Logs
    log_dir = Path.home() / "Library" / "Logs" / "ANPE GUI"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Use timestamp for unique log file name
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"setup_log_{timestamp}.txt"
    
    # Determine logging level from environment variable
    log_level = logging.DEBUG if os.environ.get("ANPE_VERBOSE") == "1" else logging.INFO
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger()
    logger.info(f"Logging initialized. Log file: {log_file}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    
    return logger

# Configure logging
logger = setup_logging()

class SetupWizard:
    """Main setup wizard controller for macOS."""
    
    def __init__(self, debug_mode=False, target_install_dir=None):
        """Initialize the setup wizard."""
        self.app = QApplication(sys.argv)
        self.stacked_widget = QStackedWidget()
        self.debug_mode = debug_mode
        self.target_install_dir = target_install_dir
        
        # Set the application icon using the installer's own icon file
        icon_path_obj = _get_bundled_resource_path_macos("app_icon_mac.icns") # Use installer asset icon
        if icon_path_obj and icon_path_obj.is_file():
            self.app.setWindowIcon(QIcon(str(icon_path_obj)))
            logger.info(f"Loaded application icon from: {icon_path_obj}")
        else:
            logger.warning(f"Application icon 'app_icon_mac.icns' not found.")
            
        if not self.target_install_dir:
            logger.critical("SetupWizard initialized without a target installation directory!")
            # Maybe show an immediate error and exit?
            # For now, let the later check handle it, but log critical error.
            
        # Initialize views
        self._setup_views()
        
        # Configure window
        self.stacked_widget.setWindowTitle("ANPE GUI First Run Setup")
        self.stacked_widget.setFixedSize(700, 600)
        self.stacked_widget.show()
        
        self.env_worker = None
        self.env_thread = None
        self.model_worker = None
        self.model_thread = None
        self._python_exe_path_for_launch = None # Store python path for launch
    
    def _setup_views(self):
        """Set up the views for the wizard."""
        # Welcome view
        self.welcome_view = WelcomeViewWidget()
        self.welcome_view.setup_requested.connect(self._on_setup_requested)
        self.welcome_view.cancel_requested.connect(self._on_welcome_cancel)
        self.stacked_widget.addWidget(self.welcome_view)
        
        # Set custom welcome text if in debug mode
        if self.debug_mode:
            self.welcome_view.set_welcome_text(
                "ANPE Setup (Debug Mode)",
                "Running in debug mode. The application will be installed in a local directory."
            )
    
    def _on_setup_requested(self, install_path_from_ui):
        """Handle the setup request from the welcome view."""
        logger.info("Setup request received.")

        # Use the target path passed during initialization
        final_install_path = self.target_install_dir

        if not final_install_path:
             logger.critical("Installation path was not provided to the Setup Wizard.")
             self._on_setup_failed("Internal Error: Installation path could not be determined.")
             return

        logger.info(f"Proceeding with setup in target directory: {final_install_path}")

        # --- Start Environment Setup --- 
        self.env_progress_view = ProgressViewWidget("Setting up Python Environment")
        self.stacked_widget.addWidget(self.env_progress_view)
        self.stacked_widget.setCurrentWidget(self.env_progress_view)

        # Create worker and thread
        self.env_worker = SetupEnvironmentWorker(final_install_path)
        self.env_thread = QThread()
        self.env_worker.moveToThread(self.env_thread)

        # Connect worker signals (Ensure update_task_status slot accepts text)
        # Note: Env worker currently doesn't send text, handle in progress_view slot
        self.env_worker.task_status_update.connect(self.env_progress_view.update_task_status) 
        self.env_worker.status_update.connect(self.env_progress_view.handle_status_update)
        self.env_worker.log_update.connect(self.env_progress_view.handle_log_update)
        logger.info("Connected env_worker log_update signal") # Log connection
        self.env_worker.progress_range.connect(self.env_progress_view.set_progress_range)
        self.env_worker.progress_update.connect(self.env_progress_view.set_progress_value)
        self.env_worker.finished.connect(self._on_env_setup_complete)
        self.env_worker.setup_failed.connect(self._on_setup_failed)
        self.env_progress_view.cancel_button.clicked.connect(self._cancel_setup) # Connect cancel
        
        # Move worker to thread and start
        self.env_thread.started.connect(self.env_worker.run)

        # Setup tasks in the view (using worker instance directly)
        self.env_progress_view.setup_tasks_from_worker(self.env_worker)

        # Start the thread (which will start the worker's run method)
        self.env_thread.start()
        logger.info("Environment setup worker thread started.")
    
    def _on_env_setup_complete(self, success: bool, error_message: str, python_exe_path: str):
        """Handle the completion of environment setup. Runs in the main thread."""
        logger.info("Received env_worker finished signal.")
        if not success:
            self._on_setup_failed(error_message or "Environment setup failed.")
            return

        if not python_exe_path:
            self._on_setup_failed("Environment setup succeeded, but Python executable path was not found.")
            return

        logger.info(f"Environment setup complete. Python executable: {python_exe_path}")
        # Store the path for the final launch
        self._python_exe_path_for_launch = python_exe_path

        # --- Clean up environment thread ---
        if self.env_thread:
            logger.debug("Quitting and waiting for environment setup thread...")
            self.env_thread.quit()
            if not self.env_thread.wait(3000): # Wait up to 3 seconds
                 logger.warning("Environment thread did not quit gracefully.")
            # Optionally delete later: self.env_thread.deleteLater(); self.env_worker.deleteLater()
            self.env_thread = None # Clear references
            self.env_worker = None

        # --- Start Model Setup --- 
        self.model_progress_view = ProgressViewWidget("Installing Language Models")
        self.stacked_widget.addWidget(self.model_progress_view)
        self.stacked_widget.setCurrentWidget(self.model_progress_view)

        # Create worker and thread
        self.model_worker = DownloadModelsWorker(python_exe_path)
        self.model_thread = QThread()
        self.model_worker.moveToThread(self.model_thread)

        # Connect worker signals (Model worker sends text)
        self.model_worker.task_status_update.connect(self.model_progress_view.update_task_status) # Connect updated signal
        self.model_worker.status_update.connect(self.model_progress_view.handle_status_update)
        self.model_worker.log_update.connect(self.model_progress_view.handle_log_update)
        logger.info("Connected model_worker log_update signal") # Log connection
        self.model_worker.progress_range.connect(self.model_progress_view.set_progress_range)
        self.model_worker.progress_update.connect(self.model_progress_view.set_progress_value)
        self.model_worker.finished.connect(self._on_model_setup_complete)
        self.model_worker.setup_failed.connect(self._on_setup_failed)
        # Re-connect cancel button in case the first worker finished very quickly
        try:
            self.model_progress_view.cancel_button.clicked.disconnect(self._cancel_setup)
        except TypeError:
            pass # Ignore if not connected
        self.model_progress_view.cancel_button.clicked.connect(self._cancel_setup)

        # Move worker to thread and start
        self.model_thread.started.connect(self.model_worker.run)

        # Setup tasks in the view
        self.model_progress_view.setup_tasks_from_worker(self.model_worker)

        # Start the thread
        self.model_thread.start()
        logger.info("Model setup worker thread started.")
    
    def _on_model_setup_complete(self, success: bool, error_message: str):
        """Handle the completion of model setup. Runs in the main thread."""
        logger.info(f"_on_model_setup_complete received: success={success}, error='{error_message}'")
        if not success:
            self._on_setup_failed(error_message or "Model setup failed.")
            return

        logger.info("Model setup reported success.")
        # On overall success, create the flag file in the *target* directory
        # This assumes the target_install_dir is the root where 'python-standalone' lives
        try:
            logger.debug("Attempting to create setup complete flag...")
            flag_path = Path(self.target_install_dir) / ".setup_complete"
            flag_path.touch()
            logger.info(f"Created setup complete flag: {flag_path}")
        except Exception as e:
             logger.error(f"Failed to create setup complete flag: {e}")
             # Proceed to show completion, but log error
             self._show_completion(success=False, error_log=f"Setup tasks finished, but failed to create completion flag: {e}")
             return

        # --- Move thread cleanup *before* showing completion view ---
        logger.debug("Starting model thread cleanup...")
        if self.model_thread:
            logger.debug("Quitting and waiting for model setup thread...")
            self.model_thread.quit()
            if not self.model_thread.wait(3000):
                logger.warning("Model thread did not quit gracefully.")
            # Optionally delete later: self.model_thread.deleteLater(); self.model_worker.deleteLater()
            self.model_thread = None # Clear references
            self.model_worker = None
            logger.debug("Model thread cleanup finished.")
        else:
            logger.debug("Model thread already cleaned up.")
        # --------------------------------------------------------

        logger.info("Proceeding to show successful completion view...")
        self._show_completion(success=True)

    def _on_setup_failed(self, error_log):
        """Handle setup failure."""
        logger.error(f"_on_setup_failed called with error: {error_log}")
        # Ensure threads are stopped on failure too
        logger.debug("Stopping threads due to setup failure...")
        self._stop_threads()
        logger.debug("Proceeding to show failed completion view...")
        self._show_completion(success=False, error_log=error_log)

    def _cancel_setup(self):
        """Handle user clicking the Cancel button."""
        logger.warning("Setup cancellation requested by user.")
        self._stop_threads()
        self._show_completion(success=False, error_log="Setup was cancelled by the user.")
        # Alternatively, could quit directly: self.app.quit()

    def _stop_threads(self):
        """Attempt to stop any running worker threads."""
        if self.env_thread and self.env_thread.isRunning():
            logger.info("Attempting to stop environment setup thread...")
            # Request the worker to stop its QProcess if applicable
            if self.env_worker and hasattr(self.env_worker, 'request_stop'):
                self.env_worker.request_stop()
            self.env_thread.requestInterruption() # Request interruption
            self.env_thread.quit()
            self.env_thread.wait(1000) # Wait a bit for clean exit
            if self.env_thread.isRunning():
                logger.warning("Environment thread did not stop gracefully, terminating.")
                self.env_thread.terminate()
                self.env_thread.wait()
            logger.info("Environment setup thread stopped.")
        
        if self.model_thread and self.model_thread.isRunning():
            logger.info("Attempting to stop model setup thread...")
            # Request the worker to stop its QProcess if applicable
            if self.model_worker and hasattr(self.model_worker, 'request_stop'):
                self.model_worker.request_stop()
            self.model_thread.requestInterruption()
            self.model_thread.quit()
            self.model_thread.wait(1000)
            if self.model_thread.isRunning():
                logger.warning("Model thread did not stop gracefully, terminating.")
                self.model_thread.terminate()
                self.model_thread.wait()
            logger.info("Model setup thread stopped.")

    def _show_completion(self, success=True, error_log=""):
        """Show the completion view."""
        logger.info(f"_show_completion called: success={success}")
        # Create completion view only when needed
        try:
            logger.debug("Creating CompletionViewWidget...")
            self.completion_view = CompletionViewWidget()
            logger.debug("Connecting launch_requested signal...")
            self.completion_view.launch_requested.connect(self._on_launch_requested)
        except Exception as e:
            logger.exception("CRITICAL: Failed to instantiate or connect CompletionViewWidget!")
            # Can't show completion view, maybe just quit?
            self.app.quit()
            return

        # Safely read log content
        log_content = "Failed to read setup log."
        try:
            logger.debug("Reading log file for completion view...")
            if logger.handlers and isinstance(logger.handlers[0], logging.FileHandler):
                log_file_path = logger.handlers[0].baseFilename
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                logger.debug(f"Successfully read log file: {log_file_path}")
            else:
                logger.warning("Could not find FileHandler to read log file.")
                log_content = "Log handler not found."
        except Exception as e:
            logger.exception("Failed to read log file for completion view.")
            log_content = f"Error reading log file: {e}"

        try:
            logger.debug("Setting completion view success state...")
            self.completion_view.set_success_state(success, log_content=log_content, error_message=error_log)
        except Exception as e:
             logger.exception("CRITICAL: Failed to set state on CompletionViewWidget!")
             # Can't show completion view, maybe just quit?
             self.app.quit()
             return

        logger.debug("Adding completion view to stacked widget...")
        self.stacked_widget.addWidget(self.completion_view)
        logger.debug("Setting completion view as current widget...")
        self.stacked_widget.setCurrentWidget(self.completion_view)
        logger.info("Completion view displayed.")

    def _on_launch_requested(self, success: bool):
        """Handle the signal from the completion view's final button."""
        if success:
            logger.info("Launch requested after successful setup.")
            python_exe = self._python_exe_path_for_launch
            
            # --- Import main_macos here ---
            try:
                import main_macos
                main_script = main_macos._get_main_script_path_macos()
            except ImportError as e:
                 logger.error(f"Failed to import main_macos module: {e}")
                 self.stacked_widget.close()
                 return
            except AttributeError as e:
                 logger.error(f"Failed to find _get_main_script_path_macos in main_macos: {e}")
                 self.stacked_widget.close()
                 return
            # ---------------------------
            
            if not python_exe:
                logger.error("Cannot launch: Python executable path is missing.")
                # Show error message? For now, just close.
                self.stacked_widget.close()
                return
            if not main_script:
                logger.error("Cannot launch: Main application script path is missing.")
                self.stacked_widget.close()
                return

            logger.info(f"Attempting to launch: {python_exe} {main_script}")
            # Use QProcess.startDetached to launch independently
            started = QProcess.startDetached(python_exe, [main_script])
            
            if not started:
                logger.error("Failed to start the main application process.")
                # Optionally show a message box here
                # QMessageBox.critical(self.stacked_widget, "Launch Error", "Could not launch ANPE GUI.")
            else:
                logger.info("Main application process launched successfully.")
                
            # Close the wizard regardless of launch success/failure after attempt
            self.stacked_widget.close()
        else:
            logger.info("Close requested after failed/cancelled setup.")
            self.stacked_widget.close()

    def _on_welcome_cancel(self):
        """Handle the cancel request from the welcome view."""
        logger.info("Cancel requested from Welcome View. Closing wizard.")
        self.stacked_widget.close()

    def run(self):
        """Run the application."""
        return self.app.exec()


def main(target_install_dir: str | None = None, debug: bool | None = None):
    """Main entry point for the setup application.
    
    Can be called directly with arguments or run standalone using argparse.
    """
    # Determine if args were passed directly or need parsing
    if target_install_dir is None or debug is None:
        # Parse command line arguments if not called directly with values
        parser = argparse.ArgumentParser(description="ANPE GUI Setup for macOS")
        parser.add_argument('--debug', action='store_true', help='Run in debug mode')
        parser.add_argument('--target-install-dir', type=str, required=target_install_dir is None,
                            help='The target base directory for installation')
        args = parser.parse_args()
        
        # Use parsed args if direct args were missing
        final_target_dir = target_install_dir if target_install_dir is not None else args.target_install_dir
        final_debug_mode = debug if debug is not None else args.debug
    else:
        # Use directly passed arguments
        final_target_dir = target_install_dir
        final_debug_mode = debug

    # Log the provided target directory
    logger.info(f"Setup starting. Target directory: {final_target_dir}, Debug mode: {final_debug_mode}")
    
    # Create and run the setup wizard
    wizard = SetupWizard(debug_mode=final_debug_mode, target_install_dir=final_target_dir)
    return wizard.run()


if __name__ == "__main__":
    # When run as script, main() will use argparse internally
    sys.exit(main())
