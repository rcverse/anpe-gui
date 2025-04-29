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
from tkinter import ttk, messagebox, filedialog, scrolledtext, font as tkFont # Added
from typing import Optional, Tuple, Callable, Any # Added

# Removed PyQt6 imports
# from PyQt6.QtWidgets import (
#     QApplication, QMainWindow, QStackedWidget, QWidget, QMessageBox, 
#     QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QLabel, QSpacerItem, QSizePolicy
# )
# from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
# from PyQt6.QtGui import QColor, QPixmap

# --- Remove old shared component imports (assuming Tkinter replacements) ---
# try:
#     from .widgets.custom_title_bar import CustomTitleBar
#     from .views.progress_view import ProgressViewWidget
#     from .utils import get_resource_path
#     from .styles import (...)
# except ImportError as e:
#     print(f"ERROR: Could not import shared components: {e}", file=sys.stderr)
#     sys.exit("Uninstaller cannot run without shared components.")


# --- Constants ---
APP_NAME = "ANPE"
REGISTRY_KEY_PATH = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
REGISTRY_INSTALL_LOCATION_VALUE = "InstallLocation"
REGISTRY_SHORTCUT_LOCATION_VALUE = "ShortcutLocation"

# UI Constants
WINDOW_WIDTH = 550
WINDOW_HEIGHT = 400
PADDING = 15
PRIMARY_FONT_FAMILY = "Segoe UI"
FALLBACK_FONT_FAMILY = "Arial" # Use a common fallback
DEFAULT_FONT_SIZE = 10
TITLE_FONT_SIZE = 16

# Colors
LIGHT_BG_COLOR = "#FFFFFF"
PRIMARY_COLOR = "#005A9C" # ANPE Blue
SECONDARY_TEXT_COLOR = "#555555"
ERROR_COLOR = "#D32F2F"
SUCCESS_COLOR = "#388E3C"
BORDER_COLOR = "#CCCCCC"

# Worker Communication Actions
ACTION_STATUS = "status"
ACTION_LOG = "log"
ACTION_PROGRESS = "progress"
ACTION_FINISHED = "finished"

# View Names (for switching)
VIEW_WELCOME = "Welcome"
VIEW_PROGRESS = "Progress"
VIEW_COMPLETION = "Completion"

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

# --- (Old PyQt6 Views - To be removed/replaced) ---
# class WelcomeUninstallWidget(QWidget):
# ... (Keep commented out or remove) ...

# class CompletionUninstallWidget(QWidget):
# ... (Keep commented out or remove) ...

