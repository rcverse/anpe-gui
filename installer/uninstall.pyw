import sys
import os
import shutil
import winreg
import subprocess
import time
import traceback
import threading # Added
import queue     # Added
import tkinter as tk # Added
import base64
import ctypes
from ctypes import wintypes
from tkinter import ttk, messagebox, filedialog, scrolledtext, font as tkFont # Added
from typing import Optional, Tuple, Callable, Any, List # Added

# Import logo data from separate file (reduces main file size and improves maintainability)
# Use a path-based import to ensure it works when packaged with PyInstaller
try:
    # First try importing directly (for development)
    from logo_data import LOGO_BASE64
except ImportError:
    # If that fails, try to load from the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from logo_data import LOGO_BASE64

# Optional dependencies:
# - psutil: Preferred for process checking (pip install psutil)
# If not available, will fall back to using wmic command directly (Windows-only).

# --- Process Checking Functions ---
def check_anpe_running(install_path: str) -> Tuple[bool, List[str]]:
    """
    Check if any ANPE Studio processes are currently running.
    
    Args:
        install_path: The installation path to check against
    
    Returns:
        Tuple containing:
            - Boolean indicating if ANPE is running
            - List of process details strings for any running ANPE processes
    """
    running_processes = []
    normalized_install_path = os.path.normcase(os.path.abspath(install_path))
    normalized_run_script = os.path.normcase(os.path.join(normalized_install_path, "anpe_studio", "run.py"))
    
    try:
        # Try using psutil if available (preferred method)
        import psutil
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip non-Python processes quickly
                if proc.info['name'].lower() not in ('python.exe', 'pythonw.exe'):
                    continue
                    
                # Check command line args for our run script
                cmdline = proc.info['cmdline']
                if not cmdline or len(cmdline) < 2:
                    continue
                    
                # Check if this process is running our script from our install path
                for arg in cmdline:
                    arg_norm = os.path.normcase(arg)
                    if arg_norm == normalized_run_script or (
                        "anpe_studio" in arg_norm and 
                        "run.py" in arg_norm and 
                        normalized_install_path in arg_norm
                    ):
                        proc_info = f"Process: {proc.info['name']} (PID: {proc.info['pid']}), Command: {' '.join(cmdline)}"
                        running_processes.append(proc_info)
                        break
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except ImportError:
        # Fallback to wmic command on Windows
        try:
            # Use Windows built-in wmic command
            output = subprocess.check_output(
                ["wmic", "process", "where", "name='pythonw.exe'", "get", "ProcessId,CommandLine", "/format:list"], 
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Parse the output
            current_pid = None
            current_cmdline = None
            
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    # Process entry separator - check accumulated data
                    if current_cmdline and current_pid and (
                        "anpe_studio" in current_cmdline.lower() and 
                        "run.py" in current_cmdline.lower() and
                        normalized_install_path.lower() in current_cmdline.lower()
                    ):
                        proc_info = f"Process: pythonw.exe (PID: {current_pid}), Command: {current_cmdline}"
                        running_processes.append(proc_info)
                        
                    # Reset for next process
                    current_pid = None
                    current_cmdline = None
                elif line.startswith("CommandLine="):
                    current_cmdline = line[len("CommandLine="):].strip()
                elif line.startswith("ProcessId="):
                    current_pid = line[len("ProcessId="):].strip()
            
            # Check the last entry
            if current_cmdline and current_pid and (
                "anpe_studio" in current_cmdline.lower() and 
                "run.py" in current_cmdline.lower() and
                normalized_install_path.lower() in current_cmdline.lower()
            ):
                proc_info = f"Process: pythonw.exe (PID: {current_pid}), Command: {current_cmdline}"
                running_processes.append(proc_info)
                
        except (subprocess.SubprocessError, OSError):
            # If all methods fail, we can't detect processes - note this in output
            running_processes.append("WARNING: Could not check for running processes! Please ensure ANPE Studio is closed.")

    # Return a tuple of (is_running, process_list)
    return len(running_processes) > 0, running_processes

# --- Base64 Logo ---


def get_logo_image(size: Tuple[int, int]) -> Optional[tk.PhotoImage]:
    """Create a PhotoImage from the base64 encoded app logo."""
    try:
        # Extract the actual base64 data (remove the header)
        base64_data = LOGO_BASE64.split(',')[-1]
        
        # Create a PhotoImage from the base64 data
        img = tk.PhotoImage(data=base64.b64decode(base64_data))
        
        # If a size is provided and different from original, we need to subsample
        # This is a simple approach since tkinter doesn't have great resizing
        if size:
            # Use the subsample method to get a smaller version
            # Not ideal but works for simple icons
            orig_width = img.width()
            orig_height = img.height()
            
            # Calculate subsample factors
            width_factor = max(1, int(orig_width / size[0]))
            height_factor = max(1, int(orig_height / size[1]))
            
            # Apply subsample
            img = img.subsample(width_factor, height_factor)
            
        return img
    except Exception as e:
        print(f"Error creating logo from base64: {e}", file=sys.stderr)
        return None

# --- Constants ---
APP_NAME = "ANPE Studio"
REGISTRY_KEY_PATH = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
# Additional registry locations that might store ANPE-related settings
REGISTRY_SETTINGS_PATH = rf"Software\rcverse\ANPE_STUDIO" # Settings path used by QSettings in the app
REGISTRY_USER_PATHS = [
    REGISTRY_KEY_PATH,           # Main uninstall key
    REGISTRY_SETTINGS_PATH,      # App settings
    rf"Software\rcverse",        # Parent company key (only if empty after removing ANPE_STUDIO)
]
REGISTRY_INSTALL_LOCATION_VALUE = "InstallLocation"
REGISTRY_SHORTCUT_LOCATION_VALUE = "ShortcutLocation"
# Name of the shortcut file (without .lnk extension)
SHORTCUT_NAME = APP_NAME  # Make sure APP_NAME is defined, e.g., "ANPE Studio"
    
# Registry Value Names for Shortcut Paths
REG_VAL_DESKTOP_SHORTCUT = "DesktopShortcutPath"
REG_VAL_STARTMENU_SHORTCUT = "StartMenuShortcutPath"
    
# For CSIDL values used in getting special folder paths
CSIDL_DESKTOPDIRECTORY = 0x0010  # Desktop
CSIDL_PROGRAMS = 0x0002          # Start Menu > Programs
# ... other global constants like REGISTRY_KEY_PATH etc.

# UI Constants
WINDOW_WIDTH = 650     # Increased width from 500 to 600
WINDOW_HEIGHT = 520    # Reduced height
PADDING = 15
PRIMARY_FONT_FAMILY = "Segoe UI"
FALLBACK_FONT_FAMILY = "Arial" # Use a common fallback
DEFAULT_FONT_SIZE = 10
TITLE_FONT_SIZE = 20    # Increased from 16 for more emphasis
SUBTITLE_FONT_SIZE = 11 # New constant for subtitle text
SMALL_FONT_SIZE = 9    # Added for smaller text
LOGO_SIZE = (70, 70)    # Size for the logo display (width, height)

# Colors
LIGHT_BG_COLOR = "#FFFFFF"
PRIMARY_COLOR = "#005A9C" # ANPE Blue
SECONDARY_TEXT_COLOR = "#555555"
ERROR_COLOR = "#D32F2F"
WARNING_COLOR = "#F57C00" # Orange for warnings
SUCCESS_COLOR = "#388E3C"
BORDER_COLOR = "#CCCCCC"
INFO_COLOR = "#0277BD" # Blue for information
INPUT_BG_COLOR = "#F9F9F9" # Light gray for input background
LOG_BG_COLOR_PROGRESS = "#F5F5F5" # Very light gray for progress view log
LOG_BG_COLOR_COMPLETION = "#F0F4F8" # Light blue-gray for completion view log
INPUT_HEIGHT = 26  # Standard height for input elements to match buttons

# Worker Communication Actions
ACTION_STATUS = "status"
ACTION_LOG = "log"
ACTION_PROGRESS = "progress"
ACTION_FINISHED = "finished"

# View Names (for switching)
VIEW_WELCOME = "Welcome"
VIEW_PROGRESS = "Progress"
VIEW_COMPLETION = "Completion"

# Add to constants section at the top
UNINSTALL_LOG_DIR = "logs"
UNINSTALL_LOG_FILE = "uninstall_log.txt"

# Add to constants section at the top
ANPE_INSTALLED_DIRS = [
    "anpe_studio",  # Main application code directory
    "python",    # Python environment directory
]

ANPE_INSTALLED_FILES = [
    "anpe.exe",      # Main executable
    "uninstall.exe", # Uninstaller executable
    "app_icon_logo.ico",
]

# --- Helper Functions (New for Tkinter) ---
def set_widget_state(widget: ttk.Widget, state: str):
    """Safely sets the state of a widget (e.g., 'normal', 'disabled')."""
    try:
        if widget.winfo_exists():
            widget.config(state=state)
    except tk.TclError as e:
        print(f"Warning: Could not set state '{state}' for widget: {e}")

def center_window(win):
    """Centers a Tkinter window on the screen."""
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')

def _get_special_folder_path(csidl_value: int) -> str:
    """
    Gets the path to a special folder using Windows CSIDL values.
    
    Args:
        csidl_value: The CSIDL integer value for the desired folder.
    
    Returns:
        The path to the special folder as a string.
    """
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl_value, None, 0, buf)
    return buf.value

