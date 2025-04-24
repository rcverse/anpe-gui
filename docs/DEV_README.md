# ANPE GUI - Developer README

This document provides a technical overview of the ANPE GUI application for developers and maintainers.

## Project Structure

```
anpe_gui/
├── __init__.py           # Package initialization
├── __main__.py           # Allows running with `python -m anpe_gui`
├── app.py                # Main application entry point, handles setup, splash screen, main window launch
├── main_window.py        # Core QMainWindow implementation, manages UI layout, tabs, signals/slots
├── splash_screen_alt.py  # Displays loading screen (using activity indicator), performs initial model checks via worker
├── theme.py              # Defines color palettes, styles, and generates stylesheets
├── resource_manager.py   # Handles loading of icons and other resources
├── version.py            # Contains the GUI application version (__version__)
├── run.py                # Simple script to run the application from source root
├── minimal_requirements.txt # Basic runtime dependencies
├── resources/            # Contains icons, images, etc.
│   └── ...
├── widgets/              # Reusable UI components (custom QWidgets)
│   ├── __init__.py
│   ├── settings_dialog.py  # Dialog for models, core updates, about info (uses settings_workers)
│   ├── result_display.py   # Widget for displaying extraction results (tree view)
│   ├── help_dialog.py      # Displays the contents of gui_help.md
│   ├── status_bar.py       # Custom status bar with color-coded messages
│   ├── structure_filter_widget.py # Checkbox list for structure filtering
│   ├── enhanced_log_panel.py # Toggleable panel for detailed logging
│   ├── file_list_widget.py   # Manages the list of files for batch processing
│   ├── license_dialog.py   # Displays license information
│   ├── activity_indicator.py # Pulsing visual indicator for busy/loading states
│   └── custom_title_bar.py # (Potentially unused) Custom window title bar
└── workers/              # QObject subclasses for background tasks (QThreadPool)
    ├── __init__.py
    ├── extraction_worker.py # Handles single text/file extraction using ANPE core
    ├── batch_worker.py     # Handles processing of multiple files
    ├── log_handler.py      # Custom logging handler to route logs to the UI log panel
    ├── status_worker.py    # Contains ModelStatusChecker used by splash screen
    └── settings_workers.py # Contains workers for SettingsDialog actions (model install/uninstall/check, core update, cleanup)

docs/
└── gui_help.md           # User-facing help documentation (markdown)

README.md                 # Main project README (user-focused)
```

## Key Components

*   **`app.py`**: Sets up `QApplication`, theme, handles High-DPI scaling, initiates the `AltSplashScreen`.
*   **`splash_screen_alt.py`**: Shows splash image overlaying a `PulsingActivityIndicator`, runs initial model presence check in a background thread (`ModelStatusChecker` in `workers/status_worker.py`), signals completion or error to `app.py`.
*   **`main_window.py`**: The central hub. 
    *   Builds the main UI using `QTabWidget` for Input/Output.
    *   Connects UI elements (buttons, checkboxes, etc.) to actions (slots).
    *   Manages background processing using `QThreadPool` and workers from the `workers/` directory.
    *   Handles signals from workers (progress, results, errors).
    *   Integrates `StatusBar`, `EnhancedLogPanel`, `SettingsDialog`, `HelpDialog`.
    *   Manages application state (e.g., whether processing is active, results data).
*   **`widgets/settings_dialog.py`**: A multi-page dialog (`QStackedWidget` + `QListWidget`) for:
    *   **Models Page**: Displaying installed spaCy/Benepar models, allowing install/uninstall actions (using `ModelActionWorker` from `settings_workers.py`), selecting usage preferences, running model cleanup (`CleanWorker`). (NLTK is used implicitly by Benepar).
    *   **Core Page**: Checking for updates to the `anpe` core library (using `CoreUpdateWorker`) and triggering updates (`pip install --upgrade`).
    *   **About Page**: Displaying GUI and Core library versions, links to documentation/repository.
*   **`workers/`**: Contains `QObject` subclasses designed to run on a `QThreadPool`.
    *   `extraction_worker.py`: Performs a single ANPE extraction task.
    *   `batch_worker.py`: Manages the processing of multiple files, emitting progress.
    *   `log_handler.py`: A custom `logging.Handler` that emits signals to update the `EnhancedLogPanel`.
    *   `status_worker.py`: Includes `ModelStatusChecker` for checking installed models asynchronously (used by splash screen).
    *   `settings_workers.py`: Provides workers (`CoreUpdateWorker`, `CleanWorker`, `InstallDefaultsWorker`, `ModelActionWorker`, `StatusCheckWorker`) specifically for operations triggered by the `SettingsDialog`.
*   **`theme.py`**: Defines color constants and generates the application's `QSS` stylesheet.
*   **`resource_manager.py`**: Provides a centralized way to access bundled resources like icons.