# --- Uninstall Worker (Adapted for Tkinter Threading) ---
class UninstallWorker(threading.Thread):
    """Worker thread to handle the actual uninstallation process."""

    def __init__(self, install_path: str, output_queue: queue.Queue):
        super().__init__(daemon=True) # Make it a daemon thread
        if not install_path or not os.path.isdir(install_path):
            raise ValueError("Invalid installation path provided to UninstallWorker.")
        self.install_path = os.path.abspath(install_path)
        self.log_dir = os.path.join(self.install_path, "logs")
        self.log_path = os.path.join(self.log_dir, "uninstall_log.txt")
        self.uninstaller_script_path = os.path.abspath(__file__)
        self.output_queue = output_queue
        self._full_log = [] # Store the full log content

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
        steps = 4
        current_step = 0
        final_message = ""
        success = True

        try:
            self._log(f"Uninstaller script path: {self.uninstaller_script_path}")
            self._log(f"Target installation directory: {self.install_path}")
            self._log(f"Log file path: {self.log_path}")

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

            # --- Step 3: Remove Installed Files and Directories ---
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

            # --- Step 4: Finalization ---
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
            self._send_update(ACTION_FINISHED, (success, final_message, full_log_content))

    # --- Core Logic Methods (Unchanged) ---
    def _remove_shortcuts(self) -> tuple[bool, str]:
        """Removes the Start Menu shortcut using registry information."""
        shortcut_path = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH, 0, winreg.KEY_READ) as reg_key:
                try:
                    shortcut_path, _ = winreg.QueryValueEx(reg_key, REGISTRY_SHORTCUT_LOCATION_VALUE)
                except FileNotFoundError:
                    return True, f"Registry value '{REGISTRY_SHORTCUT_LOCATION_VALUE}' not found. Assuming no shortcut to remove."

            if shortcut_path and os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                shortcut_dir = os.path.dirname(shortcut_path)
                try:
                    os.rmdir(shortcut_dir)
                    return True, f"Shortcut '{shortcut_path}' and parent directory '{shortcut_dir}' removed."
                except OSError:
                    return True, f"Shortcut '{shortcut_path}' removed (parent directory not empty)."
            elif shortcut_path:
                return True, f"Shortcut path '{shortcut_path}' found in registry but file does not exist."
            else:
                return True, "No shortcut path found in registry."

        except FileNotFoundError:
            return True, f"Registry key '{REGISTRY_KEY_PATH}' not found. Assuming no shortcut to remove."
        except OSError as e:
            return False, f"Error removing shortcut '{shortcut_path}': {e}"
        except Exception as e:
            return False, f"Unexpected error removing shortcut: {e}"

    def _remove_registry_entries(self) -> tuple[bool, str]:
        """Removes the application's registry key."""
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY_PATH)
            return True, f"Registry key '{REGISTRY_KEY_PATH}' removed successfully."
        except FileNotFoundError:
            return True, f"Registry key '{REGISTRY_KEY_PATH}' not found. Nothing to remove."
        except OSError as e:
            return False, f"Error removing registry key '{REGISTRY_KEY_PATH}': {e}"
        except Exception as e:
            return False, f"Unexpected error removing registry key: {e}"

    def _remove_installed_files(self) -> tuple[bool, str]:
        """Removes files and directories within the installation path."""
        removed_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        norm_script_path = os.path.normcase(self.uninstaller_script_path)
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

            if norm_item_path == norm_script_path or \
               norm_item_path == norm_log_path or \
               norm_item_path == norm_log_dir:
                # Log skipping internally, but don't flood UI queue with this
                # self._log(f"Skipping: {item_path} (active uninstaller or log)")
                skipped_count += 1
                continue

            try:
                if os.path.isdir(item_path):
                    self._log(f"Removing directory: {item_path}")
                    shutil.rmtree(item_path, ignore_errors=False)
                    removed_count += 1
                elif os.path.isfile(item_path):
                    self._log(f"Removing file: {item_path}")
                    os.remove(item_path)
                    removed_count += 1
                else:
                    self._log(f"Skipping unknown item type: {item_path}")
                    skipped_count += 1
            except (OSError, PermissionError) as e:
                error_msg = f"Failed to remove {item_path}: {e}"
                self._log(f"ERROR: {error_msg}")
                errors.append(error_msg)
                error_count += 1

        if os.path.exists(self.log_dir):
            try:
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                os.rmdir(self.log_dir)
                self._log(f"Removed log directory: {self.log_dir}")
            except OSError as e:
                error_msg = f"Could not remove log directory {self.log_dir}: {e}"
                self._log(f"WARNING: {error_msg}")
                errors.append(error_msg)

        try:
            os.rmdir(self.install_path)
            self._log(f"Removed empty installation directory: {self.install_path}")
        except OSError:
            self._log(f"Installation directory {self.install_path} not empty, skipping removal.")
            pass

        summary = f"File removal summary: {removed_count} removed, {skipped_count} skipped, {error_count} errors."
        if errors:
            summary += "\nErrors encountered:\n" + "\n".join(errors)

        return error_count == 0, summary

