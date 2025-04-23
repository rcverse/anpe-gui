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
    *   **Models Page**: Displaying installed spaCy/Benepar models, allowing install/uninstall actions (using `ModelActionWorker`), selecting usage preferences, running model cleanup (`CleanWorker`). (NLTK is used implicitly by Benepar).
    *   **Core Page**: Checking for updates to the `