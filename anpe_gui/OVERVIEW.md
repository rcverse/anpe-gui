# ANPE GUI Overview

## Project Structure

```
anpe_gui/
├── __init__.py           # Package initialization
├── __main__.py           # Entry point for module execution
├── app.py                # Main application entry point
├── main_window.py        # Main window implementation
├── setup.py              # Packaging script for cx_Freeze
├── requirements.txt      # Dependencies
├── README.md             # Documentation
├── NEXT_STEPS.md         # Future improvements
├── resources/            # Resources directory
│   └── __init__.py       # Package initialization
└── widgets/              # Custom widget components
    ├── __init__.py       # Package initialization
    ├── batch_worker.py   # Batch processing worker
    ├── extraction_worker.py # Extraction worker
    └── log_handler.py    # Log handler for GUI
```

## Additional Files

```
anpe_gui.spec              # PyInstaller specification file
package.py                 # Packaging script
run_anpe_gui.py            # Entry point script
```

## Technical Details

- **GUI Framework**: PyQt6 - cross-platform, responsive, and feature-rich
- **Threading**: QThreadPool for background processing to keep the UI responsive
- **Packaging**: PyInstaller for creating standalone executables
- **Integration**: Direct API calls to the ANPE library

## Architecture

The application follows a modular architecture with clear separation of concerns:

1. **Main Window** (`main_window.py`):
   - Handles UI layout and user interactions
   - Coordinates other components
   - Manages configuration settings

2. **Worker Classes** (`widgets/*.py`):
   - Perform background processing
   - Report progress via signals
   - Handle errors gracefully

3. **Log Handler** (`widgets/log_handler.py`):
   - Integrates Python logging into the GUI
   - Provides visual feedback on operations
   - Helps with troubleshooting

## Features

- **Text Input**: Direct text entry for quick extraction
- **File Input**: Process individual text files
- **Batch Processing**: Process multiple files in a directory
- **Configuration**: Visual interface for all ANPE settings
- **Results Display**: Formatted output of extraction results
- **Export Options**: Save results in multiple formats
- **Logging**: Integrated log display for operations

## Usage

The application can be launched in several ways:

1. **Module**: `python -m anpe_gui`
2. **Script**: `python run_anpe_gui.py`
3. **Executable**: Run the standalone executable (if built)

## Building

To create a standalone executable:

1. Install requirements:
   ```bash
   pip install -r anpe_gui/requirements.txt
   ```

2. Run the packaging script:
   ```bash
   python package.py
   ```

3. The executable will be created in the `dist` directory. 