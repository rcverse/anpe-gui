import sys
import subprocess
import os # Added for shortcut/launch paths
import platform # Added for platform-specific checks
import shutil
import winreg  # For Windows registry operations
import logging # Added for logging
import re # ADDED: For regex parsing of version file
import winshell # ADDED for retrieving standard folder paths
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget, QMessageBox, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QThread, QProcess # Added QThread and QProcess
from PyQt6.QtGui import QPalette, QColor, QIcon # Added QIcon for window icon
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
from installer.utils import get_resource_path, log_filename # Import log_filename
from installer.styles import BACKGROUND_COLOR, PRIMARY_COLOR  # Import background color

from pyshortcuts import make_shortcut

# Get logger instance (configured in utils.py)
logger = logging.getLogger()

# Constants for view indices (as per design doc)
VIEW_WELCOME = 0
VIEW_ENV_PROGRESS = 1
VIEW_MODEL_PROGRESS = 2
VIEW_COMPLETION = 3

# Define a primary color (using value from anpe_studio.theme)
PRIMARY_COLOR = "#005A9C"
BORDER_RADIUS = 10 # Adjust for desired roundness
BORDER_THICKNESS = 2 # Adjust for desired thickness

# --- Helper function to read bundled version ---
def get_bundled_app_version() -> str | None:
    """Reads the __version__ from the bundled anpe_studio/version.py file."""
    try:
        # Path relative to the installer script location or _MEIPASS root
        # utils.py's get_resource_path handles the _MEIPASS resolution.
        # This path assumes version.py is at _MEIPASS/assets/anpe_studio/version.py
        # and the script is at _MEIPASS/installer/setup_windows.pyw
        version_file_rel_path = "../assets/anpe_studio/version.py"
        version_file_abs_path = get_resource_path(version_file_rel_path)

        if not os.path.exists(version_file_abs_path):
            logger.error(f"Bundled version file not found at expected path: {version_file_abs_path}")
            return None

        with open(version_file_abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Use regex to find the __version__ assignment
        match = re.search(r"^__version__\s*=\s*['\"]([^'\"]*)['\"]", content, re.MULTILINE)
        if match:
            version = match.group(1)
            logger.info(f"Found bundled app version: {version}")
            return version
        else:
            logger.error(f"Could not find __version__ assignment in {version_file_abs_path}")
            return None
    except Exception as e:
        logger.error(f"Error reading bundled version file: {e}", exc_info=True)
        return None
# --- End helper function ---

class SetupMainWindow(QMainWindow):
    """Main window for the ANPE setup application with custom title bar."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # --- Set Window Icon --- 
        icon_path = get_resource_path("assets/app_icon_logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            logger.warning(f"Window icon not found at expected path: {icon_path}")
        # --- End Set Window Icon ---

        window_title = "ANPE Studio Setup Wizard"
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
                background-color: {BACKGROUND_COLOR}; /* Using imported background color */
                border: {BORDER_THICKNESS}px solid {PRIMARY_COLOR}; 
                border-radius: {BORDER_RADIUS}px; 
            }}
            /* Ensure child widgets don't draw over the rounded corners */
            /* This might need refinement based on specific widgets used */
            #MainFrame QStackedWidget > QWidget {{ 
                background-color: {BACKGROUND_COLOR}; /* Using imported background color */
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
        """Helper slot to print log messages to the console AND to the file logger."""
        # Keep console print for immediate feedback during development/debugging if desired
        print(f"WORKER LOG: {message}") 
        # Route the message to the configured Python logger
        logger.info(message)

    def _create_views(self):
        """Create and add view widgets to the stacked widget."""
        self.welcome_view = WelcomeViewWidget()
        self.stacked_widget.addWidget(self.welcome_view)
        self.welcome_view.setup_requested.connect(self._handle_setup_request)

        # Environment Progress View
        self.env_progress_view = ProgressViewWidget(
            "Installing ANPE Studio"
        )
        self.stacked_widget.addWidget(self.env_progress_view)

        # Model Progress View
        self.model_progress_view = ProgressViewWidget(
            "Downloading Language Models"
        )
        self.stacked_widget.addWidget(self.model_progress_view)

        # Completion View
        logger.debug("About to create CompletionViewWidget instance")
        self.completion_view = CompletionViewWidget()
        logger.debug("CompletionViewWidget instance created")
        self.stacked_widget.addWidget(self.completion_view)
        self.completion_view.shortcut_requested.connect(self._create_shortcut)
        self.completion_view.launch_requested.connect(self._launch_anpe)
        self.completion_view.preserve_log_requested.connect(self._handle_preserve_log_request)
        self.completion_view.close_requested.connect(self.close)

    def _check_for_existing_installation(self, install_path: str) -> bool:
        """Check if a valid installation already exists at the given path."""
        logger.info(f"Checking for existing installation at '{install_path}'...")
        print(f"Checking for existing installation at '{install_path}'...")
        
        # Import the function from installer_core
        try:
            from installer.installer_core import is_existing_installation_valid
            from pathlib import Path
            
            # Use the same function installer_core uses
            abs_path = Path(install_path).resolve()
            logger.info(f"Resolved absolute path for check: {abs_path}")
            
            is_upgrade = is_existing_installation_valid(abs_path)
            if is_upgrade:
                logger.info(f"Valid existing installation detected at '{abs_path}'. This will be an upgrade.")
                print(f"Valid existing installation detected at '{install_path}'. This will be an upgrade.")
            else:
                logger.info(f"No valid existing installation found at '{abs_path}'. This will be a fresh install.")
                print(f"No valid existing installation found at '{install_path}'. This will be a fresh install.")
            return is_upgrade
        except Exception as e:
            logger.error(f"Error checking for existing installation: {e}", exc_info=True)
            print(f"Failed to check for existing installation: {e}")
            # Default to fresh install in case of error
            return False

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

        # Check if this is an upgrade
        is_upgrade = self._check_for_existing_installation(install_path)
        
        # Start the appropriate setup flow
        if is_upgrade:
            # For upgrade, get Python path from existing installation
            try:
                # Construct the expected Python path
                from pathlib import Path
                python_dir = Path(abs_install_path) / "python"
                python_exe = python_dir / "python.exe"
                
                if python_exe.exists():
                    self._python_exe_path = str(python_exe)
                    print(f"Using existing Python from: {self._python_exe_path}")
                    
                    # Skip directly to app code update
                    self.env_progress_view.clear_log()
                    self.env_progress_view.update_status("Upgrading application files...")
                    self.stacked_widget.setCurrentIndex(VIEW_ENV_PROGRESS)
                    
                    # Create a worker that only updates app files
                    self._env_worker = EnvironmentSetupWorker(self._install_path, is_upgrade=True)
                    
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
                else:
                    logger.warning(f"Expected Python executable not found at {python_exe}. Falling back to full setup.")
                    self._start_environment_setup()
            except Exception as e:
                logger.error(f"Error during upgrade setup: {e}", exc_info=True)
                # Fall back to normal setup
                self._start_environment_setup()
        else:
            # For fresh install, do the normal setup
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
        
        # Determine if this was an upgrade
        is_upgrade = False
        if hasattr(self._env_worker, '_is_upgrade'):
            is_upgrade = self._env_worker._is_upgrade
            logger.info(f"Environment setup was running in upgrade mode: {is_upgrade}")
        
        # No longer need these as deleteLater handles cleanup
        # self._env_thread = None 
        # self._env_worker = None 

        if success and python_exe_path_str:
            self._python_exe_path = python_exe_path_str # Store the validated path
            # Start Stage 2: Model Setup
            self._start_model_setup(is_upgrade)
        else:
            # Setup failed, show completion view in failure state
            self._is_running = False
            self._is_env_setup_stage = True  # Still in env stage when failed
            # Pass the specific error message to the completion view
            self._show_completion_view(success=False, error_message=error_message)

    def _start_model_setup(self, is_upgrade: bool = False):
        """Instantiate and start the ModelSetupWorker in a QThread."""
        print("Starting model setup thread...")
        self._is_running = True # Still running
        self._is_env_setup_stage = False  # Now in model setup stage
        
        # Prepare progress view
        self.model_progress_view.clear_log()
        
        if is_upgrade:
            self.model_progress_view.update_status("Checking existing language models...")
        else:
            self.model_progress_view.update_status("Initializing language model setup...")
            
        self.model_progress_view.set_progress_range(0, 0) # Indeterminate
        self.stacked_widget.setCurrentIndex(VIEW_MODEL_PROGRESS)

        # Create worker and thread
        self._model_worker = ModelSetupWorker(self._python_exe_path, is_upgrade=is_upgrade)
        
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

        # Need install_path to locate the installed anpe.exe
        if not self._install_path:
            QMessageBox.warning(self, "Cannot Create Shortcut", "Internal error: Missing installation path.")
            return

        print("Creating shortcut(s) pointing to anpe.exe...")

        # --- Define Shortcut Parameters & Paths ---
        shortcut_name = "ANPE Studio"
        # Installation root directory
        install_root_abs = os.path.abspath(self._install_path)
        # Path to the installed launcher executable
        launcher_exe_abs = os.path.join(install_root_abs, "anpe.exe")
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
            # Define shortcut paths before creating them
            desktop_folder = winshell.desktop()
            startmenu_folder = winshell.programs() # Start Menu/Programs folder
            
            # Expected underscore version (created by pyshortcuts)
            desktop_lnk_path_underscore = os.path.join(desktop_folder, f"ANPE_Studio.lnk")
            startmenu_lnk_path_underscore = os.path.join(startmenu_folder, f"ANPE_Studio.lnk")
            
            # Correctly named versions
            desktop_lnk_path = os.path.join(desktop_folder, f"{shortcut_name}.lnk")
            startmenu_lnk_path = os.path.join(startmenu_folder, f"{shortcut_name}.lnk")
            
            # Log all paths
            logger.info(f"Desktop shortcut paths: {desktop_lnk_path_underscore} and {desktop_lnk_path}")
            logger.info(f"Start menu shortcut paths: {startmenu_lnk_path_underscore} and {startmenu_lnk_path}")
            
            # STEP 1: Remove any existing shortcuts FIRST
            for path in [desktop_lnk_path, desktop_lnk_path_underscore, 
                         startmenu_lnk_path, startmenu_lnk_path_underscore]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Removed existing shortcut: {path}")
                        print(f"Removed existing shortcut: {path}")
                except Exception as e:
                    logger.warning(f"Could not remove existing shortcut at {path}: {e}")
                    print(f"WARNING: Could not remove existing shortcut at {path}: {e}")
                    # Continue anyway - we'll try to create it
            
            # STEP 2: Now create the shortcut using the library
            logger.info(f"Creating shortcuts using make_shortcut: script='{launcher_exe_abs}', name='{shortcut_name}'")
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
            print("Desktop and Start Menu shortcuts created by make_shortcut.")
            logger.info("Desktop and Start Menu shortcuts created by make_shortcut.")
            
            # STEP 3: Rename the shortcuts (if the library created them with underscores)
            # Wait a brief moment to ensure files are created
            import time
            time.sleep(0.5)
            
            # Function to handle shortcut renaming with retries
            def rename_shortcut_with_retry(src, dest, max_retries=3):
                """Rename a shortcut with multiple retries if it fails."""
                if not os.path.exists(src):
                    logger.info(f"Source shortcut to rename not found: {src}")
                    return False
                
                if os.path.exists(dest):
                    logger.info(f"Destination shortcut already exists: {dest}")
                    return True
                    
                for attempt in range(max_retries):
                    try:
                        os.rename(src, dest)
                        logger.info(f"Successfully renamed shortcut from {src} to {dest}")
                        print(f"Renamed shortcut to use spaces instead of underscores.")
                        return True
                    except Exception as e:
                        logger.warning(f"Attempt {attempt+1}/{max_retries} to rename {src} failed: {e}")
                        time.sleep(0.5)  # Wait a moment before retrying
                
                logger.error(f"Failed to rename shortcut after {max_retries} attempts: {src}")
                return False
                
            # Rename desktop shortcut if needed
            if os.path.exists(desktop_lnk_path_underscore):
                rename_shortcut_with_retry(desktop_lnk_path_underscore, desktop_lnk_path)
            
            # Rename start menu shortcut if needed
            if os.path.exists(startmenu_lnk_path_underscore):
                rename_shortcut_with_retry(startmenu_lnk_path_underscore, startmenu_lnk_path)
                
            # STEP 4: Verify shortcuts exist
            desktop_exists = os.path.exists(desktop_lnk_path) or os.path.exists(desktop_lnk_path_underscore)
            startmenu_exists = os.path.exists(startmenu_lnk_path) or os.path.exists(startmenu_lnk_path_underscore)
            
            if desktop_exists and startmenu_exists:
                logger.info("Successfully verified both shortcuts exist")
            else:
                logger.warning(f"Not all shortcuts were created/verified. Desktop: {desktop_exists}, Start Menu: {startmenu_exists}")
            
            # Use the best available paths we have
            final_desktop_path = desktop_lnk_path if os.path.exists(desktop_lnk_path) else desktop_lnk_path_underscore
            final_startmenu_path = startmenu_lnk_path if os.path.exists(startmenu_lnk_path) else startmenu_lnk_path_underscore

            # Register application and uninstaller link, passing the verified shortcut paths
            self._register_app_and_create_uninstaller(install_root_abs, icon_path_abs, final_desktop_path, final_startmenu_path)
            
            # Refresh the desktop to make shortcuts immediately visible
            self._refresh_desktop()

            print("Shortcut creation, renaming, and registration process completed.")
            logger.debug("make_shortcut, rename operations, registry calls completed successfully.")
        except Exception as e:
            print(f"make_shortcut or subsequent operations failed: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"Shortcut creation or post-creation operations failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Shortcut Failed", f"Failed to create or properly name shortcuts.\nError: {e}")
        logger.debug("Leaving _create_shortcut")

    def _register_app_and_create_uninstaller(self, install_root_abs, icon_path, desktop_shortcut_path, start_menu_shortcut_path):
        """Register the application in Windows Add/Remove Programs, point to uninstall.exe, and store shortcut paths."""
        try:
            # 1. Define path to the installed uninstaller executable
            uninstaller_exe_abs = os.path.join(install_root_abs, "uninstall.exe")
            print(f"Uninstaller executable expected at: {uninstaller_exe_abs}")

            # --- Verify Uninstaller Exists ---
            if not os.path.isfile(uninstaller_exe_abs):
                error_msg = f"Cannot register uninstaller. Executable not found after installation at:\n{uninstaller_exe_abs}"
                print(error_msg, file=sys.stderr)
                QMessageBox.warning(self, "Registration Warning", error_msg)
                uninstall_string = ""  # Set empty if not found
            else:
                uninstall_string = f"{uninstaller_exe_abs}" # Properly quote the path

            app_name = "ANPE Studio"
            app_version = get_bundled_app_version() or "UNKNOWN"
            publisher = "Richard Chen"
            reg_path = rf"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}"

            print(f"Writing registry entries to: HKCU {reg_path}")
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE) as reg_key:
                winreg.SetValueEx(reg_key, "DisplayName", 0, winreg.REG_SZ, app_name)
                winreg.SetValueEx(reg_key, "DisplayVersion", 0, winreg.REG_SZ, app_version)
                winreg.SetValueEx(reg_key, "Publisher", 0, winreg.REG_SZ, publisher)
                winreg.SetValueEx(reg_key, "InstallLocation", 0, winreg.REG_SZ, install_root_abs)
                if uninstall_string:
                    winreg.SetValueEx(reg_key, "UninstallString", 0, winreg.REG_SZ, uninstall_string)
                winreg.SetValueEx(reg_key, "DisplayIcon", 0, winreg.REG_SZ, icon_path if icon_path else "")
                winreg.SetValueEx(reg_key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(reg_key, "NoRepair", 0, winreg.REG_DWORD, 1)

                # Store actual shortcut paths
                if os.path.exists(desktop_shortcut_path):
                    winreg.SetValueEx(reg_key, "DesktopShortcutPath", 0, winreg.REG_SZ, desktop_shortcut_path)
                    logger.info(f"Stored DesktopShortcutPath: {desktop_shortcut_path}")
                else:
                    winreg.SetValueEx(reg_key, "DesktopShortcutPath", 0, winreg.REG_SZ, "") # Store empty if not found
                    logger.warning(f"Desktop shortcut not found at {desktop_shortcut_path}, storing empty path.")
                
                if os.path.exists(start_menu_shortcut_path):
                    winreg.SetValueEx(reg_key, "StartMenuShortcutPath", 0, winreg.REG_SZ, start_menu_shortcut_path)
                    logger.info(f"Stored StartMenuShortcutPath: {start_menu_shortcut_path}")
                else:
                    winreg.SetValueEx(reg_key, "StartMenuShortcutPath", 0, winreg.REG_SZ, "") # Store empty if not found
                    logger.warning(f"Start Menu shortcut not found at {start_menu_shortcut_path}, storing empty path.")

            print("Application registered successfully with shortcut paths.")

        except Exception as e:
            print(f"Error during application registration: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Registration Error", f"Failed to register application components.\nError: {e}")
            # Continue without failing - this is an optional part of the installation

    def _refresh_desktop(self):
        """Refresh the Windows desktop to make new shortcuts immediately visible."""
        try:
            import ctypes
            # Use SHChangeNotify to tell the Windows shell that we've made changes
            # SHCNE_ASSOCCHANGED is a general refresh notification
            SHCNE_ASSOCCHANGED = 0x08000000
            SHCNF_IDLIST = 0
            ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
            logger.info("Desktop refresh notification sent successfully")
            print("Desktop refreshed to show new shortcuts.")
        except Exception as e:
            logger.error(f"Failed to refresh desktop: {e}", exc_info=True)
            print(f"Note: Could not refresh desktop view: {e}")

    def _launch_anpe(self, launch: bool):
        """Handle the request to launch ANPE by running anpe.exe."""
        logger.debug(f"Entering _launch_anpe with launch={launch}")
        if not launch:
            print("Skipping ANPE launch.")
            logger.debug("Skipping ANPE launch (launch=False).")
            return
        
        # Need install_path to locate anpe.exe
        if not self._install_path:
            QMessageBox.warning(self, "Cannot Launch ANPE", "Internal error: Missing installation path.")
            return
            
        print("Launching ANPE via anpe.exe...")
        # --- Set the working directory and launch command --- 
        install_root_abs = os.path.abspath(self._install_path)
        launcher_exe_abs = os.path.join(install_root_abs, "anpe.exe")
        
        print(f"Target executable: {launcher_exe_abs}")
        print(f"Working directory: {install_root_abs}")

        # --- Verify Launcher Exists ---
        if not os.path.isfile(launcher_exe_abs):
             error_msg = f"Cannot launch ANPE. Launcher executable not found after installation at:\n{launcher_exe_abs}"
             print(error_msg, file=sys.stderr)
             QMessageBox.critical(self, "Launch Failed", error_msg)
             return

        try:
            # Launch anpe.exe directly, setting the CWD to the install root
            # Use CREATE_NO_WINDOW if available to prevent potential console flash (though anpe.exe is windowed)
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

    def _handle_preserve_log_request(self, preserve: bool):
        """Handle the request to preserve or delete the actual installation log file."""
        logger.info(f"Signal received to handle log preservation. Preserve: {preserve}") # Changed to info for better visibility
        
        actual_log_file = log_filename  # Get the log filename from utils
        logger.info(f"Log filename from utils: '{actual_log_file}'")

        if not preserve:
            logger.info("Attempting to remove installation log file.")
            if actual_log_file and isinstance(actual_log_file, str) and actual_log_file.strip(): # Check if it's a non-empty string
                # Convert actual_log_file to an absolute path for reliable comparison with handler.baseFilename
                abs_actual_log_file = os.path.abspath(actual_log_file)
                logger.info(f"Resolved absolute log file path for deletion: '{abs_actual_log_file}'")

                # --- Gracefully shutdown logging to the target file ---
                logger.info(f"Attempting to shutdown logging for file: {abs_actual_log_file}")
                root_logger = logging.getLogger()
                found_and_removed_handler = False
                for handler in list(root_logger.handlers): # Iterate over a copy
                    if isinstance(handler, logging.FileHandler):
                        # Ensure handler.baseFilename is also absolute for comparison
                        handler_base_filename_abs = os.path.abspath(handler.baseFilename)
                        if handler_base_filename_abs == abs_actual_log_file:
                            logger.info(f"Found matching FileHandler for {abs_actual_log_file}. Closing and removing it.")
                            handler.close()
                            root_logger.removeHandler(handler)
                            found_and_removed_handler = True
                            # It's possible basicConfig sets up only one FileHandler.
                            # If multiple file handlers could point to the same file (unlikely with basicConfig),
                            # you might not want to break here. For this scenario, breaking is likely safe.
                            break 
                    # The check for StreamHandler writing to a file is less common with basicConfig
                    # but retained for completeness if custom handlers are ever added.
                    elif isinstance(handler, logging.StreamHandler) and hasattr(handler.stream, 'name'):
                        try:
                            # Ensure stream name can be resolved to an absolute path if it's a file path
                            stream_name_abs = os.path.abspath(handler.stream.name)
                            if stream_name_abs == abs_actual_log_file:
                                logger.info(f"Found matching StreamHandler writing to file {abs_actual_log_file}. Closing and removing it.")
                                handler.close()
                                root_logger.removeHandler(handler)
                                found_and_removed_handler = True
                                break
                        except Exception as e:
                            logger.debug(f"Could not compare stream name for handler {handler}: {e}")
                
                if found_and_removed_handler:
                    logger.info(f"Successfully closed and removed log handler for {abs_actual_log_file}.")
                else:
                    logger.warning(f"No specific file handler found for {abs_actual_log_file} among root logger's handlers. This might be okay if logging was already shut down or configured differently.")

                log_exists = os.path.exists(abs_actual_log_file) # Use abs_actual_log_file
                logger.info(f"Does log file exist at '{abs_actual_log_file}' after attempting logger shutdown? {log_exists}")
                
                if log_exists:
                    try:
                        os.remove(abs_actual_log_file) # Use abs_actual_log_file
                        # Verify removal
                        if not os.path.exists(abs_actual_log_file): # Use abs_actual_log_file
                            logger.info(f"Successfully removed installation log file: {abs_actual_log_file}")
                            print(f"Successfully removed installation log file: {abs_actual_log_file}")
                        else:
                            logger.error(f"os.remove was called on {abs_actual_log_file}, but it still exists!")
                            print(f"ERROR: os.remove was called on {abs_actual_log_file}, but it still exists!", file=sys.stderr)
                    except Exception as e:
                        print(f"Error removing installation log file: {e}", file=sys.stderr)
                        logger.error(f"Error removing installation log file '{abs_actual_log_file}': {e}", exc_info=True) # Added exc_info
                else:
                    logger.warning(f"Installation log file not found at '{abs_actual_log_file}' (after logger shutdown), skipping removal.")
            elif actual_log_file: # It has a value, but not a valid non-empty string
                logger.error(f"Installation log file path from utils ('{actual_log_file}') is not a valid non-empty string. Cannot remove.")
            else: # log_filename was None or empty from the start
                 logger.error("Could not determine installation log file path from utils (log_filename is None or empty). Cannot remove.")
        else:
            logger.info(f"Preserving installation log file ('{os.path.abspath(actual_log_file) if actual_log_file else 'N/A'}') as requested.")
        logger.debug("Leaving _handle_preserve_log_request")

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