# --- Main Application Window (Tkinter) ---
class UninstallMainWindow(tk.Tk):
    """Main Tkinter application window."""
    def __init__(self):
        super().__init__()
        self._worker_thread: Optional[UninstallWorker] = None
        self._output_queue = queue.Queue()
        self._is_running = False

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
        except tk.TclError:
            print(f"Warning: Font '{PRIMARY_FONT_FAMILY}' not found. Using '{FALLBACK_FONT_FAMILY}'.", file=sys.stderr)
            self.default_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            self.title_font = tkFont.Font(family=FALLBACK_FONT_FAMILY, size=TITLE_FONT_SIZE, weight="bold")
        self.style.configure('.', font=self.default_font, background=LIGHT_BG_COLOR)
        self.style.configure("TFrame", background=LIGHT_BG_COLOR)
        self.style.configure("TLabel", background=LIGHT_BG_COLOR, foreground="#333333", padding=PADDING // 3)
        self.style.configure("Title.TLabel", font=self.title_font, foreground=PRIMARY_COLOR, padding=(0, PADDING // 2))
        self.style.configure("Secondary.TLabel", foreground=SECONDARY_TEXT_COLOR)
        self.style.configure("Error.TLabel", foreground=ERROR_COLOR)
        self.style.configure("Success.TLabel", font=self.title_font, foreground=SUCCESS_COLOR)
        self.style.configure("TLabelframe", background=LIGHT_BG_COLOR)
        self.style.configure("TLabelframe.Label", background=LIGHT_BG_COLOR, font=self.default_font)
        self.style.configure("TProgressbar", thickness=20, background=BORDER_COLOR, troughcolor=LIGHT_BG_COLOR)
        self.style.configure("TButton", font=self.default_font, padding=(PADDING, PADDING // 2))

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

    def _start_uninstall(self, install_path: str):
        """Initiate the uninstallation process in a worker thread."""
        if self._is_running:
            messagebox.showwarning("In Progress", "Uninstallation is already running.")
            return

        try:
            # Ensure progress frame exists before trying to reset
            progress_frame = self.frames.get(VIEW_PROGRESS)
            if not progress_frame:
                raise RuntimeError("Progress frame not found during uninstall start.")

            self._worker_thread = UninstallWorker(install_path, self._output_queue)
            self._is_running = True
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
                success, message, full_log = data
                completion_frame.set_state(success, message, full_log)
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
            # Not running, close immediately
            self.destroy()


# --- Tkinter UI Frames (New) ---
class WelcomeFrame(ttk.Frame):
    """Welcome screen frame."""
    def __init__(self, parent, start_uninstall_callback: Callable[[str], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.start_uninstall_callback = start_uninstall_callback
        self.install_path: Optional[str] = None
        self.manual_path_selected = False

        self._setup_ui()
        self.update_install_path() # Initial check

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)
        # Row configure allows path label and buttons to be pushed down
        self.rowconfigure(3, weight=1)

        # Title
        title_label = ttk.Label(self, text=f"{APP_NAME} Uninstaller", style="Title.TLabel", anchor="center")
        title_label.grid(row=0, column=0, pady=(PADDING * 2, PADDING // 2), padx=PADDING, sticky="ew")

        # Welcome Text
        welcome_text = ttk.Label(
            self, text=f"This will uninstall {APP_NAME} and its components from your computer.",
            style="Secondary.TLabel", wraplength=WINDOW_WIDTH - 4 * PADDING, anchor="center", justify="center"
        )
        welcome_text.grid(row=1, column=0, pady=PADDING // 2, padx=PADDING, sticky="ew")

        # Path Display Area Frame
        path_frame = ttk.Frame(self, style="TFrame", padding=(PADDING // 2))
        path_frame.grid(row=2, column=0, pady=PADDING, padx=PADDING, sticky="ew")
        path_frame.columnconfigure(0, weight=1)

        self.path_label = ttk.Label(path_frame, text="Detecting installation path...", style="Secondary.TLabel", anchor="w", justify="left", wraplength=WINDOW_WIDTH - 6*PADDING - 80) # Allow wrapping, reserve space for button
        self.path_label.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.browse_button = ttk.Button(path_frame, text="Browse...", command=self._browse_for_path, width=10)
        # Grid placement for browse_button handled dynamically in update_install_path

        # Spacer Frame (pushes buttons to bottom)
        ttk.Frame(self, style="TFrame").grid(row=3, column=0, sticky="nsew")

        # Bottom Buttons Frame
        button_frame = ttk.Frame(self, style="TFrame")
        button_frame.grid(row=4, column=0, pady=(0, PADDING), padx=PADDING, sticky="ew")
        button_frame.columnconfigure(0, weight=1) # Center the button

        self.uninstall_button = ttk.Button(button_frame, text="Uninstall", command=self._on_uninstall_click)
        self.uninstall_button.grid(row=0, column=0, padx=PADDING)
        set_widget_state(self.uninstall_button, "disabled") # Disabled initially

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
            prefix = "Selected path:" if self.manual_path_selected else "Detected path:"
            self.path_label.config(text=f"{prefix}\n{self.install_path}", style="Secondary.TLabel")
            set_widget_state(self.uninstall_button, "normal")
            self.browse_button.grid_forget() # Hide browse button if path is set
        else:
            self.install_path = None
            self.manual_path_selected = False
            self.path_label.config(text="Installation path not found. Use 'Browse...' to select it manually.", style="Error.TLabel")
            set_widget_state(self.uninstall_button, "disabled")
            # Place browse button if not already visible
            if not self.browse_button.winfo_ismapped():
                 self.browse_button.grid(row=0, column=1, sticky="e", padx=5, pady=5)

    def _browse_for_path(self):
        """Open directory dialog for manual path selection."""
        selected_path = filedialog.askdirectory(title=f"Select {APP_NAME} Installation Directory")
        if selected_path and os.path.isdir(selected_path):
            # Update the UI with the manually selected path
            self.update_install_path(manual_path=os.path.normpath(selected_path))
        elif selected_path:
            messagebox.showerror("Invalid Selection", f"The selected path is not a valid directory:\n{selected_path}")
            # If the browse resulted in an error, revert state (re-check registry)
            self.update_install_path()
        # If dialog cancelled, do nothing, keep previous state.

    def _on_uninstall_click(self):
        """Handle uninstall button click, confirming if path was manual."""
        if not self.install_path:
            messagebox.showerror("Error", "No installation path specified.")
            return

        confirm_msg = f"Are you sure you want to uninstall {APP_NAME} from:\n{self.install_path}?\n\nThis action cannot be undone."
        confirm_title = "Confirm Uninstall"

        if self.manual_path_selected:
            confirm_msg = f"WARNING: You manually selected the installation path:\n{self.install_path}\n\nUninstalling from the wrong directory can damage other applications or your system.\n\nARE YOU ABSOLUTELY SURE you want to proceed?"
            confirm_title = "Confirm Manual Path Uninstall"

        proceed = messagebox.askyesno(confirm_title, confirm_msg, default=messagebox.NO, icon=messagebox.WARNING if self.manual_path_selected else messagebox.QUESTION)

        if proceed:
            self.start_uninstall_callback(self.install_path)


class ProgressFrame(ttk.Frame):
    """Progress display frame."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_ui()

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)

        # Title
        self.title_label = ttk.Label(self, text=f"Uninstalling {APP_NAME}...", style="Title.TLabel", anchor="w", justify="left")
        self.title_label.grid(row=0, column=0, pady=(PADDING, PADDING // 2), padx=PADDING, sticky="ew")

        # Status Label
        self.status_label = ttk.Label(self, text="Initializing...", style="Secondary.TLabel", anchor="w", justify="left")
        self.status_label.grid(row=1, column=0, pady=PADDING // 2, padx=PADDING, sticky="ew")

        # Progress Bar
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate", length=WINDOW_WIDTH - 2 * PADDING)
        self.progress_bar.grid(row=2, column=0, pady=PADDING // 2, padx=PADDING, sticky="ew")

        # Log Area (ScrolledText)
        self.log_text = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD, state="disabled", relief="solid", bd=1, font=(PRIMARY_FONT_FAMILY, DEFAULT_FONT_SIZE -1)) # Slightly smaller font for logs
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


class CompletionFrame(ttk.Frame):
    """Completion screen frame."""
    def __init__(self, parent, close_callback: Callable[[], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.close_callback = close_callback
        self._full_log_content: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)
        # Row 3 is the log area, allow it to expand/contract
        self.rowconfigure(3, weight=0) # Start with no weight

        # Title Label
        self.title_label = ttk.Label(self, text="Uninstallation Complete", style="Title.TLabel", anchor="center")
        self.title_label.grid(row=0, column=0, pady=(PADDING * 2, PADDING // 2), padx=PADDING, sticky="ew")

        # Message Label
        self.message_label = ttk.Label(self, text="", style="Secondary.TLabel", wraplength=WINDOW_WIDTH - 4 * PADDING, anchor="center", justify="center")
        self.message_label.grid(row=1, column=0, pady=PADDING // 2, padx=PADDING, sticky="ew")

        # Frame for Details button (to center it)
        details_button_frame = ttk.Frame(self, style="TFrame")
        details_button_frame.grid(row=2, column=0, pady=(PADDING, PADDING // 2))
        details_button_frame.columnconfigure(0, weight=1)

        self.details_button = ttk.Button(details_button_frame, text="Show Details", command=self._toggle_details)
        self.details_button.grid(row=0, column=0)
        set_widget_state(self.details_button, "disabled") # Disabled initially

        # Log Area (ScrolledText, initially not gridded)
        self.log_text = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD, state="disabled", relief="solid", bd=1, font=(PRIMARY_FONT_FAMILY, DEFAULT_FONT_SIZE -1))

        # Bottom Button Frame (always visible)
        button_frame = ttk.Frame(self, style="TFrame")
        button_frame.grid(row=4, column=0, pady=(PADDING // 2, PADDING), sticky="sew") # Stick to bottom-east-west
        button_frame.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1) # Push button to bottom

        # Close Button (centered in bottom frame)
        self.close_button = ttk.Button(button_frame, text="Close", command=self.close_callback)
        self.close_button.grid(row=0, column=0, padx=PADDING)

    def set_state(self, success: bool, final_message: str, full_log: str):
        """Set the final state of the completion screen."""
        if not self.winfo_exists(): return

        self._full_log_content = full_log
        if success:
            self.title_label.config(text="Uninstallation Complete", style="Success.TLabel")
            self.message_label.config(text=f"{APP_NAME} has been successfully uninstalled.")
        else:
            self.title_label.config(text="Uninstallation Failed", style="Error.TLabel")
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

    def _toggle_details(self):
        """Show or hide the detailed log."""
        if self.log_text.winfo_ismapped(): # Check if gridded (visible)
            self._hide_details()
        else:
            self._show_details()

    def _show_details(self):
        if not self._full_log_content or not self.winfo_exists():
            return
        # Place the log text widget
        self.log_text.grid(row=3, column=0, pady=0, padx=PADDING, sticky="nsew")
        self.rowconfigure(3, weight=1) # Allow log area to take space
        self.rowconfigure(4, weight=0) # Button frame no longer expands
        set_widget_state(self.log_text, "normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, self._full_log_content)
        set_widget_state(self.log_text, "disabled")
        self.details_button.config(text="Hide Details")
        self.update_idletasks() # Ensure layout updates

    def _hide_details(self):
        if not self.winfo_exists(): return
        self.log_text.grid_forget()
        self.rowconfigure(3, weight=0) # Log area takes no space
        self.rowconfigure(4, weight=1) # Button frame expands again
        self.details_button.config(text="Show Details")
        self.update_idletasks()


# --- Tkinter main ---
def main():
    # Redirect stdout/stderr if running with pythonw.exe
    if "pythonw.exe" in sys.executable.lower():
        log_dir_fallback = os.path.join(os.path.expanduser("~"), "AppData", "Local", APP_NAME, "Logs")
        os.makedirs(log_dir_fallback, exist_ok=True)
        log_file = os.path.join(log_dir_fallback, "uninstaller_gui_errors.log")
        try:
            sys.stdout = open(log_file, "a", encoding='utf-8')
            sys.stderr = sys.stdout
            print(f"--- {APP_NAME} Uninstaller GUI Started ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
        except Exception as e:
            print(f"Critical: Failed to redirect stdout/stderr: {e}")

    try:
        app = UninstallMainWindow()
        app.mainloop()
    except Exception as e:
        print("--- Uninstaller GUI FATAL ERROR ---")
        traceback.print_exc()
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"A critical error occurred in the uninstaller GUI: {e}\nSee logs for details.", f"{APP_NAME} Uninstaller Error", 0x10 | 0x0)
        except Exception:
            pass

if __name__ == "__main__":
    main() 