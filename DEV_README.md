# ANPE Studio - Developer Documentation

This document provides guidance for developers interested in contributing to the ANPE Studio project, building it from source, or understanding its internal structure.

---

## Table of Contents

*   [Project Overview](#project-overview)
*   [Getting Started](#getting-started)
*   [Project Structure](#project-structure)
*   [Key Modules](#key-modules)
*   [Dependencies](#dependencies)
*   [Building the Application](#building-the-application)
    *   [Windows](#windows)
    *   [macOS (Experimental)](#macos-experimental)
*   [Code Style and Conventions](#code-style-and-conventions)
*   [Testing](#testing)
*   [Contributing](#contributing)

---

## Project Overview

ANPE Studio is a Python application built with PyQt6 that provides a graphical user interface for the [ANPE core library](https://github.com/rcverse/another-noun-phrase-extractor). It allows users to extract noun phrases from text or files without needing programming knowledge.

The project includes:

*   The main GUI application (`anpe_studio/`).
*   A separate installer GUI for Windows (`installer/`).
*   A launcher script for the installed Windows version (`launcher.py`).
*   Build configurations using PyInstaller (`.spec` files).

---

## Getting Started


1.  **Clone:** `git clone https://github.com/rcverse/anpe-studio.git && cd anpe-studio`
2.  **Create & Activate Virtual Environment:**
    *   `venv`: `python -m venv .venv && .\.venv\Scripts\activate` (Win) or `source .venv/bin/activate` (Mac/Linux)
    *   `conda`: `conda create -n anpe-studio python=3.x && conda activate anpe-studio`
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    # Optional: for building
    pip install pyinstaller
    ```
4.  **Run:**
    ```bash
    python -m anpe_studio
    # or
    python anpe_studio/run.py
    ```

---

## Project Structure

```
.anpe-studio/
├── anpe_studio/        # Main GUI application source code
│   ├── resources/      # Static assets (icons, etc.)
│   ├── widgets/        # Reusable custom UI widgets
│   ├── workers/        # Background QThread workers
│   ├── __init__.py
│   ├── __main__.py     # Allows running with 'python -m anpe_studio'
│   ├── app.py          # QApplication setup, splash screen, main window launch
│   ├── main_window.py  # Core application logic and UI structure
│   ├── resource_manager.py # Asset handling
│   ├── run.py          # Simple script to run app.main()
│   ├── splash_screen.py # Initial loading/checking screen
│   ├── theme.py        # Styling and themes
│   └── version.py      # Application version
├── installer/          # Windows installer GUI source code
│   ├── assets/         # Assets specific to the installer
│   ├── views/          # UI views for the installer (Welcome, Progress, Completion)
│   ├── widgets/        # Custom widgets for the installer (TitleBar)
│   ├── workers/        # Background workers for install tasks
│   ├── __init__.py
│   ├── setup_windows.pyw # Main entry point for the installer GUI
│   └── utils.py        # Utility functions for the installer
├── docs/               # Documentation files (including this one)
├── scripts/            # Utility/helper scripts (if any)
├── tests/              # Unit/integration tests (if any)
├── .git/               # Git repository data
├── .venv/              # Virtual environment (if created here)
├── build/              # PyInstaller build cache
├── dist/               # PyInstaller output directory (executables)
├── .gitignore          # Files/directories ignored by Git
├── ANPE_Studio_app.spec       # PyInstaller spec file for the main application
├── ANPE_Studio_Installer.spec # PyInstaller spec file for the Windows installer
├── ANPE_Studio_Uninstaller.spec # PyInstaller spec file for the uninstaller
├── launcher.py         # Wrapper script launched by the final Windows executable
├── LICENSE             # Project license file
├── main_macos.py     # macOS specific logic (likely experimental)
├── README.md           # User-facing README
├── requirements.txt    # Python package dependencies
└── setup.py            # Python package metadata (might be minimal if PyInstaller is primary)
```

---

## Key Modules

*   **`anpe_studio/app.py`:** Initializes the `QApplication`, sets the theme, manages the splash screen, and launches the `MainWindow`.
*   **`anpe_studio/main_window.py`:** The heart of the application. Defines the main UI structure (tabs, widgets), handles user interactions, manages configuration, orchestrates background processing via workers, and displays results.
*   **`anpe_studio/workers/`:** Contains `QObject` subclasses designed to run in separate `QThread`s for long-running tasks like NLP processing (`ExtractionWorker`, `BatchWorker`) and model status checks (`ModelStatusChecker`). This prevents the GUI from freezing.
*   **`anpe_studio/widgets/`:** Houses custom, reusable UI components like the file list, filter selectors, log panel, results display, settings dialog, and help dialog.
*   **`anpe_studio/theme.py`:** Centralizes application styling, including color definitions and stylesheet generation.
*   **`anpe_studio/splash_screen.py`:** Provides initial feedback to the user while performing startup checks (e.g., model availability).
*   **`installer/setup_windows.pyw`:** A separate PyQt application that acts as the installation wizard for Windows. It guides users through selecting an install path and handles environment/model setup using its own workers.
*   **`launcher.py`:** A simple Python script compiled by PyInstaller into the final `.exe` for the Windows installed version. Its main job is to locate the embedded Python interpreter within the installation directory and execute the main application script (`anpe_studio/run.py`) with the correct environment and working directory.
*   **`.spec` Files:** Define how PyInstaller should bundle the application, installer, and uninstaller, including dependencies, hidden imports, data files (like icons), and executable metadata.

---

## Dependencies

Runtime dependencies are in `requirements.txt`.

For building, install PyInstaller: `pip install pyinstaller`

---

## Building the Application

The application uses **PyInstaller** with `.spec` files.

### Windows

Three executables are typically built:

1.  **Main Application:** Uses `ANPE_Studio_app.spec`.
2.  **Installer:** Uses `ANPE_Studio_Installer.spec`.
3.  **Uninstaller:** Uses `ANPE_Studio_Uninstaller.spec`.

To build (from the project root, with the virtual environment activated):

```bash
# Build the main application (output in dist/ANPE_Studio)
pyinstaller ANPE_Studio_app.spec

# Build the installer (output in dist/ANPE_Setup)
pyinstaller ANPE_Studio_Installer.spec

# Build the uninstaller (output in dist/uninstall)
pyinstaller ANPE_Studio_Uninstaller.spec
```

*   You might need to adjust paths within the `.spec` files depending on your environment or changes.
*   The final installer usually bundles the output of the main application build and the uninstaller build.

### macOS (Experimental)

macOS support is under development. Building likely involves `main_macos.py` and potentially custom scripts or modifications to the `.spec` files. Consult specific macOS build instructions if available, or analyze `main_macos.py` and related scripts (`debug_macos_*.sh`).

---

## Code Style and Conventions

*   **PEP 8:** Please adhere to the [PEP 8 Style Guide](https://www.python.org/dev/peps/pep-0008/). Tools like `flake8` or `black` can help.
*   **Type Hinting:** Use type hints (`typing` module) for function signatures and variables where practical to improve code clarity and enable static analysis.
*   **Docstrings:** Write clear docstrings for modules, classes, and functions explaining their purpose, arguments, and return values.
*   **Meaningful Names:** Use descriptive names for variables, functions, and classes.
*   **Imports:** Organize imports according to PEP 8 (standard library, third-party, local application).
*   **Logging:** Use the `logging` module for application events, warnings, and errors. Avoid excessive use of `print()` for debugging information in committed code.

---

## Testing

*(Placeholder)* No formal test suite exists currently. Contributions adding tests (e.g., `pytest`, `pytest-qt`) are welcome.

---

## Contributing

Contributions are welcome!

1.  **Bugs & Enhancements:** Check existing [Issues](https://github.com/rcverse/anpe-studio/issues) or create a new one with clear details.
2.  **Pull Requests:**
    *   Fork the repo, create a feature branch.
    *   Make your changes, adhering to code style.
    *   Commit with clear messages.
    *   Push to your fork and open a PR against the main repository branch (`main` or `develop`).
    *   Clearly describe your changes in the PR. 