# ANPE GUI

[![ANPE GUI Banner Placeholder](pics/placeholder_banner.png)](https://github.com/rcverse/anpe-gui) <!-- TODO: Replace with actual banner -->

**The user-friendly way to extract noun phrases!**

ANPE GUI provides an intuitive graphical interface for the powerful [ANPE (Another Noun Phrase Extractor)](https://github.com/rcverse/another-noun-phrase-extractor) Python library. It provides a user-friendly way to extract noun phrases from text—**no coding required**.


---


## ✨ Features

ANPE GUI packs a range of features to streamline your noun phrase extraction workflow:

*   **✍️ Flexible Input:** Paste text directly or process single/multiple `.txt` files.
*   **⚙️ Granular Control:** Configure extraction options like including nested phrases, adding metadata (source filename), and handling sentence boundaries.
*   **🔍 Powerful Filtering:** Refine results by filtering phrases based on word count (min/max length) or specific grammatical structures (e.g., *Determiner*, *Compound*, *Possessive*).
*   **📊 Clear Results View:** Displays extracted phrases in a structured, hierarchical tree, revealing relationships between nested phrases. You may also pop out the results into a separate, resizable window for focused analysis or comparison.
*   **💾 Versatile Export:** Save your extracted noun phrases to multiple formats: plain text (`.txt`), comma-separated values (`.csv`), or structured data (`.json`).
*   **📚 Easy Model Management:** Install, uninstall, and manage required spaCy and Benepar language models directly within the app via Settings (internet connection needed).
*   **🔄 Core Library Updates:** Check for and install updates to the underlying ANPE extraction engine with a single click in Settings.
*   **📜 Detailed Logging:** A toggleable log panel (accessible from the status bar) provides insights into the extraction process and aids in troubleshooting.

---

## 📸 Screenshots

***(PLACEHOLDER: Add Screenshots Here!)***

*We need screenshots to visually demonstrate the application. Please add images showcasing:*

*   `[Screenshot: Main Window - Input Tab]`
*   `[Screenshot: Main Window - Output Tab with Results Tree]`
*   `[Screenshot: Settings - Models Page]`
*   `[Screenshot: Detached Results Viewer Window]`
*   `[Screenshot: Export Dialog]`

---

## 🚀 Getting Started

Getting ANPE GUI running is simple:

1.  **Download:** Visit the **[Releases Page](https://github.com/rcverse/anpe-gui/releases)** and download the latest installer for your operating system. <!-- Confirm link points to Releases -->
2.  **Install (Windows):**
    *   Run the downloaded `.exe` setup file.
    *   Follow the on-screen prompts. The installer creates a self-contained folder for ANPE GUI (preventing conflicts with other Python tools you might have) and downloads the necessary base language models.
3.  **Install (macOS):**
    *   *macOS support is currently under development. Installation instructions will be provided when available.*
4.  **Launch:** Find and start ANPE GUI from your Windows Start Menu or Applications folder (macOS, when available).
5.  **First Run:** The application might take a few moments on its first launch to verify language models (requires an internet connection).

---

## 💡 Basic Usage Guide

1.  Open ANPE GUI and go to the **Input** tab.
2.  Choose how to add your text:
    *   **Add Files:** Click "Add Files..." or "Add Directory..." to select one or more `.txt` files.
    *   **Paste Text:** Copy your text and paste it into the large text area.
3.  Adjust **Configuration** options in the right-hand panel as needed (e.g., check "Include nested phrases", set length filters).
4.  Click the **Process** button. You can monitor progress in the status bar at the bottom.
5.  Navigate to the **Output** tab. The extracted noun phrases will appear in the tree view. If you processed multiple files, use the dropdown menu at the top to switch between file results.
6.  Click the **Export** button to save the currently viewed results. Choose your desired format (`.txt`, `.csv`, `.json`) and save location.

For a more detailed exploration of all features, please refer to the built-in **Help Guide**.

---

## 🛠️ Core Runtime Libraries

ANPE GUI integrates several powerful open-source libraries to provide its functionality. The application installer bundles these so you don't have to manage them separately:

*   [ANPE Core](https://github.com/rcverse/another-noun-phrase-extractor): The fundamental noun phrase extraction engine.
*   [PyQt6](https://riverbankcomputing.com/software/pyqt/): The framework used to build the graphical user interface.
*   [spaCy](https://spacy.io/): Provides core natural language processing capabilities.
*   [Benepar](https://github.com/nikitakit/self-attentive-parser): Enables advanced constituency parsing needed for detailed phrase structure.
*   [NLTK](https://www.nltk.org/): Used by Benepar for managing its language models.

---

## ❓ Troubleshooting

Encountering issues? Here are a few common solutions:

*   **Model Downloads:** Ensure you have a stable **internet connection** when installing/updating models (during setup or via Settings). Firewalls might sometimes block downloads.
*   **Model Errors:** If extraction fails with model-related errors, try the **Settings > Models > Clean Models** tool to reset them, then try installing again.
*   **Check Logs:** Click the Status Bar at the bottom of the main window to toggle the **Log Panel**. It often contains detailed error messages.
*   **Consult Help:** Press `F1` or go to `Help > Show Help` for the built-in guide.
*   **Report Bugs:** If problems persist, please check existing [issues](https://github.com/rcverse/anpe-gui/issues) or [report a new one](https://github.com/rcverse/anpe-gui/issues/new). Include details from the Log Panel if possible! <!-- Confirm issue tracker link -->

---

## 💻 Development

Interested in contributing, building from source, or understanding the build process?

*   This project uses **PyInstaller** to package the Python application and its dependencies into a standalone executable for easier distribution on Windows.
*   Please see the [**Developer README (docs/DEV_README.md)**](docs/DEV_README.md) for detailed setup and build instructions.

---

## 📄 License

This project is distributed under the MIT License. See the [LICENSE](LICENSE) file for full details. <!-- Confirm LICENSE file exists and is MIT -->

---

## 🙏 Acknowledgements

ANPE GUI is made possible by the excellent work of the developers and communities behind:

*   **PyQt6, spaCy, Benepar, and NLTK:** The core libraries providing the application's functionality.
*   **PyInstaller:** The tool used to create the distributable package for Windows users.

We are grateful for their contributions to the open-source ecosystem.

---

## 🎓 Citation

If ANPE GUI aids your research or project work, we kindly request that you cite the core **[ANPE library](https://github.com/rcverse/another-noun-phrase-extractor#citation)** that performs the extraction. Citation details can be found on the ANPE library's repository page. 