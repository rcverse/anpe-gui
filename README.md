# ANPE GUI

[![ANPE GUI Banner Placeholder](pics/placeholder_banner.png)](https://github.com/rcverse/anpe-gui) <!-- Replace with actual banner -->

**The user-friendly way to extract noun phrases!**

ANPE GUI provides an intuitive graphical interface for the powerful [ANPE (Another Noun Phrase Extractor)](https://github.com/rcverse/another-noun-phrase-extractor) Python library. It's designed specifically for researchers, students, analysts, and anyone who needs to extract noun phrases from text *without* writing any code.

This application bundles all necessary dependencies and guides you through model setup, offering a standalone experience for **Windows**. macOS support is planned for a future release.

---

## ✨ Features

*   **🖥️ Intuitive Interface:** Clean, tabbed layout (Input/Output) for a smooth workflow.
*   **✍️ Flexible Input:** Paste text directly or process single/multiple `.txt` files using file dialogs.
*   **⚙️ Granular Control:** Easily configure extraction options like including nested phrases, adding metadata, and handling sentence boundaries.
*   **🔍 Powerful Filtering:** Refine your results by filtering noun phrases based on word count (min/max length) or specific structural patterns (e.g., *Determiner*, *Compound*, *Possessive*).
*   **📊 Clear Results View:** Display extracted phrases in a structured, hierarchical tree view, showing relationships between nested phrases.
*   **✨ Detached Viewer:** Pop out the results into a separate, resizable window for detailed analysis.
*   **💾 Versatile Export:** Save extracted noun phrases to user-friendly formats: `.txt`, `.csv`, or `.json`.
*   **📚 Easy Model Management:** Install, uninstall, and manage required spaCy and Benepar language models directly within the app via the Settings dialog (internet required).
*   **🔄 Core Library Updates:** Check for and install updates to the underlying ANPE library with a single click.
*   **📜 Detailed Logging:** A toggleable log panel provides detailed information about the extraction process and helps troubleshoot issues.

---

## 📸 Screenshots

*Add screenshots here to showcase the interface:*

*   `[Screenshot: Main Window - Input Tab]`
*   `[Screenshot: Main Window - Output Tab]`
*   `[Screenshot: Settings - Models Page]`
*   `[Screenshot: Detached Results Viewer]`

---

## 🚀 Getting Started

1.  **Download:** Grab the latest installer for your operating system from the **[Releases Page](https://github.com/rcverse/anpe-gui/releases)**. <!-- Update link if needed -->
2.  **Install (Windows):**
    *   Run the downloaded `.exe` installer.
    *   Follow the on-screen prompts. The installer handles setting up an isolated environment and downloading the necessary base models.
3.  **Install (macOS):**
    *   *macOS support is currently under development and not yet available in releases.*
4.  **Launch:** Start ANPE GUI from your Start Menu (Windows) or Applications folder (macOS, when available).
5.  **First Run:** On first launch, the app might take a moment to verify/download language models (requires internet).

---

## 💡 Basic Usage

1.  Navigate to the **Input** tab.
2.  Choose your input method:
    *   **Text Input:** Paste your text directly into the large text box.
    *   **File Input:** Click "Add Files" or "Add Directory" to select `.txt` files.
3.  Adjust **Configuration** settings on the right panel (e.g., enable "Include nested phrases", set length filters, select structure filters).
4.  Click the **Process** button. Watch the status bar for progress.
5.  Switch to the **Output** tab to view the extracted noun phrases. If you processed multiple files, use the dropdown menu to select a file's results.
6.  Click the **Export** button to save the results to your computer (choose format and location).

For a detailed walkthrough of all features and options, please consult the built-in **Help Guide** accessible from the application menu (`Help > Show Help` or press `F1`).

---

## 🛠️ Dependencies

ANPE GUI bundles its core dependencies for a smooth user experience. It relies on these outstanding open-source libraries:

*   [ANPE Core](https://github.com/rcverse/another-noun-phrase-extractor): The underlying extraction engine.
*   [PyQt6](https://riverbankcomputing.com/software/pyqt/): For the graphical user interface.
*   [spaCy](https://spacy.io/): For natural language processing foundations.
*   [Benepar](https://github.com/nikitakit/self-attentive-parser): For constituency parsing.
*   [NLTK](https://www.nltk.org/): Used by Benepar for model management.

---

## ❓ Troubleshooting

*   Ensure you have a stable **internet connection** when installing models via the Settings dialog or during the initial setup.
*   If you encounter errors related to models, try the **Settings > Models > Clean Models** tool.
*   Check the **Log Panel** (click the Status Bar at the bottom to toggle) for detailed error messages.
*   Consult the built-in **Help Guide** (`F1`).
*   If problems persist, please [report an issue](https://github.com/rcverse/anpe-gui/issues). <!-- Update link if needed -->

---

## 💻 Development

Interested in contributing or building from source? Please see the [Developer README](docs/DEV_README.md) for instructions.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. <!-- Assuming MIT License. Verify LICENSE file exists -->

---

## 🙏 Acknowledgements

ANPE GUI is built upon the fantastic work of the developers behind PyQt6, spaCy, Benepar, and NLTK.

---

## 🎓 Citation

If you use ANPE GUI in your research or projects, we kindly ask that you cite the core **[ANPE library](https://github.com/rcverse/another-noun-phrase-extractor#citation)** upon which it is built. 