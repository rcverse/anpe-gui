# ANPE Studio Help

Welcome to the ANPE Studio! This application provides a user-friendly interface to the core ANPE library, allowing you to easily extract noun phrases from text without needing to write code.

## Starting the app

When you start the app, ANPE will automatically check for required language models in the background.

If any essential model are missing, the status bar will display a warning (e.g., "Missing required models: spaCy model(s), NLTK data. Use 'Manage Models' (⚙️ icon) to install.") and the "Process" button will remain disabled.

Model installation and management are handled through the `<button>` Settings `</button>` dialog, accessible via the gear icon (`<q>` ⚙️ `</q>`) in the top-right corner. This dialog requires an internet connection for downloading models.

## Usage

The application is organized into two main tabs: `<option>` Input `</option>` and `<option>` Output `</option>`. A toggleable log panel is also available at the bottom (click on colored status label to toggle), showing detailed processing messages.

### Input Tab

This is where you prepare your text and configure the extraction process.

#### Input Options

You can choose between two ways to provide text using the toggle buttons at the top:

**File Input**

   This mode allows you to batch process multiple files or simply process a single file.

* `<button>` Add Files `</button>`: Select individual `<format>` .txt `</format>` files.
* `<button>` Add Directory `</button>`: Add all `<format>` .txt `</format>` files within a selected folder.
* `<button>` Remove Selected `</button>` / `<button>` Clear All `</button>`: Manage the list of files to process.
  **Text Input**

   This mode allows you to type or paste text directly into the editor for quick analysis.

* `<button>` Paste `</button>`: Insert text from your clipboard.
* `<button>` Clear `</button>`: Empty the text input area.

#### Configuration

Fine-tune the extraction process using the options on the right side:

**General Settings**:

* <option> Include nested phrases </option>: Captures noun phrases embedded within larger ones.
* <option> Add metadata to output </option>: Includes length and structure information for each phrase.
* <option> Do not treat newlines as sentence boundaries </option>: Controls how line breaks are interpreted. Check this box to ignore line breaks as sentence boundaries; suitable when processing files with irregular line breaking.

**Filtering Options**:

* <option> Min Length </option> and <option> Max Length </option>: Specify the word count limits for phrases.
* <option> Do not accept Pronouns </option>: Controls whether single-word pronouns are included.

**Structure Filtering**:

* Enable the main toggle (`<option>` Filter by Structure `</option>`) to activate structure filtering. Then, select specific structures from the list to *include* in the output. Only phrases matching at least one selected structure will be kept.
  * **`<option>` Determiner `</option>`**: Phrases starting with articles or determiners (e.g., 'the cat', 'a house').
  * **`<option>` Adjectival Modifier `</option>`**: Phrases containing adjectives that describe the noun (e.g., 'red car', 'beautiful day').
  * **`<option>` Prepositional Modifier `</option>`**: Phrases where a prepositional phrase follows the noun (e.g., 'book on the table').
  * **`<option>` Compound `</option>`**: Phrases made of multiple nouns acting as one unit (e.g., 'noun phrase extractor', 'apple pie').
  * **`<option>` Possessive `</option>`**: Phrases showing ownership (e.g., "John's book", 'her bag').
  * **`<option>` Quantified `</option>`**: Phrases indicating quantity or number (e.g., 'two dogs', 'many people').
  * **`<option>` Coordinated `</option>`**: Phrases linking items with 'and' or 'or' (e.g., 'cats and dogs').
  * **`<option>` Appositive `</option>`**: Phrases where one noun phrase renames another, often set off by commas (e.g., 'Bob, my friend').
  * **`<option>` Relative Clause `</option>`**: Phrases containing a clause that modifies the noun (e.g., 'the man who called').
  * **`<option>` Reduced Relative Clause `</option>`**: A relative clause modifying a noun, but without the relative pronoun (e.g., 'the book *written by him*').
  * **`<option>` Nonfinite Complement `</option>`**: A phrase (often starting with 'to' or ending in '-ing') that completes the meaning of a noun (e.g., 'the *decision to leave*').
  * **`<option>` Finite Complement `</option>`**: A full clause (often starting with 'that' or 'whether') that completes the meaning of a noun (e.g., 'the *idea that he left*').
  * **`<option>` Pronoun `</option>`**: Phrases consisting only of a pronoun (e.g., 'he', 'it', 'they'). Note: Use the "Do not accept Pronouns" filter option to exclude these if needed, regardless of structure filtering.
  * **`<option>` Standalone Noun `</option>`**: Phrases consisting only of a single noun or proper noun (e.g., 'book', 'John').
  * **`<option>` Others `</option>`**: Any other identified noun phrase structures not fitting the above categories.

