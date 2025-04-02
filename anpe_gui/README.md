# ANPE GUI

A graphical user interface for [ANPE (Another Noun Phrase Extractor)](https://github.com/rcverse/anpe).

![ANPE GUI Screenshot](resources/screenshot.png)

## Features

- Direct text input or file processing
- Batch processing of multiple files
- Configurable extraction settings
- Results visualization
- Export to multiple formats (TXT, CSV, JSON)
- Log viewer for tracking operations

## Installation

The ANPE GUI application can be used in two ways:

### 1. Run from source

Make sure you have Python 3.9+ and ANPE installed:

```bash
pip install anpe
pip install PyQt6
```

Then run:

```bash
python run_anpe_gui.py
```

### 2. Use standalone executable

Download the standalone executable for your platform from the latest release:

- Windows: `anpe_gui.exe`
- Mac: `anpe_gui.app`

No installation required - just download and run!

## Usage

### Input Options

- **Text Input**: Enter text directly in the text area
- **File Input**: Select a single text file to process
- **Batch Processing**: Select a directory containing multiple text files

### Configuration Options

- **Filtering**: Set minimum/maximum NP length, exclude pronouns
- **Structure Filters**: Choose specific NP structures to include
- **Logging**: Configure log level and output

### Output Options

- View extraction results in the application
- Export to TXT, CSV, or JSON formats
- Select a custom export directory

## Building from Source

To create a standalone executable:

1. Install PyInstaller or cx_Freeze:
   ```bash
   pip install pyinstaller
   # or
   pip install cx_freeze
   ```

2. Run the build script:
   ```bash
   # Using PyInstaller
   pyinstaller --onefile --windowed anpe_gui/app.py
   
   # Using cx_Freeze
   python anpe_gui/setup.py build
   ```

3. Find the executable in the `dist` directory

## License

This project is licensed under the same terms as ANPE - see the [LICENSE](../LICENSE) file for details. 