# --- Uninstall Worker (Adapted for Tkinter Threading) ---
class UninstallWorker(threading.Thread):
    """Worker thread to handle the actual uninstallation process."""

    def __init__(self, install_path: str, output_queue: queue.Queue, remove_models: bool):
        super().__init__(daemon=True) # Make it a daemon thread
        if not install_path or not os.path.isdir(install_path):
            raise ValueError("Invalid installation path provided to UninstallWorker.")
        self.install_path = os.path.abspath(install_path)
        self.log_dir = os.path.join(self.install_path, "logs")
        self.log_path = os.path.join(self.log_dir, "uninstall_log.txt")
        self.uninstaller_script_path = os.path.abspath(__file__)
        self.output_queue = output_queue
        self._full_log = [] # Store the full log content
        self.remove_models = remove_models

    def _send_update(self, action: str, data: Any):
        """Send updates to the main thread via the queue."""
        try:
            self.output_queue.put((action, data))
        except Exception as e:
            # Log error if queue fails? Unlikely but possible.
            print(f"Error putting item on queue: {e}")

    def _log(self, message: str):
        """Log message to file and send update to UI."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self._full_log.append(log_entry) # Add timestamped entry to full log

        try:
            os.makedirs(self.log_dir, exist_ok=True)
            with open(self.log_path, "a", encoding='utf-8') as f:
                f.write(log_entry + "\n")
        except OSError as e:
            print(f"Error writing to log file {self.log_path}: {e}", file=sys.stderr)
            # Send log error to UI
            self._send_update(ACTION_LOG, f"[Log Write Error] {message}")
            return # Don't emit the original message if write failed

        self._send_update(ACTION_LOG, message) # Send only the message part to UI queue

    def run(self):
        """Main uninstallation process."""
        steps = 5 if self.remove_models else 4  # Add model cleaning step if requested
        current_step = 0
        final_message = ""
        success = True

        try:
            self._log(f"Uninstaller script path: {self.uninstaller_script_path}")
            self._log(f"Target installation directory: {self.install_path}")
            self._log(f"Log file path: {self.log_path}")
            self._log(f"Model removal requested: {self.remove_models}")

            # --- Step 1: Remove Start Menu Shortcut ---
            current_step += 1
            self._send_update(ACTION_PROGRESS, (current_step, steps))
            self._send_update(ACTION_STATUS, "Removing Start Menu shortcut...")
            self._log("Attempting to remove Start Menu shortcut...")
            shortcut_removed, shortcut_msg = self._remove_shortcuts()
            self._log(shortcut_msg)
            if not shortcut_removed:
                self._log("Warning: Failed to remove Start Menu shortcut. Continuing uninstall.")

            # --- Step 2: Remove Registry Entries ---
            current_step += 1
            self._send_update(ACTION_PROGRESS, (current_step, steps))
            self._send_update(ACTION_STATUS, "Removing registry entries...")
            self._log("Attempting to remove registry entries...")
            registry_removed, registry_msg = self._remove_registry_entries()
            self._log(registry_msg)
            if not registry_removed:
                self._log("Warning: Failed to remove registry entries. Continuing uninstall.")
                
            # --- Step 3: Clean ANPE Models (if requested) ---
            if self.remove_models:
                current_step += 1
                self._send_update(ACTION_PROGRESS, (current_step, steps))
                self._send_update(ACTION_STATUS, "Cleaning ANPE models (this may take a while)...")
                self._log("Attempting to clean ANPE-related models...")
                
                models_cleaned, models_msg = self._clean_anpe_models()
                self._log(models_msg)
                if not models_cleaned:
                    self._log("Warning: Failed to completely clean ANPE models. Continuing uninstall.")

            # --- Step 4: Remove Installed Files and Directories ---
            current_step += 1
            self._send_update(ACTION_PROGRESS, (current_step, steps))
            self._send_update(ACTION_STATUS, "Removing installed files...")
            self._log(f"Attempting to remove files and directories in {self.install_path}...")
            files_removed, files_msg = self._remove_installed_files()
            self._log(files_msg)
            if not files_removed:
                success = False
                self._log("Error: Failed to remove some installed files or directories. Uninstallation incomplete.")
                # Use the summary message from _remove_installed_files if available
                if "File removal summary:" in files_msg:
                    final_message = files_msg.split("File removal summary:")[0].strip() # Get errors part
                    if not final_message: final_message = "Failed to remove some files/directories."
                else:
                     final_message = "Failed to remove some installed files/directories."

            # --- Step 5: Finalization ---
            current_step += 1
            self._send_update(ACTION_PROGRESS, (current_step, steps))
            if success:
                self._send_update(ACTION_STATUS, "Uninstallation completed successfully.")
                self._log("Uninstallation process completed successfully.")
                if not final_message: # Only set if not already set by failure
                    final_message = f"{APP_NAME} uninstalled successfully."
            else:
                self._send_update(ACTION_STATUS, "Uninstallation failed.")
                self._log("Uninstallation process failed.")
                if not final_message: # Ensure final_message is set on failure
                     final_message = "Uninstallation failed. See logs for details."

        except Exception as e:
            success = False
            error_details = traceback.format_exc()
            final_message = f"An unexpected error occurred: {e}"
            # Try sending update even in catastrophic failure
            try:
                self._send_update(ACTION_STATUS, "Uninstallation failed due to an error.")
            except Exception:
                pass # Ignore if queue fails here
            self._log(f"FATAL ERROR during uninstallation: {e}\n{error_details}")
            print(f"Uninstallation Error: {e}\n{error_details}", file=sys.stderr)

        finally:
            # Ensure the final signal is always emitted via the queue
            full_log_content = "\n".join(self._full_log)
            self._send_update(ACTION_FINISHED, (success, final_message, full_log_content, self.log_path))

    # --- Core Logic Methods (Unchanged) ---
    def _remove_shortcuts(self) -> tuple[bool, str]:
        """
        Removes Desktop and Start Menu shortcuts for the application.
        It first tries to read precise paths from the registry (written by the installer).
        If not found, it falls back to checking common locations.
        """
        messages = []
        all_removed_successfully = True
        shortcut_filename = f"{SHORTCUT_NAME}.lnk"
        
        desktop_shortcut_removed_via_registry = False
        startmenu_shortcut_removed_via_registry = False

        # Attempt to remove shortcuts using paths from registry first
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH, 0, winreg.KEY_READ) as reg_key:
                # --- Desktop Shortcut from Registry ---
                try:
                    desktop_shortcut_reg_path, _ = winreg.QueryValueEx(reg_key, REG_VAL_DESKTOP_SHORTCUT)
                    if desktop_shortcut_reg_path and os.path.exists(desktop_shortcut_reg_path):
                        os.remove(desktop_shortcut_reg_path)
                        msg = f"Desktop shortcut removed (from registry path): {desktop_shortcut_reg_path}"
                        messages.append(msg)
                        self._log(f"INFO: {msg}")
                        desktop_shortcut_removed_via_registry = True
                    elif desktop_shortcut_reg_path: # Path in registry but not on disk
                        msg = f"Desktop shortcut path from registry not found on disk: {desktop_shortcut_reg_path}"
                        messages.append(msg)
                        self._log(f"INFO: {msg}")
                    # If value is empty string in registry, it won't be processed above.
                    # If value name doesn't exist, FileNotFoundError is caught.
                except FileNotFoundError:
                    self._log(f"INFO: Registry value '{REG_VAL_DESKTOP_SHORTCUT}' not found.")
                except Exception as e_reg_desktop:
                    all_removed_successfully = False # Consider error in registry read as failure
                    error_msg = f"Error processing registry desktop shortcut path: {e_reg_desktop}"
                    messages.append(error_msg)
                    self._log(f"ERROR: {error_msg}")

                # --- Start Menu Shortcut from Registry ---
                try:
                    startmenu_shortcut_reg_path, _ = winreg.QueryValueEx(reg_key, REG_VAL_STARTMENU_SHORTCUT)
                    if startmenu_shortcut_reg_path and os.path.exists(startmenu_shortcut_reg_path):
                        os.remove(startmenu_shortcut_reg_path)
                        msg = f"Start Menu shortcut removed (from registry path): {startmenu_shortcut_reg_path}"
                        messages.append(msg)
                        self._log(f"INFO: {msg}")
                        startmenu_shortcut_removed_via_registry = True
                        # Note: The installer (setup_windows.pyw using pyshortcuts) typically creates the .lnk
                        # directly in the Programs folder, not in an app-specific subfolder by default.
                        # So, removing an app-specific folder here based on registry path is not usually needed
                        # unless the installer's behavior changes to create such a subfolder AND store that path.
                    elif startmenu_shortcut_reg_path: # Path in registry but not on disk
                        msg = f"Start Menu shortcut path from registry not found on disk: {startmenu_shortcut_reg_path}"
                        messages.append(msg)
                        self._log(f"INFO: {msg}")
                except FileNotFoundError:
                    self._log(f"INFO: Registry value '{REG_VAL_STARTMENU_SHORTCUT}' not found.")
                except Exception as e_reg_startmenu:
                    all_removed_successfully = False
                    error_msg = f"Error processing registry Start Menu shortcut path: {e_reg_startmenu}"
                    messages.append(error_msg)
                    self._log(f"ERROR: {error_msg}")

        except FileNotFoundError:
            self._log(f"INFO: Main uninstall registry key '{REGISTRY_KEY_PATH}' not found. Cannot read shortcut paths from registry.")
        except Exception as e_reg_open:
            all_removed_successfully = False # If we can't open the key, we can't confirm removal via registry
            error_msg = f"Error opening registry key '{REGISTRY_KEY_PATH}': {e_reg_open}"
            messages.append(error_msg)
            self._log(f"ERROR: {error_msg}")

        # --- Fallback to common locations if not removed via registry ---
        # Desktop Shortcut Fallback
        if not desktop_shortcut_removed_via_registry:
            self._log("INFO: Desktop shortcut not removed via registry. Trying fallback common path.")
            try:
                desktop_path = _get_special_folder_path(CSIDL_DESKTOPDIRECTORY)
                desktop_shortcut_path_fallback = os.path.join(desktop_path, shortcut_filename)
                
                if os.path.exists(desktop_shortcut_path_fallback):
                    os.remove(desktop_shortcut_path_fallback)
                    msg = f"Desktop shortcut removed (fallback common path): {desktop_shortcut_path_fallback}"
                    messages.append(msg)
                    self._log(f"INFO: {msg}")
                else:
                    # Only add "not found" if no message about desktop shortcut exists yet
                    if not any("Desktop shortcut" in m for m in messages):
                        msg = f"Desktop shortcut not found (fallback common path): {desktop_shortcut_path_fallback}"
                        messages.append(msg)
                        self._log(f"INFO: {msg}")
            except Exception as e_fallback_desktop:
                all_removed_successfully = False
                error_msg = f"Error removing desktop shortcut (fallback): {e_fallback_desktop}"
                messages.append(error_msg)
                self._log(f"ERROR: {error_msg}")

        # Start Menu Shortcut Fallback
        if not startmenu_shortcut_removed_via_registry:
            self._log("INFO: StartMenu shortcut not removed via registry. Trying fallback common paths.")
            try:
                start_menu_programs_path = _get_special_folder_path(CSIDL_PROGRAMS)
                # Path variant a) Directly in Programs
                start_menu_shortcut_v1_fallback = os.path.join(start_menu_programs_path, shortcut_filename)
                # Path variant b) In a subfolder named like the application
                app_specific_start_menu_folder_fallback = os.path.join(start_menu_programs_path, SHORTCUT_NAME)
                start_menu_shortcut_v2_fallback = os.path.join(app_specific_start_menu_folder_fallback, shortcut_filename)

                removed_sm_shortcut_fallback = False
                if os.path.exists(start_menu_shortcut_v1_fallback):
                    os.remove(start_menu_shortcut_v1_fallback)
                    msg = f"Start Menu shortcut removed (fallback common path): {start_menu_shortcut_v1_fallback}"
                    messages.append(msg)
                    self._log(f"INFO: {msg}")
                    removed_sm_shortcut_fallback = True
                elif os.path.exists(start_menu_shortcut_v2_fallback):
                    os.remove(start_menu_shortcut_v2_fallback)
                    msg = f"Start Menu shortcut removed (fallback common path): {start_menu_shortcut_v2_fallback}"
                    messages.append(msg)
                    self._log(f"INFO: {msg}")
                    removed_sm_shortcut_fallback = True
                    # Attempt to remove the application-specific Start Menu folder if it's empty
                    try:
                        if os.path.exists(app_specific_start_menu_folder_fallback) and \
                           os.path.isdir(app_specific_start_menu_folder_fallback) and \
                           not os.listdir(app_specific_start_menu_folder_fallback):
                            os.rmdir(app_specific_start_menu_folder_fallback)
                            msg_dir = f"Empty Start Menu shortcut folder removed (fallback): {app_specific_start_menu_folder_fallback}"
                            messages.append(msg_dir)
                            self._log(f"INFO: {msg_dir}")
                    except Exception as e_rmdir_fallback:
                        msg_dir_err = f"Could not remove Start Menu folder (fallback) '{app_specific_start_menu_folder_fallback}': {e_rmdir_fallback}"
                        # messages.append(msg_dir_err) # Optional: only log, don't clutter summary too much
                        self._log(f"INFO: {msg_dir_err}")
                
                if not removed_sm_shortcut_fallback:
                     if not any("Start Menu shortcut" in m for m in messages):
                        msg = f"Start Menu shortcut not found at common fallbacks (e.g., '{start_menu_shortcut_v1_fallback}' or '{start_menu_shortcut_v2_fallback}')"
                        messages.append(msg)
                        self._log(f"INFO: {msg}")

            except Exception as e_fallback_startmenu:
                all_removed_successfully = False
                error_msg = f"Error removing Start Menu shortcut (fallback): {e_fallback_startmenu}"
                messages.append(error_msg)
                self._log(f"ERROR: {error_msg}")
        
        if not messages: # If truly nothing was done and no errors.
            summary_message = "No shortcut removal actions performed or necessary (no paths in registry, no common paths found)."
        else:
            summary_message = " ".join(messages) # Concatenate all messages.
            
        return all_removed_successfully, summary_message

    def _remove_registry_entries(self) -> tuple[bool, str]:
        """Removes all application's registry keys."""
        success = True
        removed_count = 0
        errors = []
        results = []

        # We'll delete keys in order - most specific to least specific
        for reg_path in REGISTRY_USER_PATHS:
            try:
                # First check if the key exists
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
                        # Key exists, attempt to delete it recursively
                        self._log(f"Found registry key: {reg_path}, removing...")
                        
                        # Delete any subkeys recursively (if any)
                        self._delete_key_recursive(winreg.HKEY_CURRENT_USER, reg_path)
                        
                        removed_count += 1
                        results.append(f"Registry key '{reg_path}' removed successfully.")
                except FileNotFoundError:
                    # This key doesn't exist, which is fine
                    self._log(f"Registry key '{reg_path}' not found. Skipping.")
                    results.append(f"Registry key '{reg_path}' not found. Nothing to remove.")
                    
            except OSError as e:
                error_msg = f"Error removing registry key '{reg_path}': {e}"
                self._log(f"ERROR: {error_msg}")
                errors.append(error_msg)
                success = False
            except Exception as e:
                error_msg = f"Unexpected error removing registry key '{reg_path}': {e}"
                self._log(f"ERROR: {error_msg}")
                errors.append(error_msg)
                success = False
                
        # Generate the summary message
        if removed_count > 0:
            summary = f"Successfully removed {removed_count} registry keys."
        else:
            summary = "No registry keys were found to remove."
            
        if errors:
            summary += "\nErrors encountered:\n" + "\n".join(errors)
            
        return success, summary
        
    def _delete_key_recursive(self, root_key, sub_key):
        """
        Recursively delete a registry key and all its subkeys.
        """
        try:
            # Open the key
            with winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_READ | winreg.KEY_ENUMERATE_SUB_KEYS) as key:
                # Enumerate subkeys
                subkey_count = winreg.QueryInfoKey(key)[0]
                
                # If no subkeys, we can delete directly
                if subkey_count == 0:
                    winreg.DeleteKey(root_key, sub_key)
                    return
                    
                # Otherwise, we need to collect subkey names first
                # (Can't modify while enumerating)
                subkey_names = []
                for i in range(subkey_count):
                    # Get each subkey name
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_names.append(subkey_name)
                    
            # Now delete each subkey
            for subkey_name in subkey_names:
                # Full path to the subkey
                full_subkey_path = f"{sub_key}\\{subkey_name}"
                # Recursively delete this subkey
                self._delete_key_recursive(root_key, full_subkey_path)
                
            # After all subkeys are deleted, delete the main key
            winreg.DeleteKey(root_key, sub_key)
        except FileNotFoundError:
            # Key doesn't exist
            pass
        except Exception as e:
            self._log(f"Error during recursive registry key deletion: {e}")
            raise  # Re-raise to be caught by the caller

    def _remove_installed_files(self) -> tuple[bool, str]:
        """Removes only ANPE-related files and directories within the installation path."""
        removed_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        # Skip trying to remove log directory during uninstallation
        norm_log_path = os.path.normcase(self.log_path)
        norm_log_dir = os.path.normcase(self.log_dir)

        if not os.path.exists(self.install_path):
            return True, "Installation directory does not exist. Nothing to remove."

        try:
            items = os.listdir(self.install_path)
        except OSError as e:
            return False, f"Could not list installation directory '{self.install_path}': {e}"

        for item_name in items:
            item_path = os.path.join(self.install_path, item_name)
            norm_item_path = os.path.normcase(os.path.abspath(item_path))

            # Skip logs - they'll be handled by completion page
            if norm_item_path == norm_log_path or norm_item_path == norm_log_dir:
                skipped_count += 1
                continue

            # Only remove known ANPE files and directories
            is_anpe_dir = item_name in ANPE_INSTALLED_DIRS
            is_anpe_file = item_name in ANPE_INSTALLED_FILES
            
            if not (is_anpe_dir or is_anpe_file):
                self._log(f"Skipping non-ANPE item: {item_path}")
                skipped_count += 1
                continue

            try:
                if os.path.isdir(item_path):
                    self._log(f"Removing ANPE directory: {item_path}")
                    shutil.rmtree(item_path, ignore_errors=False)
                    removed_count += 1
                elif os.path.isfile(item_path):
                    # Don't remove uninstaller yet - it's still running
                    if item_name == "uninstall.exe":
                        skipped_count += 1
                        continue
                    self._log(f"Removing ANPE file: {item_path}")
                    os.remove(item_path)
                    removed_count += 1
            except (OSError, PermissionError) as e:
                error_msg = f"Failed to remove {item_path}: {e}"
                self._log(f"ERROR: {error_msg}")
                errors.append(error_msg)
                error_count += 1

        try:
            # Check if only uninstaller and logs remain
            remaining_items = [item for item in os.listdir(self.install_path) 
                             if item != "uninstall.exe" and item != "logs"]
            if not remaining_items:
                self._log("Only uninstaller and logs remain. Directory will be removed on close.")
            else:
                non_anpe_items = [item for item in remaining_items if item not in ANPE_INSTALLED_DIRS + ANPE_INSTALLED_FILES]
                if non_anpe_items:
                    self._log(f"Non-ANPE items remain in directory: {', '.join(non_anpe_items)}")
        except OSError as e:
            self._log(f"Warning: Could not check installation directory contents: {e}")

        summary = f"File removal summary: {removed_count} removed, {skipped_count} skipped, {error_count} errors."
        if errors:
            summary += "\nErrors encountered:\n" + "\n".join(errors)

        return error_count == 0, summary

    def _clean_anpe_models(self) -> tuple[bool, str]:
        """Cleans ANPE-related models (spaCy and benepar) using the ANPE CLI command."""
        try:
            # Find the Python executable in the installation directory
            python_dir = os.path.join(self.install_path, "python")
            if not os.path.exists(python_dir):
                return False, "Python directory not found in the installation path."
                
            # Look for the ANPE CLI in the Scripts directory
            scripts_dir = os.path.join(python_dir, "Scripts")
            anpe_cli = os.path.join(scripts_dir, "anpe.exe") 
            
            # If Scripts directory or anpe.exe doesn't exist, try direct module execution
            if not os.path.exists(scripts_dir) or not os.path.exists(anpe_cli):
                self._log("ANPE CLI executable not found in Scripts directory. Trying Python module approach...")
                
                # Find Python executable
                python_exe = None
                for executable_name in ["python.exe", "pythonw.exe"]:
                    executable_path = os.path.join(python_dir, executable_name)
                    if os.path.exists(executable_path):
                        python_exe = executable_path
                        break
                        
                # Also check the Scripts directory for Python
                if not python_exe and os.path.exists(scripts_dir):
                    for executable_name in ["python.exe", "pythonw.exe"]:
                        executable_path = os.path.join(scripts_dir, executable_name)
                        if os.path.exists(executable_path):
                            python_exe = executable_path
                            break
                
                if not python_exe:
                    return False, "Python executable not found in the installation directory."
                    
                self._log(f"Found Python executable: {python_exe}")
                
                # Use Python to run the module directly
                self._log("Starting ANPE model cleanup using Python module...")
                command = [python_exe, "-m", "anpe.utils.clean_models", "--force"]
            else:
                # Use the ANPE CLI directly
                self._log(f"Found ANPE CLI at: {anpe_cli}")
                self._log("Starting ANPE model cleanup using CLI...")
                command = [anpe_cli, "setup", "--clean-models", "--force"]
            
            # Execute the command
            self._send_update(ACTION_STATUS, "Cleaning ANPE models (this may take a while)...")
            sub_env = os.environ.copy()
            sub_env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=False,
                encoding='utf-8',
                errors='replace',
                env=sub_env
            )
            
            # Process the output
            output_lines = []
            found_start = False  # Track whether we've found the command start
            cleaning_in_progress = False  # Track when actual cleaning is happening
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                    
                if line:
                    clean_line = line.strip()
                    if clean_line:  # Skip empty lines
                        output_lines.append(clean_line)
                        
                        # Update status based on key phrases
                        if "Starting" in clean_line or "Cleanup" in clean_line:
                            found_start = True
                            
                        if "Found" in clean_line and "package" in clean_line:
                            cleaning_in_progress = True
                            # Update UI status with what's being cleaned
                            model_info = clean_line.split("Found")[1].strip() if "Found" in clean_line else "models"
                            self._send_update(ACTION_STATUS, f"Cleaning ANPE models: {model_info}...")
                            
                        if "Removing" in clean_line:
                            cleaning_in_progress = True
                            # Extract what's being removed for status update
                            model_info = clean_line.split("Removing")[1].strip() if "Removing" in clean_line else "models"
                            self._send_update(ACTION_STATUS, f"Removing model: {model_info}...")
                            
                        # Log the output
                        self._log(f"Model cleanup: {clean_line}")
            
            # Wait for the process to complete
            return_code = process.wait()
            
            # If no start messages were found, the command might have failed silently
            if not found_start and len(output_lines) < 2:
                return False, "ANPE model cleanup command didn't produce expected output. It may not have executed properly."
                
            if return_code == 0:
                if not cleaning_in_progress and len(output_lines) < 3:
                    # No models needed cleaning - this is a success case
                    return True, "ANPE model cleanup completed - no models needed to be removed."
                else:
                    return True, "ANPE model cleanup completed successfully."
            else:
                return False, f"ANPE model cleanup failed with return code {return_code}. See log for details."
                
        except Exception as e:
            error_details = traceback.format_exc()
            error_message = f"Error during model cleanup: {e}\n{error_details}"
            self._log(error_message)
            return False, f"Failed to clean ANPE models: {e}"

