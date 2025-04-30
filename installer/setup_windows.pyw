import sys
import subprocess
import os # Added for shortcut/launch paths
import platform # Added for platform-specific checks
import shutil
import winreg  # For Windows registry operations
import logging # Added for logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget, QMessageBox, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QThread, QProcess # Added QThread and QProcess
from PyQt6.QtGui import QPalette, QColor # Added for background
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve # Added for fade-in

# Import views - CHANGED FROM RELATIVE TO ABSOLUTE IMPORTS
from installer.views.welcome_view import WelcomeViewWidget
from installer.views.progress_view import ProgressViewWidget
from installer.views.completion_view import CompletionViewWidget

# Import workers - CHANGED FROM RELATIVE TO ABSOLUTE IMPORTS
from installer.workers.env_setup_worker import EnvironmentSetupWorker # Added
from installer.workers.model_setup_worker import ModelSetupWorker # Added

# Import Custom Title Bar - CHANGED FROM RELATIVE TO ABSOLUTE IMPORTS
from installer.widgets.custom_title_bar import CustomTitleBar

# Import utility - CHANGED FROM RELATIVE TO ABSOLUTE IMPORTS
from installer.utils import get_resource_path

from pyshortcuts import make_shortcut

# Get logger instance (configured in utils.py)
logger = logging.getLogger()

# Constants for view indices (as per design doc)
VIEW_WELCOME = 0
VIEW_ENV_PROGRESS = 1
VIEW_MODEL_PROGRESS = 2
VIEW_COMPLETION = 3

# Define a primary color (using value from anpe_gui.theme)
PRIMARY_COLOR = "#005A9C"
BORDER_RADIUS = 10 # Adjust for desired roundness
BORDER_THICKNESS = 2 # Adjust for desired thickness

