# ANPE GUI

A graphical user interface for [ANPE (Another Noun Phrase Extractor)](https://github.com/rcverse/anpe).

<!-- Optional: Insert Screenshot Here -->
<!-- ![ANPE GUI Screenshot](resources/screenshot.png) -->

## Features

- **User-friendly interface** with distinct Input and Output tabs.
- **Input Modes**: Process text via Direct Text Input (with Paste/Clear) or File Input.
- **File Handling**: Add single files or entire directories; view and manage the list.
- **Batch Processing**: Automatically handles multiple files from selected directories.
- **Visual Configuration**: Easily configure all ANPE settings:
    - General: Include Nested Phrases, Include Metadata, Treat Newlines as Boundaries.
    - Filtering: Min/Max NP length, Accept Pronouns.
    - Structure Filtering: Master toggle switch and individual selection for specific NP structures (Determiner, Compound, Relative Clause, etc.).
    - Tooltips: Hover over options for detailed explanations.
- **Real-time Log Viewer**: Track operations and potential issues with log level filtering.
- **Results Visualization**: View formatted extraction results in the Output tab.
- **Batch Result Navigation**: Use a dropdown to view results for specific files when processing batches.
- **Export Options**: Export results to TXT, CSV, or JSON formats to a selected directory.
- **Status Bar**: Provides feedback on application readiness, processing progress, and completion status.
- **Workflow Control**: Process button initiates extraction, Reset button clears inputs/outputs for a new task.

## Installation & Usage

The ANPE GUI application can be used in two main ways:

### 1. Run from source (Recommended for Development)

Requires Python 3.9+ and the necessary dependencies. Navigate to the main project root directory (`ANPE_public`) and run:

```bash
# Ensure dependencies are installed (from main requirements.txt)
# pip install -r requirements.txt 

# Run the GUI entry point
python run_anpe_gui.py 
```

(This assumes `anpe` library and `PyQt6` are installed, typically via the main `requirements.txt`)

### 2. Use Standalone Executable (Recommended for End Users)

Download the standalone executable for your platform (e.g., `ANPE_GUI.exe` for Windows, `ANPE_GUI.app` for macOS) from the project's GitHub Releases page (if available).

No installation is required - just download and run!

## Building Standalone Executable from Source

To create a standalone executable for distribution:

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Navigate to Project Root:** Open your terminal in the main project directory (e.g., `ANPE_public`).

3.  **Run PyInstaller:**
    Use the `run_anpe_gui.py` script as the entry point.
    ```bash
    # Basic command
    pyinstaller --windowed --name ANPE_GUI run_anpe_gui.py
    
    # Recommended for single file (can be slower startup)
    pyinstaller --onefile --windowed --name ANPE_GUI run_anpe_gui.py 
    ```
    *   `--windowed`: Prevents console window (essential for GUI).
    *   `--name ANPE_GUI`: Sets the output executable/app name.
    *   `--onefile`: Bundles everything into a single file (optional).
    *   Consider adding `--hidden-import` flags if you encounter missing module errors during packaging or runtime (see main `README.md` for details).

4.  **Find Executable:** The executable will be located in the `dist` directory (`dist/ANPE_GUI.exe` or `dist/ANPE_GUI.app`).

## License

This project is licensed under the same terms as ANPE - see the [LICENSE](../LICENSE) file for details. 