# --- Main Application Window (Tkinter) ---
class UninstallMainWindow(tk.Tk):
    """Main Tkinter application window."""
    def __init__(self):
        super().__init__()
        self._worker_thread: Optional[UninstallWorker] = None
        self._output_queue = queue.Queue()
        self._is_running = False
        self._install_path: Optional[str] = None # Added to store install path
        self._remove_models: bool = True  # Default value, will be updated

        self._setup_window()
        self._setup_styles()
        self._create_widgets()
        self._check_queue() # Start polling the queue

    def _setup_window(self):
        self.title(f"{APP_NAME} Uninstaller")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        center_window(self)
        # Use custom close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use('vista')
        except tk.TclError:
            print("Warning: 'vista' theme not available. Using default.", file=sys.stderr)
        try:
            self.default_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            self.title_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
        except tk.TclError:
            print(f"Warning: Font '{PRIMARY_FONT_FAMILY}' not found. Using '{FALLBACK_FONT_FAMILY}'.", file=sys.stderr)
            self.default_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            self.title_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
        self.style.configure('.', font=self.default_font, background=LIGHT_BG_COLOR)
        self.style.configure("TFrame", background=LIGHT_BG_COLOR)
        self.style.configure("TLabel", background=LIGHT_BG_COLOR, foreground="#333333", padding=0)
        self.style.configure("Title.TLabel", font=self.title_font, foreground=PRIMARY_COLOR, padding=(0, PADDING // 2))
        self.style.configure("Subtitle.TLabel", font=self.subtitle_font, foreground=SECONDARY_TEXT_COLOR, padding=(0, PADDING // 4))
        self.style.configure("Secondary.TLabel", foreground=SECONDARY_TEXT_COLOR)
        self.style.configure("Error.TLabel", foreground=ERROR_COLOR)
        self.style.configure("Warning.TLabel", foreground=WARNING_COLOR)
        self.style.configure("Success.TLabel", foreground=SUCCESS_COLOR)
        self.style.configure("Info.TLabel", foreground=INFO_COLOR)
        self.style.configure("TLabelframe", background=LIGHT_BG_COLOR)
        self.style.configure("TLabelframe.Label", background=LIGHT_BG_COLOR, font=self.default_font)
        self.style.configure("TProgressbar", thickness=20, background=BORDER_COLOR, troughcolor=LIGHT_BG_COLOR)
        self.style.configure("TButton", font=self.default_font, padding=(PADDING, PADDING // 2))
        self.style.configure("PathBrowse.TButton", padding=(10, 4))  # Adjusted padding for height
        self.style.configure("PathLabel.TLabel", 
                           font=(PRIMARY_FONT_FAMILY, SMALL_FONT_SIZE, "italic"),
                           foreground=SECONDARY_TEXT_COLOR,
                           background=LIGHT_BG_COLOR)

    def _create_widgets(self):
        """Create and layout the main container and frames."""
        self.main_container = ttk.Frame(self, padding=0, style="TFrame")
        self.main_container.pack(expand=True, fill="both")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.frames = {}
        for F, name in [(WelcomeFrame, VIEW_WELCOME),
                        (ProgressFrame, VIEW_PROGRESS),
                        (CompletionFrame, VIEW_COMPLETION)]:
            if name == VIEW_WELCOME:
                frame = F(self.main_container, start_uninstall_callback=self._start_uninstall, style="TFrame")
            elif name == VIEW_COMPLETION:
                frame = F(self.main_container, close_callback=self._on_close, style="TFrame")
            else:
                frame = F(self.main_container, style="TFrame")
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        self._switch_view(VIEW_WELCOME)

    def _switch_view(self, view_name: str):
        """Bring the specified view frame to the top."""
        frame = self.frames.get(view_name)
        if frame:
            frame.tkraise()
        else:
            print(f"Error: View '{view_name}' not found.", file=sys.stderr)

    def _start_uninstall(self, install_path: str, remove_models: bool = True):
        """Initiate the uninstallation process in a worker thread."""
        if self._is_running:
            messagebox.showwarning("In Progress", "Uninstallation is already running.")
            return

        try:
            # Ensure progress frame exists before trying to reset
            progress_frame = self.frames.get(VIEW_PROGRESS)
            if not progress_frame:
                raise RuntimeError("Progress frame not found during uninstall start.")

            self._worker_thread = UninstallWorker(install_path, self._output_queue, remove_models)
            self._is_running = True
            self._install_path = install_path # Store the install path
            self._remove_models = remove_models  # Store for potential future use
            progress_frame.reset_progress() # Reset UI before switching
            self._switch_view(VIEW_PROGRESS)
            self._worker_thread.start()

        except ValueError as e: # Catch specific error from worker init
            messagebox.showerror("Error", f"Failed to start uninstaller: {e}")
            self._is_running = False # Ensure state is reset
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred while starting the uninstallation: {e}")
            traceback.print_exc() # Log detailed error
            self._is_running = False

    def _check_queue(self):
        """Periodically check the queue for updates from the worker."""
        try:
            while True: # Process all messages currently in queue
                action, data = self._output_queue.get_nowait()
                self._process_worker_update(action, data)
        except queue.Empty:
            pass # No messages currently
        except Exception as e:
            # Log unexpected error during queue processing
            print(f"Error processing worker queue: {e}")
            traceback.print_exc()
        finally:
            # Schedule the next check, always
            self.after(100, self._check_queue)

    def _process_worker_update(self, action: str, data: Any):
        """Process a message received from the worker thread."""
        progress_frame = self.frames.get(VIEW_PROGRESS)
        completion_frame = self.frames.get(VIEW_COMPLETION)

        # Ensure frames exist before updating them
        if not progress_frame or not completion_frame:
            print("Error: UI frames not ready to process worker update.", file=sys.stderr)
            return

        try:
            if action == ACTION_STATUS:
                progress_frame.set_status(data)
            elif action == ACTION_LOG:
                progress_frame.append_log(data)
            elif action == ACTION_PROGRESS:
                current, total = data
                progress_frame.set_progress(current, total)
            elif action == ACTION_FINISHED:
                self._is_running = False # Mark process as finished
                success, message, full_log, log_path = data
                completion_frame.set_state(success, message, full_log, log_path)
                self._switch_view(VIEW_COMPLETION)
            else:
                print(f"Warning: Unknown action from worker: {action}", file=sys.stderr)
        except tk.TclError as e:
            # Catch errors if widgets are destroyed during update (e.g., rapid close)
            print(f"Tkinter error processing worker update ({action}): {e}")
        except Exception as e:
            # Catch any other unexpected errors during UI update
            print(f"Error processing worker update ({action}): {e}")
            traceback.print_exc()

    def _on_close(self):
        """Handle window close event (WM_DELETE_WINDOW)."""
        if self._is_running:
            if messagebox.askyesno("Confirm Exit",
                                   "Uninstallation is in progress. Are you sure you want to exit?\n" + \
                                   "This may leave the uninstallation incomplete.",
                                   default=messagebox.NO):
                # Worker is daemon, will exit when main thread exits.
                # No explicit termination needed/safe.
                self.destroy()
            # else: User selected No, do nothing
        else:
            # Not running, attempt self-destruction before closing
            if self._install_path:
                try:
                    uninstaller_exe_path = os.path.join(self._install_path, "uninstall.exe")
                    install_dir_path = self._install_path
                    
                    # Check if user wants to keep logs 
                    should_keep_logs = False
                    completion_frame = self.frames.get(VIEW_COMPLETION)
                    if completion_frame and hasattr(completion_frame, 'keep_logs_var'):
                        should_keep_logs = completion_frame.keep_logs_var.get()
                        print(f"Log preservation choice: Keep logs = {should_keep_logs}")

                    if os.path.exists(uninstaller_exe_path):
                        print(f"Attempting self-destruction for: {uninstaller_exe_path}")
                        
                        if should_keep_logs:
                            # Just delete the uninstaller executable, keep the logs
                            cmd = f'cmd.exe /c "timeout /t 1 /nobreak > nul && del /f /q "{uninstaller_exe_path}""'
                            print("Keeping logs, only deleting uninstaller executable.")
                        else:
                            # Delete uninstaller and remove the entire directory
                            cmd = f'cmd.exe /c "timeout /t 1 /nobreak > nul && del /f /q "{uninstaller_exe_path}" && rmdir /s /q "{install_dir_path}""'
                            print("Not keeping logs, removing entire installation directory.")
                        
                        # DETACHED_PROCESS allows the parent (uninstaller) to exit immediately
                        # CREATE_NO_WINDOW hides the command prompt window
                        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                        subprocess.Popen(cmd, creationflags=creation_flags, shell=False)
                        print("Self-destruction process launched.")
                    else:
                        print("Uninstaller executable not found, skipping self-destruction.")
                        
                        # If uninstaller.exe not found but we still want to delete the directory
                        if not should_keep_logs and os.path.exists(install_dir_path):
                            cmd = f'cmd.exe /c "timeout /t 1 /nobreak > nul && rmdir /s /q "{install_dir_path}""'
                            creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                            subprocess.Popen(cmd, creationflags=creation_flags, shell=False)
                            print("Removing installation directory.")
                except Exception as e:
                    print(f"Error launching self-destruction process: {e}")
                    # Log error, but proceed with closing

            # Not running, close immediately
            self.destroy()


# --- Tkinter UI Frames (New) ---
class WelcomeFrame(ttk.Frame):
    """Welcome screen frame."""
    def __init__(self, parent, start_uninstall_callback: Callable[[str, bool], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.start_uninstall_callback = start_uninstall_callback
        self.install_path: Optional[str] = None
        self.manual_path_selected = False
        self.path_status_text = ""
        self.path_status_style = "Secondary.TLabel"
        self.remove_models_var = tk.BooleanVar(value=True)  # Default to True (checked)

        self._setup_styles()  # Set up styles FIRST
        self._setup_ui()      # Then set up UI components
        self.update_install_path() # Initial check

    def _setup_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use('vista')
        except tk.TclError:
            print("Warning: 'vista' theme not available. Using default.", file=sys.stderr)
        try:
            self.default_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            self.title_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
            self.status_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=SUBTITLE_FONT_SIZE-1, slant="italic")
        except tk.TclError:
            print(f"Warning: Font '{PRIMARY_FONT_FAMILY}' not found. Using '{FALLBACK_FONT_FAMILY}'.", file=sys.stderr)
            self.default_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            self.title_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
            self.status_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=SUBTITLE_FONT_SIZE-1, slant="italic")

        self.style.configure('.', font=self.default_font, background=LIGHT_BG_COLOR)
        self.style.configure("TFrame", background=LIGHT_BG_COLOR)
        self.style.configure("TLabel", background=LIGHT_BG_COLOR, foreground="#333333", padding=0)
        self.style.configure("Title.TLabel", font=self.title_font, foreground=PRIMARY_COLOR, padding=(0, PADDING // 2))
        self.style.configure("Subtitle.TLabel", font=self.subtitle_font, foreground=SECONDARY_TEXT_COLOR, padding=(0, PADDING // 4))
        self.style.configure("Status.TLabel", font=self.status_font, foreground=SECONDARY_TEXT_COLOR)
        self.style.configure("Secondary.TLabel", foreground=SECONDARY_TEXT_COLOR)
        self.style.configure("Error.TLabel", foreground=ERROR_COLOR)
        self.style.configure("Warning.TLabel", foreground=WARNING_COLOR)
        self.style.configure("Success.TLabel", foreground=SUCCESS_COLOR)
        self.style.configure("Info.TLabel", foreground=INFO_COLOR)
        self.style.configure("TLabelframe", background=LIGHT_BG_COLOR)
        self.style.configure("TLabelframe.Label", background=LIGHT_BG_COLOR, font=self.default_font)
        self.style.configure("TProgressbar", thickness=20, background=BORDER_COLOR, troughcolor=LIGHT_BG_COLOR)
        self.style.configure("TButton", font=self.default_font, padding=(PADDING, PADDING // 2))

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)
        
        # Center container frame
        center_container = ttk.Frame(self, style="TFrame")
        center_container.grid(row=0, column=0, sticky="nsew")
        center_container.columnconfigure(0, weight=1)
        
        # Spacer at top (pushes content down slightly)
        ttk.Frame(center_container, style="TFrame").grid(row=0, column=0, pady=PADDING)

        # Logo Frame
        logo_frame = ttk.Frame(center_container, style="TFrame")
        logo_frame.grid(row=1, column=0, pady=(0, PADDING//2))
        
        # Logo Label (centered)
        self.logo_label = ttk.Label(logo_frame, style="TLabel")
        self.logo_image = get_logo_image(LOGO_SIZE)
        if self.logo_image:
            self.logo_label.config(image=self.logo_image)
            self.logo_label.image = self.logo_image
        self.logo_label.pack(anchor="center")

        # Title (centered)
        title_label = ttk.Label(
            center_container,
            text=f"{APP_NAME} Uninstaller",
            style="Title.TLabel",
            anchor="center"
        )
        title_label.grid(row=2, column=0, pady=(0, PADDING))

        # Welcome Text (centered)
        welcome_text = ttk.Label(
            center_container,
            text=(f"This will uninstall {APP_NAME} and its components from your computer. "
                  f"The uninstaller will remove {APP_NAME} application files and registry entries, "
                  f"but will not affect other Python installations or your personal files. "
                  f"Please ensure {APP_NAME} is not running before proceeding."),
            style="Subtitle.TLabel",
            wraplength=WINDOW_WIDTH - 6 * PADDING,  # Adjusted for wider window
            anchor="center",
            justify="center"
        )
        welcome_text.grid(row=3, column=0, pady=(0, PADDING * 2), padx=PADDING * 2)
        welcome_text.configure(font=(PRIMARY_FONT_FAMILY, SMALL_FONT_SIZE))  # Made even smaller

        # Path Section Frame - Make it full width
        path_section = ttk.Frame(center_container, style="TFrame")
        path_section.grid(row=4, column=0, pady=(0, PADDING), padx=PADDING * 2, sticky="ew")
        path_section.columnconfigure(0, weight=1)  # Make the frame expand horizontally

        # Path Label (left aligned, italic, smaller)
        path_label = ttk.Label(
            path_section,
            text="Uninstall ANPE from:",
            style="PathLabel.TLabel",
            anchor="w"
        )
        path_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Path Entry and Browse Button Frame
        path_entry_frame = ttk.Frame(path_section, style="TFrame")
        path_entry_frame.grid(row=1, column=0, sticky="ew")
        path_entry_frame.columnconfigure(0, weight=1)  # Make entry expand
        path_entry_frame.columnconfigure(1, weight=0)  # Don't expand browse button

        # Configure entry style for consistent height
        entry_height = 26  # Match button height
        entry_pady = (entry_height - DEFAULT_FONT_SIZE - 6) // 2  # Calculate padding to center text

        # Path Entry with fixed height through padding
        self.path_entry = ttk.Entry(  # Changed to ttk.Entry for consistent styling
            path_entry_frame,
            font=(PRIMARY_FONT_FAMILY, DEFAULT_FONT_SIZE),
            style="Path.TEntry"  # Use custom style
        )
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # Configure style for the entry
        self.style.configure("Path.TEntry",
            padding=(5, entry_pady),  # Horizontal and vertical padding
            selectbackground=PRIMARY_COLOR,
            fieldbackground=INPUT_BG_COLOR
        )

        # Browse Button with matching height and fixed width
        self.browse_button = ttk.Button(
            path_entry_frame,
            text="Browse...",
            command=self._browse_for_path,
            width=12,  # Fixed width in characters
            style="PathBrowse.TButton"
        )
        self.browse_button.grid(row=0, column=1, sticky="e")  # Changed column to 1

        # Path Status Label (centered, italic)
        self.path_status_label = ttk.Label(
            path_section,
            text="",
            style="Status.TLabel",
            anchor="center"
        )
        self.path_status_label.grid(row=2, column=0, sticky="ew", pady=(5, 0))

        # Add checkbox for model removal
        model_cleanup_frame = ttk.Frame(center_container, style="TFrame")
        model_cleanup_frame.grid(row=5, column=0, pady=(0, PADDING), padx=PADDING * 2, sticky="ew")

        # Model cleanup checkbox
        self.remove_models_checkbox = ttk.Checkbutton(
            model_cleanup_frame,
            text="Remove ANPE-related models (spaCy and benepar models)",
            variable=self.remove_models_var,
            style="TCheckbutton"
        )
        self.remove_models_checkbox.grid(row=0, column=0, sticky="w")

        # Bottom Button Frame (centered)
        button_frame = ttk.Frame(center_container, style="TFrame")
        button_frame.grid(row=6, column=0, pady=PADDING * 2, sticky="ew")
        button_frame.columnconfigure(0, weight=1)  # Enable centering

        # Uninstall button with fixed width
        self.uninstall_button = ttk.Button(
            button_frame,
            text="Uninstall",
            command=self._on_uninstall_click,
            width=15  # Fixed width for better appearance
        )
        self.uninstall_button.grid(row=0, column=0)  # Use grid instead of pack
        set_widget_state(self.uninstall_button, "disabled")  # Disabled initially

    def _get_install_path_from_registry(self) -> Optional[str]:
        """Get the installation path from the registry."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH, 0, winreg.KEY_READ) as reg_key:
                install_path, _ = winreg.QueryValueEx(reg_key, REGISTRY_INSTALL_LOCATION_VALUE)
            if install_path and os.path.isdir(install_path):
                return os.path.normpath(install_path)
            else:
                print(f"Registry path found but invalid: {install_path}", file=sys.stderr)
                return None
        except FileNotFoundError:
            # This is expected if the app isn't installed, don't spam console
            # print(f"Registry key '{REGISTRY_KEY_PATH}' not found.", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error reading registry: {e}", file=sys.stderr)
            return None

    def update_install_path(self, manual_path: Optional[str] = None):
        """Check registry or use manual path, then update UI."""
        path_to_use = manual_path if manual_path else self._get_install_path_from_registry()

        if path_to_use:
            self.install_path = path_to_use
            self.manual_path_selected = bool(manual_path)
            
            # Update path entry with detected path and make it read-only
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, self.install_path)
            
            # Make the entry read-only (state=readonly doesn't work well with styling)
            # Instead, bind events to prevent modification
            self.path_entry.bind("<Key>", lambda e: "break" if e.keysym not in ("c", "C") or not (e.state & 4) else None)  # Allow Ctrl+C
            
            # Update status label based on source and validation
            if self.manual_path_selected:
                is_likely_anpe, _ = self._is_likely_anpe_installation(path_to_use)
                if is_likely_anpe:
                    self.path_status_text = "✓ Manually selected - Appears to be an ANPE installation"
                    self.path_status_style = "Success.TLabel"
                else:
                    self.path_status_text = "⚠ Manually selected - Unlikely to be an ANPE installation"
                    self.path_status_style = "Warning.TLabel"
            else:
                self.path_status_text = "✓ Automatically detected from registry"
                self.path_status_style = "Info.TLabel"
                
            self.path_status_label.config(text=self.path_status_text, style=self.path_status_style)
            set_widget_state(self.uninstall_button, "normal")
        else:
            self.install_path = None
            self.manual_path_selected = False
            
            # Clear entry and make it writable
            self.path_entry.delete(0, tk.END)
            self.path_entry.unbind("<Key>")  # Allow typing for manual path entry
            
            # Update status label
            self.path_status_text = "Installation path not found. Use 'Browse...' to select it manually."
            self.path_status_style = "Error.TLabel"
            self.path_status_label.config(text=self.path_status_text, style=self.path_status_style)
            set_widget_state(self.uninstall_button, "disabled")

    def _browse_for_path(self):
        """Open directory dialog for manual path selection."""
        try:
            initial_dir = self.path_entry.get().strip() or os.path.expanduser("~")
        except:
            initial_dir = os.path.expanduser("~")
            
        selected_path = filedialog.askdirectory(title=f"Select {APP_NAME} Installation Directory", initialdir=initial_dir)
        if selected_path and os.path.isdir(selected_path):
            # Update the UI with the manually selected path
            self.update_install_path(manual_path=os.path.normpath(selected_path))
        elif selected_path:
            messagebox.showerror("Invalid Selection", f"The selected path is not a valid directory:\n{selected_path}")
            # If the browse resulted in an error, revert state (re-check registry)
            self.update_install_path()
        # If dialog cancelled, do nothing, keep previous state.

    def _is_likely_anpe_installation(self, path: str) -> tuple[bool, list]:
        """
        Check if the given path appears to be an ANPE installation.
        Returns a tuple of (is_likely_anpe, file_list)
        """
        if not os.path.isdir(path):
            return (False, [])
            
        expected_anpe_files = [
            "anpe.exe", 
            "uninstall.exe"
        ]
        expected_anpe_dirs = [
            "anpe_studio",
            "python"
        ]
        
        items = []
        try:
            items = os.listdir(path)
        except (PermissionError, OSError):
            # If we can't access the directory, we can't tell
            return (False, [])
            
        # Check for key ANPE files/directories
        anpe_indicators_found = 0
        for item in expected_anpe_files:
            if item in items and os.path.isfile(os.path.join(path, item)):
                anpe_indicators_found += 1
                
        for item in expected_anpe_dirs:
            if item in items and os.path.isdir(os.path.join(path, item)):
                anpe_indicators_found += 1
                
        # If we found at least 2 indicators, it's likely an ANPE installation
        # Return both the result and the file list for showing the user
        return (anpe_indicators_found >= 2, items)

    def _on_uninstall_click(self):
        """Handle uninstall button click, confirming if path was manual."""
        if not self.install_path:
            # Try to get path from entry if install_path is not set
            entered_path = self.path_entry.get().strip()
            if entered_path and os.path.isdir(entered_path):
                self.install_path = entered_path
                self.manual_path_selected = True
            else:
                messagebox.showerror("Error", "No valid installation path specified.")
                return

        # Check if ANPE Studio is running before proceeding
        is_running, running_processes = check_anpe_running(self.install_path)
        if is_running:
            process_details = "\n".join(running_processes[:5])  # Show up to 5 processes
            if len(running_processes) > 5:
                process_details += f"\n... and {len(running_processes) - 5} more"
                
            error_message = (
                f"ANPE Studio is currently running. Please close the application before uninstalling.\n\n"
                f"Running processes found:\n{process_details}"
            )
            messagebox.showerror("Cannot Uninstall", error_message)
            return

        # First level check - is it manually selected?
        if self.manual_path_selected:
            # Additional safety check for manually selected paths
            is_anpe, file_list = self._is_likely_anpe_installation(self.install_path)
            
            if not is_anpe:
                # Format file list for display, limit to reasonable length
                formatted_files = "\n".join(file_list[:15])
                if len(file_list) > 15:
                    formatted_files += f"\n... and {len(file_list) - 15} more files/folders"
                
                unsafe_message = (
                    f"⚠️ WARNING: The directory you selected does NOT appear to be an ANPE installation!\n\n"
                    f"Path: {self.install_path}\n\n"
                    f"Directory contents:\n{formatted_files}\n\n"
                    f"Continuing with uninstallation may DELETE DATA UNRELATED TO ANPE.\n\n"
                    f"Are you ABSOLUTELY SURE you want to delete these files?"
                )
                
                proceed = messagebox.askyesno(
                    "⚠️ DANGEROUS OPERATION", 
                    unsafe_message,
                    default=messagebox.NO, 
                    icon=messagebox.WARNING
                )
                
                if not proceed:
                    return
                    
            # Normal manual path warning (shown even if it looks like ANPE)
            confirm_msg = f"WARNING: You manually selected the installation path:\n{self.install_path}\n\nUninstalling from the wrong directory can damage other applications or your system.\n\nARE YOU ABSOLUTELY SURE you want to proceed?"
            confirm_title = "Confirm Manual Path Uninstall"
            
            proceed = messagebox.askyesno(confirm_title, confirm_msg, default=messagebox.NO, icon=messagebox.WARNING)
            
            if not proceed:
                return
        else:
            # Standard confirmation for registry-detected paths
            confirm_msg = f"Are you sure you want to uninstall {APP_NAME} from:\n{self.install_path}?\n\nThis action cannot be undone."
            confirm_title = "Confirm Uninstall"
            
            proceed = messagebox.askyesno(confirm_title, confirm_msg, default=messagebox.NO, icon=messagebox.QUESTION)
            
            if not proceed:
                return

        self.start_uninstall_callback(self.install_path, self.remove_models_var.get())

    def _load_logo_image(self, size: Tuple[int, int]) -> Optional[tk.PhotoImage]:
        """Load the logo image using the base64 encoded data."""
        return get_logo_image(size)


class ProgressFrame(ttk.Frame):
    """Progress display frame."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_styles()  # Set up styles before UI
        self._setup_ui()
        
    def _setup_styles(self):
        try:
            self.title_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
        except tk.TclError:
            self.title_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
        
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=self.title_font, foreground=PRIMARY_COLOR, padding=(0, PADDING // 2))
        style.configure("Subtitle.TLabel", font=self.subtitle_font, foreground=SECONDARY_TEXT_COLOR, padding=(0, PADDING // 4))

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)

        # --- Header with Logo and Title (mimicking PyQt views) ---
        header_frame = ttk.Frame(self, style="TFrame")
        header_frame.grid(row=0, column=0, pady=(PADDING, PADDING // 2), padx=PADDING, sticky="ew")
        header_frame.columnconfigure(1, weight=1)  # Title column expands
        
        # Logo display (left side of header)
        self.logo_label = ttk.Label(header_frame, style="TLabel")
        self.logo_image = self._load_logo_image(LOGO_SIZE)
        if self.logo_image:
            self.logo_label.config(image=self.logo_image)
            self.logo_label.image = self.logo_image  # Keep reference
        self.logo_label.grid(row=0, column=0, padx=(0, PADDING), sticky="w")
        
        # Title in header (right side of logo)
        self.title_label = ttk.Label(
            header_frame, 
            text=f"Uninstalling {APP_NAME}...", 
            style="Title.TLabel", 
            anchor="w"
        )
        self.title_label.grid(row=0, column=1, sticky="w")

        # Status Label (as subtitle)
        self.status_label = ttk.Label(self, text="Initializing...", style="Subtitle.TLabel", anchor="w", justify="left")
        self.status_label.grid(row=1, column=0, pady=(0, PADDING // 2), padx=PADDING, sticky="w")

        # Progress Bar
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate", length=WINDOW_WIDTH - 2 * PADDING)
        self.progress_bar.grid(row=2, column=0, pady=PADDING // 2, padx=PADDING, sticky="ew")

        # Log Area (ScrolledText)
        self.log_text = scrolledtext.ScrolledText(
            self, 
            height=10, 
            width=70,  # Add width parameter for wider window
            wrap=tk.WORD, 
            state="disabled", 
            relief="solid", 
            bd=1, 
            bg=LOG_BG_COLOR_PROGRESS,
            font=(PRIMARY_FONT_FAMILY, DEFAULT_FONT_SIZE -1)
        ) # Slightly smaller font for logs
        self.log_text.grid(row=3, column=0, pady=(PADDING // 2, PADDING), padx=PADDING, sticky="nsew")
        self.rowconfigure(3, weight=1) # Allow log area to expand vertically

        # Configure styles for log text tags
        self.log_text.tag_config("ERROR", foreground=ERROR_COLOR)
        self.log_text.tag_config("WARNING", foreground="#FFA000") # Orange-like
        self.log_text.tag_config("INFO", foreground=SECONDARY_TEXT_COLOR)
        self.log_text.tag_config("DEBUG", foreground="#888888")

    def reset_progress(self):
        """Reset progress bar and log."""
        self.set_status("Initializing...")
        self.set_progress(0, 1) # Initial state
        set_widget_state(self.log_text, "normal")
        self.log_text.delete("1.0", tk.END)
        set_widget_state(self.log_text, "disabled")

    def set_status(self, status: str):
        """Update the status label text."""
        if self.winfo_exists():
            self.status_label.config(text=status)

    def set_progress(self, current_step: int, total_steps: int):
        """Update the progress bar value."""
        if self.winfo_exists():
            if total_steps > 0:
                percentage = (current_step / total_steps) * 100
                self.progress_bar['value'] = percentage
            else:
                self.progress_bar['value'] = 0

    def append_log(self, message: str):
        """Append a message to the log area, applying tags."""
        if not self.winfo_exists(): return

        set_widget_state(self.log_text, "normal")
        tag = "INFO"
        if message.startswith("ERROR") or message.startswith("[Log Write Error]"):
            tag = "ERROR"
        elif message.startswith("WARNING"):
            tag = "WARNING"
        elif message.startswith("DEBUG"):
             tag = "DEBUG"
        # Add more conditions for other log levels if needed

        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END) # Auto-scroll
        set_widget_state(self.log_text, "disabled")

    def _load_logo_image(self, size: Tuple[int, int]) -> Optional[tk.PhotoImage]:
        """Load the logo image using the base64 encoded data."""
        return get_logo_image(size)


class CompletionFrame(ttk.Frame):
    """Completion screen frame."""
    def __init__(self, parent, close_callback: Callable[[], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.close_callback = close_callback
        self._full_log_content: Optional[str] = None
        self._log_path: Optional[str] = None  # Add this to store log path
        self._install_path: Optional[str] = None  # Add this to store install path
        self._setup_styles()
        self._setup_ui()

    def _setup_styles(self):
        try:
            self.title_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=PRIMARY_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
        except tk.TclError:
            self.title_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
            self.subtitle_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=SUBTITLE_FONT_SIZE)
        
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=self.title_font, foreground=PRIMARY_COLOR, padding=(0, PADDING // 2))
        style.configure("Success.Title.TLabel", font=self.title_font, foreground=SUCCESS_COLOR, padding=(0, PADDING // 2))
        style.configure("Error.Title.TLabel", font=self.title_font, foreground=ERROR_COLOR, padding=(0, PADDING // 2))
        style.configure("Subtitle.TLabel", font=self.subtitle_font, foreground=SECONDARY_TEXT_COLOR, padding=(0, PADDING // 4))

    def _setup_ui(self):
        # Configure grid weights to make content expand but keep bottom fixed
        self.columnconfigure(0, weight=1)
        
        # Create main content frame that will expand
        main_content = ttk.Frame(self, style="TFrame")
        main_content.grid(row=0, column=0, sticky="nsew")
        main_content.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)  # Allow main content to expand

        # --- Header with Logo and Title ---
        header_frame = ttk.Frame(main_content, style="TFrame")
        header_frame.grid(row=0, column=0, pady=(PADDING, PADDING // 2), padx=PADDING, sticky="ew")
        header_frame.columnconfigure(1, weight=1)
        
        # Logo display
        self.logo_label = ttk.Label(header_frame, style="TLabel")
        self.logo_image = self._load_logo_image(LOGO_SIZE)
        if self.logo_image:
            self.logo_label.config(image=self.logo_image)
            self.logo_label.image = self.logo_image
        self.logo_label.grid(row=0, column=0, padx=(0, PADDING), sticky="w")
        
        # Title
        self.title_label = ttk.Label(header_frame, text="Uninstallation Complete", style="Title.TLabel", anchor="w")
        self.title_label.grid(row=0, column=1, sticky="w")

        # Message Label
        self.message_label = ttk.Label(main_content, text="", style="Subtitle.TLabel", 
                                     wraplength=WINDOW_WIDTH - 3 * PADDING, anchor="w", justify="left")
        self.message_label.grid(row=1, column=0, pady=(0, PADDING // 2), padx=PADDING, sticky="w")

        # Details button frame
        details_button_frame = ttk.Frame(main_content, style="TFrame")
        details_button_frame.grid(row=2, column=0, pady=(0, PADDING // 2), padx=PADDING, sticky="w")

        self.details_button = ttk.Button(details_button_frame, text="Show Details", command=self._toggle_details)
        self.details_button.grid(row=0, column=0)
        set_widget_state(self.details_button, "disabled")

        # Log Area (ScrolledText, initially not gridded)
        self.log_text = scrolledtext.ScrolledText(
            main_content, 
            height=12,
            width=70,  # Increased width for wider window
            wrap=tk.WORD, 
            state="disabled",
            relief="solid",
            bd=1,
            bg=LOG_BG_COLOR_COMPLETION,
            font=(PRIMARY_FONT_FAMILY, DEFAULT_FONT_SIZE - 1)
        )

        # Bottom section frame - no separator, just padding
        bottom_frame = ttk.Frame(self, style="TFrame")
        bottom_frame.grid(row=1, column=0, sticky="sew", pady=(PADDING, 0))
        bottom_frame.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)  # Don't allow bottom frame to expand

        # Controls container with padding
        controls_frame = ttk.Frame(bottom_frame, style="TFrame")
        controls_frame.grid(row=0, column=0, padx=PADDING, pady=(0, PADDING), sticky="sw")
        
        # Checkbox
        self.keep_logs_var = tk.BooleanVar(value=True)
        self.keep_logs_checkbox = ttk.Checkbutton(
            controls_frame,
            text="Keep uninstallation log file",
            variable=self.keep_logs_var,
            style="TCheckbutton"
        )
        self.keep_logs_checkbox.grid(row=0, column=0, sticky="w", pady=(0, PADDING//2))
        
        # Close Button
        self.close_button = ttk.Button(controls_frame, text="Close", command=self._on_close)
        self.close_button.grid(row=1, column=0, sticky="w")

    def _toggle_details(self):
        """Show or hide the detailed log."""
        if self.log_text.winfo_ismapped(): # Check if gridded (visible)
            self._hide_details()
        else:
            self._show_details()

    def _show_details(self):
        """Show the detailed log."""
        if not self._full_log_content or not self.winfo_exists():
            return
        # Place the log text widget above the bottom frame
        self.log_text.grid(row=3, column=0, pady=(0, PADDING//2), padx=PADDING, sticky="nsew")
        self.rowconfigure(3, weight=1)
        set_widget_state(self.log_text, "normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, self._full_log_content)
        set_widget_state(self.log_text, "disabled")
        self.details_button.config(text="Hide Details")
        self.update_idletasks()

    def _hide_details(self):
        """Hide the detailed log."""
        if not self.winfo_exists():
            return
        self.log_text.grid_forget()
        self.rowconfigure(3, weight=0)
        self.details_button.config(text="Show Details")
        self.update_idletasks()

    def _on_close(self):
        """Handle window close button click."""
        # Call the provided close callback which handles all the cleanup logic
        self.close_callback()

    def set_state(self, success: bool, final_message: str, full_log: str, log_path: Optional[str] = None):
        """Set the final state of the completion screen."""
        if not self.winfo_exists():
            return

        self._full_log_content = full_log
        self._log_path = log_path  # Store the log path
        
        # Extract install path from log_path if available
        if log_path:
            self._install_path = os.path.dirname(os.path.dirname(log_path))

        if success:
            self.title_label.config(text="Uninstallation Complete", style="Success.Title.TLabel")
            self.message_label.config(text=f"{APP_NAME} has been successfully uninstalled.")
        else:
            self.title_label.config(text="Uninstallation Failed", style="Error.Title.TLabel")
            error_text = f"An error occurred during uninstallation."
            # Use the final_message from worker if available and specific
            if final_message and "unexpected error occurred" not in final_message.lower():
                 error_text += f"\n\nDetails: {final_message}"
            elif final_message:
                 # Generic error message if worker had unexpected exception
                 error_text += " Please check the logs for more details."

            self.message_label.config(text=error_text)

        # Enable the details button only if there's log content
        if self._full_log_content:
            set_widget_state(self.details_button, "normal")
        else:
            set_widget_state(self.details_button, "disabled")

        # Ensure log is hidden initially
        self._hide_details()

    def _load_logo_image(self, size: Tuple[int, int]) -> Optional[tk.PhotoImage]:
        """Load the logo image using the base64 encoded data."""
        return get_logo_image(size)


# --- Tkinter main ---
def main():
    """Main entry point for the uninstaller GUI."""
    # Only redirect stdout/stderr if running with pythonw.exe
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_file = None

    try:
        if "pythonw.exe" in sys.executable.lower():
            log_dir_fallback = os.path.join(os.path.expanduser("~"), "AppData", "Local", APP_NAME, "Logs")
            os.makedirs(log_dir_fallback, exist_ok=True)
            log_file = open(os.path.join(log_dir_fallback, "uninstaller_gui_errors.log"), "a", encoding='utf-8')
            sys.stdout = log_file
            sys.stderr = log_file
            print(f"--- {APP_NAME} Uninstaller GUI Started ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")

        try:
            app = UninstallMainWindow()
            app.mainloop()
        except Exception as e:
            print("--- Uninstaller GUI FATAL ERROR ---")
            traceback.print_exc()
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, 
                    f"A critical error occurred in the uninstaller GUI: {e}\nSee logs for details.", 
                    f"{APP_NAME} Uninstaller Error", 
                    0x10 | 0x0)
            except Exception:
                pass
    finally:
        # Restore original streams before exiting
        if "pythonw.exe" in sys.executable.lower():
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            if log_file:
                try:
                    log_file.close()
                except:
                    pass

if __name__ == "__main__":
    main() 