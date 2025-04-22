# ANPE GUI - Developer README

This document provides a technical overview of the ANPE GUI application for developers and maintainers.

## Project Structure

```
anpe_gui/
├── __init__.py           # Package initialization
├── __main__.py           # Allows running with `python -m anpe_gui`
├── app.py                # Main application entry point, handles setup, splash screen, main window launch
├── main_window.py        # Core QMainWindow implementation, manages UI layout, tabs, signals/slots
├── splash_screen.py      # Displays loading screen, performs initial model checks
├── theme.py              # Defines color palettes, styles, and generates stylesheets
├── resource_manager.py   # Handles loading of icons and other resources
├── version.py            # Contains the GUI application version (__version__)
├── run.py                # Simple script to run the application from source root
├── minimal_requirements.txt # Basic runtime dependencies
├── resources/            # Contains icons, images, etc.
│   └── ...
├── widgets/              # Reusable UI components (custom QWidgets)
│   ├── __init__.py
│   ├── settings_dialog.py  # Dialog for models, core updates, about info
│   ├── result_display.py   # Widget for displaying extraction results (tree view)
│   ├── help_dialog.py      # Displays the contents of gui_help.md
│   ├── status_bar.py       # Custom status bar with color-coded messages
│   ├── structure_filter_widget.py # Checkbox list for structure filtering
│   ├── enhanced_log_panel.py # Toggleable panel for detailed logging
│   ├── file_list_widget.py   # Manages the list of files for batch processing
│   ├── license_dialog.py   # Displays license information
│   ├── activity_indicator.py # Simple visual indicator for busy states
│   └── custom_title_bar.py # (Potentially unused) Custom window title bar
└── workers/              # QObject subclasses for background tasks (QThreadPool)
    ├── __init__.py
    ├── extraction_worker.py # Handles single text/file extraction using ANPE core
    ├── batch_worker.py     # Handles processing of multiple files
    └── log_handler.py      # Custom logging handler to route logs to the UI log panel

docs/
└── gui_help.md           # User-facing help documentation (markdown)

README.md                 # Main project README (user-focused)
```

## Key Components

*   **`app.py`**: Sets up `QApplication`, theme, handles High-DPI scaling, initiates the `SplashScreen`.
*   **`splash_screen.py`**: Shows splash image, runs initial model presence check in a background thread (`ExtractorInitializer` in `main_window.py`), signals completion or error to `app.py`.
*   **`main_window.py`**: The central hub. 
    *   Builds the main UI using `QTabWidget` for Input/Output.
    *   Connects UI elements (buttons, checkboxes, etc.) to actions (slots).
    *   Manages background processing using `QThreadPool` and workers from the `workers/` directory.
    *   Handles signals from workers (progress, results, errors).
    *   Integrates `StatusBar`, `EnhancedLogPanel`, `SettingsDialog`, `HelpDialog`.
    *   Manages application state (e.g., whether processing is active, results data).
*   **`widgets/settings_dialog.py`**: A multi-page dialog (`QStackedWidget` + `QListWidget`) for:
    *   **Models Page**: Displaying installed models (spaCy, Benepar, NLTK), allowing install/uninstall actions (using `ModelActionWorker`), selecting usage preferences, running model cleanup (`CleanWorker`).
    *   **Core Page**: Checking for updates to the `anpe` core library via PyPI and running `pip install --upgrade anpe` (`CoreUpdateWorker`).
    *   **About Page**: Displaying version info and licenses.
*   **`widgets/result_display.py`**: Uses a `QTreeView` with a custom model (`ResultModel`) to show hierarchical noun phrase results.
*   **`workers/`**: Contains `QObject` subclasses with a `run` method designed to be executed in a `QThreadPool`. They emit signals (`pyqtSignal`) to communicate progress, results, or errors back to the main thread (`MainWindow`).
*   **`theme.py`**: Defines color constants and generates Qt Stylesheets (QSS) for a consistent look and feel.
*   **`resource_manager.py`**: Loads icons dynamically, facilitating packaging (e.g., with PyInstaller).

## Core Logic Flow

1.  **Startup**: `app.py` -> `SplashScreen`.
2.  **Initialization**: `SplashScreen` starts `ExtractorInitializer` (in `main_window.py`) to check for essential model *types*.
3.  **Main Window Launch**: `SplashScreen` signals completion/error -> `app.py` creates and shows `MainWindow`, passing initial status.
4.  **Input**: User adds files/text via `main_window.py` UI elements (e.g., `FileListWidget`, `QTextEdit`).
5.  **Configuration**: User sets options (checkboxes, spinboxes, `StructureFilterWidget`) in `main_window.py`.
6.  **Processing**: 
    *   User clicks "Process".
    *   `main_window.py` gathers configuration and input.
    *   It creates either an `ExtractionWorker` (single) or `BatchWorker` (multiple files).
    *   The worker is submitted to the global `QThreadPool`.
    *   `MainWindow` connects to the worker's signals (`progress`, `finished`, `error`).
    *   UI is updated based on worker signals (status bar, progress bar, log panel).
7.  **Results**: 
    *   Worker emits results via `finished` signal.
    *   `main_window.py` receives results, stores them, updates the `ResultDisplayWidget`, and switches to the Output tab.
8.  **Export**: User clicks "Export" -> `main_window.py` uses `QFileDialog` and calls the `anpe` core library's export function.
9.  **Settings**: User clicks gear icon -> `main_window.py` opens `SettingsDialog`. Actions within the dialog (e.g., install model, update core) use their own background workers.

## Dependencies

*   **PyQt6**: GUI framework.
*   **anpe**: The core noun phrase extraction library.
    *   *Transitive dependencies*: spaCy, benepar, NLTK, etc. (Managed by the `anpe` package itself).

See `minimal_requirements.txt` for direct GUI dependencies and the `anpe` package for its requirements.

## Development Notes

*   **Threading**: Background tasks are crucial for responsiveness. Use `QThreadPool` and `QObject` workers emitting signals. Avoid blocking the main GUI thread.
*   **Styling**: UI styling is primarily done via QSS in `theme.py`. Use the defined color constants.
*   **Resource Management**: Use `ResourceManager.get_icon()` etc., to ensure resources are found correctly, especially when packaged.
*   **Logging**: A custom `QtLogHandler` routes standard Python logging messages to the `EnhancedLogPanel` in the UI.
*   **Model Management**: Core model installation/checking logic resides within the `anpe` library (`anpe.utils`). The GUI interacts with these functions, often via workers in `settings_dialog.py`.
*   **Cross-Platform**: Built with PyQt, aiming for cross-platform compatibility (Windows, macOS, Linux), though testing might be required. 