#### Control Buttons

* `<button>` Process `</button>`: Starts the noun phrase extraction based on your input and configuration.
* `<button>` Reset `</button>`: Clears all input fields (text area, file list) and resets configuration settings to their defaults.
* `<button>` Default `</button>`: Reverts only the filtering options (lengths, structure selections) to their defaults, leaving input untouched.

### Output Tab

This tab displays the results of the extraction process.

#### Viewing Results

* The main area shows the extracted noun phrases, formatted according to your settings.
* If processing multiple files (batch mode), a dropdown menu appears above the results area, allowing you to select which file's results to view.
* If nested phrases were included (`<option>` Include nested phrases `</option>`) was checked, the display will show the hierarchical structure. By default, nested phrases are collapsed; click on a parent phrase entry to expand or collapse its children.

#### Detached Results Viewer

Click the detach button (looks like a box with an arrow) in the upper-right corner of the results area to open the results in a separate, resizable window. This detached window provides a larger view that can be moved independently, allowing you to see more info.
All functionality from the main view is preserved:

* Search filter box to quickly find specific phrases.
* Sorting options (by appearance order, length, or structure).
* Expanding/collapsing nested phrases.
  You can use following keyboard shortcut in this viewer:
* `<kbd>` Ctrl + = `</kbd>`: Expand all items.
* `<kbd>` Ctrl + - `</kbd>`: Collapse all items.
* `<kbd>` Ctrl + F `</kbd>`: Focus the search filter input box.

#### Exporting Results

Click the `<button>` Export `</button>` button (located below the results area) to save the currently displayed results (or all results in batch mode).
**Export Options**:

* Choose an output format: `<format>` TXT `</format>`, `<format>` CSV `</format>`, or `<format>` JSON `</format>`.
* Optionally, enter a prefix to add to the beginning of the exported filename(s).
* Select a destination directory to save the file(s).
  **Batch Export**: If you processed multiple files, clicking Export saves results for *all* processed files, each to its own output file in the chosen directory and format.
  **Single Export**: If you processed text input or a single file, one output file is saved.

#### Filename Structure

Exported files are named automatically:

* **Batch Export File:** `[prefix]_[original_filename]_anpe_results_YYYYMMDD_HHMMSS.format`
* **Text Input Export:** `[prefix]_anpe_text_results_YYYYMMDD_HHMMSS.format`
* **Single File Export:** `[prefix]_[original_filename]_anpe_results_YYYYMMDD_HHMMSS.format`

Where:

* `[prefix]` is the optional prefix you entered.
* `original_filename` is the name of the input file (without extension).
* `YYYYMMDD_HHMMSS` is the timestamp of the export.
* `format` is the selected format extension (txt, csv, json).

### Status Bar & Log Panel

The status bar at the bottom provides real-time feedback. Clicking its left side (message area) toggles the Log Panel for detailed messages.

**Status Bar Components**:
    *   **Message Area (Left)**: Displays current status (e.g., `<option>` ANPE Ready `</option>`, `<option>` Processing... `</option>`, `<option>` Error `</option>`). Color indicates message type (red for errors, orange for warnings).
    *   **Activity Indicators (Right)**:
        *   **Pulsing Circle**: Visual cue for activity:
            *   Green (Static/Hidden): Idle.
            *   Blue (Pulsing): Busy/Processing (e.g., file processing, model loading).
            *   Yellow (Pulsing): Background check (e.g., model status).
            *   Orange (Pulsing): Warning active.
            *   Red (Pulsing): Error occurred.
        *   **Progress Bar**: Shows progress for longer tasks:
            *   Idle: `<option>` Waiting for tasks `</option>`.
            *   Determinate: Percentage (e.g., `<option>` 75% `</option>`) during tasks like batch processing.
            *   Completion: Shows `<option>` Completing... `</option>` then `<option>` Complete `</option>` on success.