class SetupMainWindow(QMainWindow):
    """Main window for the ANPE setup application with custom title bar."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        window_title = "ANPE Setup Wizard"
        self.setWindowTitle(window_title)
        # Fixed size might conflict slightly with exact border/radius look
        # Consider setting minimum size and letting layout manage?
        # CHANGED from setFixedSize to setMinimumSize and increased default height
        # Calculate a reasonable initial/minimum height
        initial_height = 550 # Reduced base height back closer to original
        if hasattr(self, '_title_bar'):
            initial_height += self._title_bar.height()
        else:
            initial_height += 35 # Approx title bar height
        initial_height += (BORDER_THICKNESS * 2)
        self.setMinimumSize(650 + (BORDER_THICKNESS * 2), initial_height)
        # Remove the fixed size setting
        # self.setFixedSize(650 + (BORDER_THICKNESS * 2), 550 + self._title_bar.height() + (BORDER_THICKNESS * 2) if hasattr(self, '_title_bar') else 500 + 35 + (BORDER_THICKNESS * 2))

        # --- Custom Window Frame --- 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # Make window background transparent to see rounded corners
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main container widget (needed for transparency and layout)
        self._main_container = QWidget(self)
        self.setCentralWidget(self._main_container)

        # Layout for the main container
        self._container_layout = QVBoxLayout(self._main_container)
        # Add margins to create space for the border effect
        self._container_layout.setContentsMargins(BORDER_THICKNESS, BORDER_THICKNESS, BORDER_THICKNESS, BORDER_THICKNESS)
        self._container_layout.setSpacing(0)

        # Frame for content (background, border radius)
        self._main_frame = QFrame(self._main_container)
        self._main_frame.setObjectName("MainFrame") # Set object name for styling
        self._container_layout.addWidget(self._main_frame)

        # Layout *inside* the main frame
        self._frame_layout = QVBoxLayout(self._main_frame)
        self._frame_layout.setContentsMargins(0, 0, 0, 0) # Frame handles padding via border
        self._frame_layout.setSpacing(0)

        # Custom Title Bar (Add to frame layout)
        self._title_bar = CustomTitleBar(window_title, self._main_frame)
        self._frame_layout.addWidget(self._title_bar)

        # Content Area (Stacked Widget - Add to frame layout)
        self.stacked_widget = QStackedWidget(self._main_frame)
        self._frame_layout.addWidget(self.stacked_widget)

        # --- Apply Styles --- 
        self.setStyleSheet(f"""
            #MainFrame {{ 
                background-color: white; 
                border: {BORDER_THICKNESS}px solid {PRIMARY_COLOR}; 
                border-radius: {BORDER_RADIUS}px; 
            }}
            /* Ensure child widgets don't draw over the rounded corners */
            /* This might need refinement based on specific widgets used */
            #MainFrame QStackedWidget > QWidget {{ 
                background-color: white; 
                border-radius: 0px; /* Prevent children from having radius */
            }}
            /* Style title bar slightly */
            CustomTitleBar {{ 
                background-color: #f0f0f0; 
                /* Apply top-left/right radius to match main frame */
                border-top-left-radius: {BORDER_RADIUS - BORDER_THICKNESS}px; 
                border-top-right-radius: {BORDER_RADIUS - BORDER_THICKNESS}px; 
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
        """)
        # --- End Styling --- 

        # Connect title bar signals
        self._title_bar.minimize_requested.connect(self.showMinimized)
        self._title_bar.close_requested.connect(self.close)

        # --- End Custom Window Frame Setup --- 

        # Store view instances
        self.welcome_view = None
        self.env_progress_view = None
        self.model_progress_view = None
        self.completion_view = None

        # Store setup parameters
        self._install_path = None
        self._python_exe_path = None

        # Worker and thread management
        self._env_worker = None
        self._env_thread = None
        self._model_worker = None
        self._model_thread = None
        self._is_running = False # Flag to track if setup is in progress
        self._is_env_setup_stage = True  # Track current stage

        self._create_views()
        self.stacked_widget.setCurrentIndex(VIEW_WELCOME) # Show welcome view initially

        # Initialize window opacity to 0 for fade-in
        self.setWindowOpacity(0.0)
        self.show()
        
        # Create and start fade-in animation
        self._fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in_animation.setDuration(500) # 500 ms duration
        self._fade_in_animation.setStartValue(0.0)
        self._fade_in_animation.setEndValue(1.0)
        self._fade_in_animation.setEasingCurve(QEasingCurve.Type.InOutQuad) # Smooth easing
        self._fade_in_animation.start()

    def _print_log_message(self, message: str):
        """Helper slot to print log messages directly to the console."""
        print(f"WORKER LOG: {message}")

    def _create_views(self):
        """Create and add view widgets to the stacked widget."""
        self.welcome_view = WelcomeViewWidget()
        self.stacked_widget.addWidget(self.welcome_view)
        self.welcome_view.setup_requested.connect(self._handle_setup_request)

        # Environment Progress View
        self.env_progress_view = ProgressViewWidget(
            "Creating Environment"
        )
        self.stacked_widget.addWidget(self.env_progress_view)

        # Model Progress View
        self.model_progress_view = ProgressViewWidget(
            "Downloading Models"
        )
        self.stacked_widget.addWidget(self.model_progress_view)

        # Completion View
        logger.debug("About to create CompletionViewWidget instance")
        self.completion_view = CompletionViewWidget()
        logger.debug("CompletionViewWidget instance created")
        self.stacked_widget.addWidget(self.completion_view)
        self.completion_view.shortcut_requested.connect(self._create_shortcut)
        self.completion_view.launch_requested.connect(self._launch_anpe)
        self.completion_view.close_requested.connect(self.close)

    def _handle_setup_request(self, install_path: str):
        """Slot to handle the setup request from the Welcome view."""
        print(f"Main Window received setup request: Path='{install_path}'")
        
        self._install_path = install_path

        # --- Path Validation --- 
        abs_install_path = os.path.abspath(install_path)
        parent_dir = os.path.dirname(abs_install_path)

        # 1. Check if path is empty
        if not install_path.strip():
            QMessageBox.critical(self, "Invalid Path", "The installation path cannot be empty.")
            return

        # 2. Check if parent directory exists or can be created
        if not os.path.isdir(parent_dir):
             try:
                 print(f"Attempting to create parent directory: {parent_dir}")
                 os.makedirs(parent_dir, exist_ok=True)
             except Exception as e:
                 QMessageBox.critical(self, "Invalid Path", f"The installation path's parent directory does not exist and cannot be created:\n{parent_dir}\nError: {e}")
                 return
        
        # 3. Check writability of the target or parent directory
        # Try writing to the target directory first if it exists, else the parent
        write_test_dir = abs_install_path if os.path.isdir(abs_install_path) else parent_dir
        try:
            test_file = os.path.join(write_test_dir, ".installer_permissions_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            QMessageBox.critical(self, "Path Not Writable", f"The installation path is not writable:\n{abs_install_path}\n(Tested in: {write_test_dir})\nError: {e}")
            return
        # --- End Path Validation ---

        # Start Stage 1
        self._start_environment_setup()

    def _start_environment_setup(self):
        """Instantiate and start the EnvironmentSetupWorker in a QThread."""
        print("Starting environment setup thread...")
        self._is_running = True
        self._is_env_setup_stage = True  # Track current stage
        
        # Prepare progress view
        self.env_progress_view.clear_log()
        self.env_progress_view.update_status("Initializing environment setup...")
        self.env_progress_view.set_progress_range(0, 0) # Indeterminate
        self.stacked_widget.setCurrentIndex(VIEW_ENV_PROGRESS)

        # Create worker and thread
        self._env_worker = EnvironmentSetupWorker(self._install_path)
        
        # Set up task list based on worker's tasks
        self.env_progress_view.setup_tasks_from_worker(self._env_worker)
        
        self._env_thread = QThread()
        self._env_worker.moveToThread(self._env_thread)

        # Connect signals
        self._env_worker.log_update.connect(self.env_progress_view.append_log)
        self._env_worker.log_update.connect(self._print_log_message)
        self._env_worker.status_update.connect(self.env_progress_view.update_status)
        self._env_worker.task_status_update.connect(self.env_progress_view.update_task_status)
        self._env_worker.finished.connect(self._environment_setup_finished)
        self._env_thread.started.connect(self._env_worker.run)
        self._env_worker.finished.connect(self._env_thread.quit)
        self._env_worker.finished.connect(self._env_worker.deleteLater)
        self._env_thread.finished.connect(self._env_thread.deleteLater)

        self._env_thread.start()

    def _environment_setup_finished(self, success: bool, python_exe_path: object, error_message: str):
        """Handle completion of the environment setup worker."""
        # Ensure python_exe_path is treated as string or None
        python_exe_path_str = str(python_exe_path) if python_exe_path is not None else None
        
        logger.info(f"Environment setup finished. Success: {success}, Python Path: {python_exe_path_str}, Error: '{error_message}'")
        
        # No longer need these as deleteLater handles cleanup
        # self._env_thread = None 
        # self._env_worker = None 

        if success and python_exe_path_str:
            self._python_exe_path = python_exe_path_str # Store the validated path
            # Start Stage 2: Model Setup
            self._start_model_setup()
        else:
            # Setup failed, show completion view in failure state
            self._is_running = False
            self._is_env_setup_stage = True  # Still in env stage when failed
            # Pass the specific error message to the completion view
            self._show_completion_view(success=False, error_message=error_message)

    def _start_model_setup(self):
        """Instantiate and start the ModelSetupWorker in a QThread."""
        print("Starting model setup thread...")
        self._is_running = True # Still running
        self._is_env_setup_stage = False  # Now in model setup stage
        
        # Prepare progress view
        self.model_progress_view.clear_log()
        self.model_progress_view.update_status("Initializing language model setup...")
        self.model_progress_view.set_progress_range(0, 0) # Indeterminate
        self.stacked_widget.setCurrentIndex(VIEW_MODEL_PROGRESS)

        # Create worker and thread
        self._model_worker = ModelSetupWorker(self._python_exe_path)
        
        # Set up task list based on worker's tasks
        self.model_progress_view.setup_tasks_from_worker(self._model_worker)
        
        self._model_thread = QThread()
        self._model_worker.moveToThread(self._model_thread)

        # Connect signals
        self._model_worker.log_update.connect(self.model_progress_view.append_log)
        self._model_worker.log_update.connect(self._print_log_message)
        self._model_worker.status_update.connect(self.model_progress_view.update_status)
        self._model_worker.task_status_update.connect(self.model_progress_view.update_task_status)
        self._model_worker.finished.connect(self._model_setup_finished)
        self._model_thread.started.connect(self._model_worker.run)
        self._model_worker.finished.connect(self._model_thread.quit)
        self._model_worker.finished.connect(self._model_worker.deleteLater)
        self._model_thread.finished.connect(self._model_thread.deleteLater)

        self._model_thread.start()

    def _model_setup_finished(self, success: bool):
        """Handle completion of the model setup worker."""
        print(f"Model setup finished. Success: {success}")
        # self._model_thread = None # REMOVE: Let deleteLater handle cleanup
        # self._model_worker = None # REMOVE: Let deleteLater handle cleanup
        self._is_running = False # Setup process is now fully complete

        # Show completion view (success or failure)
        self._show_completion_view(success=success)

    def _show_completion_view(self, success: bool, error_message: str = None):
        """Switch to the completion view and set its state."""
        # Collect logs from the appropriate progress view
        log_content = ""
        if hasattr(self, '_is_env_setup_stage') and self._is_env_setup_stage:
            # Environment setup logs
            log_content = self.env_progress_view._log_area.toPlainText()
        else:
            # Model setup logs (default to this if we can't determine stage)
            log_content = self.model_progress_view._log_area.toPlainText()
            
        # --- DEBUGGING PRINT ---
        logger.debug("About to call completion_view.set_success_state()")
        logger.debug(f"set_success_state called with: Success={success}, Log Length={len(log_content)}, Error Msg='{error_message}'")

        # Set success state and pass logs
        self.completion_view.set_success_state(success, log_content, error_message)
        self.stacked_widget.setCurrentIndex(VIEW_COMPLETION)

    # --- Slots for Completion Actions --- 
    def _create_shortcut(self, create: bool):
        """Handle the request to create shortcuts (using make_shortcut function)."""
        logger.debug(f"Entering _create_shortcut with create={create}")
        if not create:
            print("Skipping shortcut creation.")
            logger.debug("Skipping shortcut creation (create=False).")
            return

        # Need install_path to locate the installed ANPE.exe
        if not self._install_path:
            QMessageBox.warning(self, "Cannot Create Shortcut", "Internal error: Missing installation path.")
            return

        print("Creating shortcut(s) pointing to ANPE.exe...")

        # --- Define Shortcut Parameters & Paths ---
        shortcut_name = "ANPE"
        # Installation root directory
        install_root_abs = os.path.abspath(self._install_path)
        # Path to the installed launcher executable
        launcher_exe_abs = os.path.join(install_root_abs, "ANPE.exe")
        # Path to the copied icon file in the install root
        icon_path_abs = os.path.join(install_root_abs, "app_icon_logo.ico")

        # --- Verify Launcher Exists ---
        if not os.path.isfile(launcher_exe_abs):
             error_msg = f"Cannot create shortcut. Launcher executable not found after installation at:\n{launcher_exe_abs}"
             print(error_msg, file=sys.stderr)
             QMessageBox.critical(self, "Shortcut Failed", error_msg)
             return

        # --- Verify Icon File Exists ---
        if not os.path.isfile(icon_path_abs):
            print(f"Warning: Icon file '{icon_path_abs}' not found after copy. Shortcut will use default icon.", file=sys.stderr)
            logger.warning(f"Icon file '{icon_path_abs}' not found. Shortcut will use default icon.")
            icon_path_abs = None # Fallback to default

        try:
            # Create shortcut explicitly using the copied icon file
            print(f"Calling make_shortcut: script='{launcher_exe_abs}', name='{shortcut_name}', icon='{icon_path_abs}', working_dir='{install_root_abs}'")
            make_shortcut(
                script=launcher_exe_abs,  # Target is the launcher executable
                name=shortcut_name,
                icon=icon_path_abs,       # Use the explicit icon path
                # executable=None, # Not needed when script is an exe
                terminal=False,
                desktop=True,
                startmenu=True,
                working_dir=install_root_abs # Launcher expects to run from install root
            )

            # Register application and uninstaller link
            # Pass the explicit icon path for DisplayIcon
            self._register_app_and_create_uninstaller(install_root_abs, icon_path_abs)

            print("Desktop and Start Menu shortcuts created successfully.")
            logger.debug("make_shortcut and registry calls completed successfully.")
        except Exception as e:
            print(f"make_shortcut failed: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"Shortcut creation failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Shortcut Failed", f"Failed to create shortcuts using make_shortcut.\nError: {e}")
        logger.debug("Leaving _create_shortcut")

    def _register_app_and_create_uninstaller(self, install_root_abs, icon_path):
        """Register the application in Windows Add/Remove Programs and point to uninstall.exe."""
        try:
            # 1. Installation log (optional, can be kept or removed)
            install_log_path = os.path.join(install_root_abs, "install_log.txt")
            # ... (logging code can remain if useful) ...
            print(f"Install log being written to: {install_log_path}")
            # ... (rest of logging code) ...

            # 2. Define path to the installed uninstaller executable
            uninstaller_exe_abs = os.path.join(install_root_abs, "uninstall.exe")
            print(f"Uninstaller executable expected at: {uninstaller_exe_abs}")

            # --- Verify Uninstaller Exists ---
            if not os.path.isfile(uninstaller_exe_abs):
                error_msg = f"Cannot register uninstaller. Executable not found after installation at:\n{uninstaller_exe_abs}"
                print(error_msg, file=sys.stderr)
                # Don't make registration fail completely, maybe just warn?
                QMessageBox.warning(self, "Registration Warning", error_msg)
                # Fallback or skip registration?
                # For now, proceed without setting UninstallString if not found.
                uninstall_string = "" # Set empty if not found
            else:
                uninstall_string = f'"{uninstaller_exe_abs}"' # Properly quote the path

            # 3. Create registry entries
            app_name = "ANPE" # Consistent name
            app_version = "1.0.0"  # TODO: Parameterize or read from somewhere?
            publisher = "ANPE Project" # TODO: Update publisher if needed

            reg_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" # Use app_name in key

            print(f"Writing registry entries to: HKCU {reg_path}")
            reg_key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)

            winreg.SetValueEx(reg_key, "DisplayName", 0, winreg.REG_SZ, app_name)
            winreg.SetValueEx(reg_key, "DisplayVersion", 0, winreg.REG_SZ, app_version)
            winreg.SetValueEx(reg_key, "Publisher", 0, winreg.REG_SZ, publisher)
            winreg.SetValueEx(reg_key, "InstallLocation", 0, winreg.REG_SZ, install_root_abs)
            # --- Update UninstallString to point directly to uninstall.exe --- 
            if uninstall_string: # Only write if uninstaller was found
                 winreg.SetValueEx(reg_key, "UninstallString", 0, winreg.REG_SZ, uninstall_string)
            # ------------------------------------------------------------------
            # Use the provided explicit icon_path for DisplayIcon
            winreg.SetValueEx(reg_key, "DisplayIcon", 0, winreg.REG_SZ, icon_path if icon_path else "") 
            winreg.SetValueEx(reg_key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(reg_key, "NoRepair", 0, winreg.REG_DWORD, 1)
            # Estimate size? Difficult to calculate accurately here.
            # winreg.SetValueEx(reg_key, "EstimatedSize", 0, winreg.REG_DWORD, size_in_kb)

            winreg.CloseKey(reg_key)

            print("Application registered successfully in Windows Add/Remove Programs.")

        except Exception as e:
            print(f"Error during application registration: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Registration Error", f"Failed to register application components.\nError: {e}")
            # Continue without failing - this is an optional part of the installation

    def _launch_anpe(self, launch: bool):
        """Handle the request to launch ANPE by running ANPE.exe."""
        logger.debug(f"Entering _launch_anpe with launch={launch}")
        if not launch:
            print("Skipping ANPE launch.")
            logger.debug("Skipping ANPE launch (launch=False).")
            return
        
        # Need install_path to locate ANPE.exe
        if not self._install_path:
            QMessageBox.warning(self, "Cannot Launch ANPE", "Internal error: Missing installation path.")
            return
            
        print("Launching ANPE via ANPE.exe...")
        # --- Set the working directory and launch command --- 
        install_root_abs = os.path.abspath(self._install_path)
        launcher_exe_abs = os.path.join(install_root_abs, "ANPE.exe")
        
        print(f"Target executable: {launcher_exe_abs}")
        print(f"Working directory: {install_root_abs}")

        # --- Verify Launcher Exists ---
        if not os.path.isfile(launcher_exe_abs):
             error_msg = f"Cannot launch ANPE. Launcher executable not found after installation at:\n{launcher_exe_abs}"
             print(error_msg, file=sys.stderr)
             QMessageBox.critical(self, "Launch Failed", error_msg)
             return

        try:
            # Launch ANPE.exe directly, setting the CWD to the install root
            # Use CREATE_NO_WINDOW if available to prevent potential console flash (though ANPE.exe is windowed)
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW
                
            subprocess.Popen([launcher_exe_abs], cwd=install_root_abs, creationflags=creationflags)
            print("ANPE launch command issued.")
            logger.info("ANPE launch command issued successfully.")
        except FileNotFoundError:
            error_msg = f"Could not find the ANPE executable: {launcher_exe_abs}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Launch Failed", error_msg)
        except Exception as e:
            logger.error(f"Unexpected error launching ANPE: {e}", exc_info=True)
            QMessageBox.critical(self, "Launch Error", f"An unexpected error occurred while trying to launch ANPE:\n{e}")
        logger.debug("Leaving _launch_anpe")

    def closeEvent(self, event):
        """Handle the main window close event."""
        if self._is_running:
            reply = QMessageBox.question(self, 'Confirm Close',
                                       "Setup is currently in progress. Are you sure you want to cancel and exit?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                print("Terminating running processes and closing...")
                
                # First try to terminate any running processes gracefully
                # Environment setup worker
                if self._env_thread and self._env_thread.isRunning():
                    if hasattr(self._env_worker, "_process") and self._env_worker._process:
                        try:
                            # Try to terminate any running subprocess
                            self._env_worker._process.terminate()
                            # Give it a moment to terminate
                            self._env_worker._process.waitForFinished(1000)
                            # If it's still running, kill it
                            if self._env_worker._process.state() != QProcess.ProcessState.NotRunning:
                                self._env_worker._process.kill()
                        except Exception as e:
                            print(f"Error terminating environment process: {e}")
                    
                    # Quit the thread
                    self._env_thread.quit()
                    # Wait briefly for thread to finish
                    if not self._env_thread.wait(1000):
                        print("Environment setup thread did not terminate in time")
                
                # Model setup worker
                if self._model_thread and self._model_thread.isRunning():
                    if hasattr(self._model_worker, "_process") and self._model_worker._process:
                        try:
                            # Try to terminate any running subprocess
                            self._model_worker._process.terminate()
                            # Give it a moment to terminate
                            self._model_worker._process.waitForFinished(1000)
                            # If it's still running, kill it
                            if self._model_worker._process.state() != QProcess.ProcessState.NotRunning:
                                self._model_worker._process.kill()
                        except Exception as e:
                            print(f"Error terminating model process: {e}")
                    
                    # Quit the thread
                    self._model_thread.quit()
                    # Wait briefly for thread to finish
                    if not self._model_thread.wait(1000):
                        print("Model setup thread did not terminate in time")
                
                # Set flag to not running
                self._is_running = False
                
                # Accept the close event
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    """Main entry point for the application."""
    # Ensure logging is configured BEFORE anything else
    # (Assuming setup_logging is handled in utils imported elsewhere or globally)
    global_logger = logging.getLogger() # Get root logger
    global_logger.info("Starting ANPE Setup Application")
    
    # Configure logging to capture DEBUG level
    # If setup_logging is not already doing this, add basic config:
    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Make sure your file handler also captures DEBUG

    app = QApplication(sys.argv)

    try:
        global_logger.debug("Creating SetupMainWindow instance.")
        window = SetupMainWindow()
        global_logger.debug("SetupMainWindow created, starting event loop.")
        exit_code = app.exec()
        global_logger.info(f"Application event loop finished with exit code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        global_logger.critical("Unhandled exception caught in main execution loop!", exc_info=True)
        # Optionally show a critical error message to the user
        try:
            error_msg = f"A critical error occurred:\n\n{type(e).__name__}: {e}\n\nSee the log file for details."
            QMessageBox.critical(None, "Fatal Error", error_msg)
        except Exception as msg_e:
             # If even showing the message box fails, just log it
            global_logger.error(f"Failed to show critical error message box: {msg_e}")
        sys.exit(1) # Exit with a non-zero code to indicate failure

if __name__ == "__main__":
    main()
