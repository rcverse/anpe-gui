# ANPE GUI

***One-click solution to extract complete noun phrases***

![Banner](./banner.png)

ANPE GUI provides an intuitive graphical interface for the powerful [ANPE (Another Noun Phrase Extractor)](https://github.com/rcverse/another-noun-phrase-extractor) Python library. It provides a user-friendly way to extract noun phrases from text—**no coding required**.

---

## ✨ Features

ANPE GUI packs a range of features:

* **✍️ Flexible Input:** Paste text directly or process single/multiple `.txt` files.
* **⚙️ Granular Control:** Configure extraction options like including nested phrases, adding metadata (source filename), and handling sentence boundaries.
* **🔍 Powerful Filtering:** Refine results by filtering phrases based on word count (min/max length) or specific grammatical structures (e.g., *Determiner*, *Compound*, *Possessive*).
* **📊 Clear Results View:** Displays extracted phrases in a structured, hierarchical tree, revealing relationships between nested phrases. You may also pop out the results into a separate, resizable window for focused analysis or comparison.
* **💾 Versatile Export:** Save your extracted noun phrases to multiple formats: plain text (`.txt`), comma-separated values (`.csv`), or structured data (`.json`).
* **📚 Easy Model Management:** Install, uninstall, and manage required spaCy and Benepar language models directly within the app via Settings (internet connection needed).
* **🔄 Core Library Updates:** Check for and install updates to the underlying ANPE extraction engine with a single click in Settings.
* **📜 Detailed Logging:** A toggleable log panel (accessible from the status bar) provides insights into the extraction process and aids in troubleshooting.

---

## 📸 Screenshots

### Main Input Area

![Main Input Tab](./software_screenshots/input_tab.png)
*Caption: The main input tab where users can paste or type their text for analysis.*

### Analysis Output Display

![Output Tab with Results](./software_screenshots/output_tab.png)
*Caption: The output tab showcasing the structured results of the NLP analysis.*

### Application Settings

![Settings Page](./software_screenshots/setting_page.png)
*Caption: The settings page, likely showing model management or other configuration options.*

### Detached Result Viewer

![Detached Result Viewer](./software_screenshots/detached_result_viewer.png)
*Caption: A detached window for viewing detailed analysis results, allowing for a flexible workspace.*

### Log Panel

![Log Panel Toggled](./software_screenshots/log_toggled.png)
*Caption: The application's log panel, useful for debugging and monitoring processes.*

---

## 🚀 Getting Started

Getting ANPE GUI running is simple:

1. **Download:** Visit the **[Releases Page](https://github.com/rcverse/anpe-gui/releases)** and download the latest installer for your operating system. `<!-- Confirm link points to Releases -->`
2. **Install (Windows):**
   * Run the downloaded `.exe` setup file.
   * Follow the on-screen prompts. The installer creates a self-contained folder for ANPE GUI (preventing conflicts with other Python tools you might have) and downloads the necessary base language models.
3. **Install (macOS):**
   * Run the downloaded `.dmg` file.
   * Drag the ANPE icon into the application folder
   * Start ANPE from Applications, and follow the on-screen prompts to setup the environment for first use.
4. **Launch:** Find and start ANPE GUI from your Windows Start Menu or Applications folder (macOS).

---

## 💡 Basic Usage Guide

1. Open ANPE GUI and go to the **Input** tab.
2. Choose how to add your text:
   * **Add Files:** Click "Add Files..." or "Add Directory..." to select one or more `.txt` files.
   * **Paste Text:** Copy your text and paste it into the large text area.
3. Adjust **Configuration** options as needed (e.g., check "Include nested phrases", set length filters).
4. Click the **Process** button. You can monitor progress in the status bar at the bottom.
5. Affter processing, you will be directed to the **Output** tab. The extracted noun phrases will appear in the tree view. If you processed multiple files, use the dropdown menu at the top to switch between file results.
6. Click the **Export** button to save the currently viewed results. Choose your desired format (`.txt`, `.csv`, `.json`) and save location.

For a more detailed exploration of all features, please refer to the built-in **Help Guide** (the question mark icon on the right upper corner).

---

## ❓ Troubleshooting

Encountering issues? Here are a few common solutions:

* **Model Downloads:** Ensure you have a stable **internet connection** when installing/updating models (during setup or via Settings). Firewalls might sometimes block downloads.
* **Model Errors:** If extraction fails with model-related errors, try the **Settings > Models > Clean Models** tool to reset them, then try installing again.
* **Check Logs:** Click the Status Bar at the bottom of the main window to toggle the **Log Panel**. It often contains detailed error messages.
* **Report Bugs:** If problems persist, please check existing [issues](https://github.com/rcverse/anpe-gui/issues) or [report a new one](https://github.com/rcverse/anpe-gui/issues/new). Include details from the Log Panel if possible! `<!-- Confirm issue tracker link -->`

---

## 📄 License

This project is distributed under the GNU General Public License. See the [LICENSE](LICENSE) file for full details.

---

## 🙌 Acknowledgements

ANPE GUI is made possible by the excellent work of the developers and communities behind the following open-source projects and tools:

### 🛠️ Core Runtime Libraries

The application installer bundles these core libraries so you don't have to manage them separately:

* **[ANPE Core](https://github.com/rcverse/another-noun-phrase-extractor)**: The fundamental noun phrase extraction engine.
* **[PyQt6](https://riverbankcomputing.com/software/pyqt/)**: The framework used to build the graphical user interface.
* **[spaCy](https://spacy.io/)**: Provides core natural language processing capabilities.
* **[Benepar](https://github.com/nikitakit/self-attentive-parser)**: Enables advanced constituency parsing needed for detailed phrase structure.
* **[NLTK](https://www.nltk.org/)**: Used by Benepar for managing its language models.

### 📦 Installer Creation & Distribution

Creating a user-friendly, distributable application relies on these powerful tools:

* **[PyInstaller](https://pyinstaller.org/)**: Used to package the Python application and its dependencies into a standalone executable for Windows.
* **[py2app](https://py2app.readthedocs.io/)**: (Planned/Used for macOS) Utilized for creating macOS application bundles.
* **[python-build-standalone](https://github.com/astral-sh/python-build-standalone)**: This project by Astral SH provides pre-built, distributable Python versions. We leverage these builds to create a consistent Python environment, particularly for our macOS distributions, simplifying the packaging process. The Python builds from this project are licensed under MPL-2.0, which is compatible with GPLv3, allowing their integration into ANPE GUI.

We are immensely grateful for the contributions of all these projects to the open-source ecosystem, enabling us to build and share ANPE GUI.

---

## 🎓 Citation

If ANPE GUI aids your research or project work, we kindly request that you cite the core **[ANPE library](https://github.com/rcverse/another-noun-phrase-extractor#citation)** that performs the extraction. Citation details can be found on the ANPE library's repository page.

---

## 💻 Development

* Please see the [**Developer README (docs/DEV_README.md)**](docs/DEV_README.md) for detailed developing-related information.