**Log Panel**: Toggled via the status bar message area. Shows detailed logs for processing, model loading, warnings, and errors. Useful for troubleshooting.

### Settings Dialog

Click the gear icon (`<q>` ⚙️ `</q>`) in the top-right corner to open the Settings dialog. This allows you to manage models, update the core library, and view application information.

#### Models Page

**Usage Preference**: If you have multiple spaCy or Benepar models installed, select your preferred model for ANPE to use by default.
**Model Status & Management**:

* View installation status for spaCy models (e.g., `en_core_web_sm`, `md`, `lg`, `trf`) and Benepar models (`benepar_en3`, `benepar_en3_large`).
* `<button>` Install `</button>` / `<button>` Uninstall `</button>`: Manage individual models (requires internet).
* `<button>` Refresh Status `</button>`: Re-check your environment for installed models.
* `<button>` Install Defaults `</button>`: Installs essential models if any are missing. (Hold **Alt** to activate `<button>` Clean Models `</button>` button, which removes all installed models—useful for resolving model-related issues; `<button>` Clean Models `</button>` `<button>`  `</button>` also displays if all models are installed).

#### Core Page

**ANPE Library Version**: Displays the currently installed version of the underlying `anpe` Python library.
**Check for Updates**: Queries the Python Package Index (PyPI) to see if a newer version of the `anpe` library is available.
**Update Core**: If an update is available, this button allows you to upgrade the `anpe` library directly using `pip`. Requires an internet connection and potentially administrator privileges depending on your Python setup.

#### About Page

* Displays version information for the ANPE GUI and the core `anpe` library, provides links to the project's GitHub repository and contact information, and includes license details for the GUI and its dependencies.
* **GUI Update Check**:
    * When you open the About page, it automatically checks for newer versions of ANPE Studio on GitHub.
    * You can click the status icon or text to manually trigger a new check at any time.
    * If an update is found, an update icon will appear next to the version. Clicking this icon will take you to the GitHub releases page to download the new version.


## Tips

### Choose the right export format

**`<format>` TXT `</format>` Format (.txt)**

* Outputs noun phrases in a human-readable, plain text format.
* Nested phrases are shown using indentation.
* **Recommendation:** Best for quick reading, simple lists, or when you just need the plain text of the phrases, especially top-level ones.

**`<format>` CSV `</format>` Format (.csv)**

* Outputs results as Comma-Separated Values, suitable for spreadsheets (like Excel).
* Provides a flat structure where each row is a noun phrase.
* Hierarchy is represented using `ID` and `Parent_ID` columns.
* Includes columns for `Level`, `Length`, and `Structures` if metadata is enabled.
* **Recommendation:** Best for importing into spreadsheets or other data analysis tools that work well with tabular data.

**`<format>` JSON `</format>` Format (.json)**

* Outputs results in JavaScript Object Notation.
* Maintains the full hierarchical structure using nested objects.
* Includes all metadata.
* **Recommendation:** Best for programmatic use, preserving hierarchy, or detailed inspection.

### Performance

Extracting from large files or many files can take time. Monitor the status bar at the bottom for progress updates and any potential errors. If you find processing takes too long, please consider installing and using smaller models.

### Batch Processing

When extracting from a directory, ANPE saves one output file per input file; You may wish to set up a new folder to save these files, and add prefix to your filename to help you identify the batch of processing.

## Acknowledgements

The ANPE GUI relies on several open-source libraries:

* **PyQt6** (GPLv3 or Commercial): For the graphical user interface framework
* **spaCy** (MIT License): For initial text processing (tokenization, sentence segmentation)
* **Benepar** (MIT License): For constituency parsing (identifying phrase structures)
* **NLTK** (Apache License 2.0): Used by Benepar for model management

We are grateful for the developers of these packages that make ANPE and ANPE GUI possible. You can find more detailed license information in the application's About dialog.