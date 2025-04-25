# ANPE GUI Packaging: cx_Freeze Implementation Plan (Strategy 3)

**Objective:** Transition the ANPE GUI packaging process from the current source-copying installer method to using `cx_Freeze` to create a launcher executable (`ANPE.exe`). This executable will leverage the separately installed embedded Python environment for large dependencies, while bundling the core `anpe_gui` application code within the `cx_Freeze` distribution (likely in `library.zip`) to avoid shipping loose `.py` files. A separate process (e.g., PyInstaller) will package the installer scripts and the `cx_Freeze`-built application bundle into a final distributable installer executable.

---

**Background:**

The ANPE GUI application relies on large Python libraries (PyTorch, spaCy, NLTK, etc.), making traditional single-file packaging difficult. The current solution uses a custom installer (`installer_core.py`, `setup_windows.pyw`) that deploys an embedded Python environment, installs dependencies via pip, and copies the raw `anpe_gui` source files.

This project aims to improve the packaging by:
1.  Creating a native-feeling launcher (`ANPE.exe`) using `cx_Freeze`.
2.  Avoiding the distribution of loose `.py` source files by letting `cx_Freeze` bundle the `anpe_gui` code.
3.  Continuing to leverage the embedded Python environment installed separately to manage large dependencies.
4.  Packaging the installer scripts themselves, along with the `cx_Freeze`-built application and other assets, into a single distributable installer file (e.g., `ANPE_Installer.exe`).

The core mechanism involves two main build stages:
*   **Stage 1 (Application Build - `cx_Freeze`):**
    *   A `launcher.py` script (at project root) acts as the entry point for `cx_Freeze`.
    *   `launcher.py` finds the embedded Python (installed later by the installer) and sets environment variables (`PYTHONHOME`, `PYTHONPATH`).
    *   `cx_Freeze` (configured via `setup.py`) builds `launcher.py` into `ANPE.exe`, bundling the `anpe_gui` code (excluding large libraries) into `library.zip`. Output goes to `build/anpe_dist/`.
*   **Stage 2 (Installer Build - e.g., `PyInstaller`):**
    *   A tool like PyInstaller packages the installer scripts (`installer_core.py`, `setup_windows.pyw`).
    *   It bundles necessary assets: the embedded Python zip, and the *entire output* of Stage 1 (`build/anpe_dist/`).
    *   The result is the final `ANPE_Installer.exe`.
*   **Installation:** Running `ANPE_Installer.exe` executes the logic in `installer_core.py`, which unpacks the embedded Python, installs dependencies, unpacks the `ANPE.exe` bundle (from its bundled assets) into the installation directory, and creates shortcuts.

**Projected Installed File Structure:**

To ensure clarity between the `cx_Freeze` build process and the `installer_core.py` deployment, the target installation directory (e.g., `C:\Program Files\ANPE\`) should have the following structure:

```
C:\Program Files\ANPE\  (Example Root Installation Directory)
├── ANPE.exe            # Built by cx_Freeze (contains launcher bytecode + Python DLL)
├── library.zip         # Built by cx_Freeze (contains anpe_gui + stdlib bytecode)
├── python3x.dll        # Core Python DLL, bundled by cx_Freeze (name may vary)
├── VCRUNTIME140.dll    # Example other DLLs bundled by cx_Freeze
├── ...                 # Other files/DLLs required by cx_Freeze
│
├── python\             # Deployed by installer_core.py (using embedded Python zip)
│   ├── python.exe      # Embedded Python interpreter
│   ├── pythonXY.dll
│   ├── Lib\            # Embedded Python Standard Library
│   │   └── site-packages\  # Dependencies installed by installer_core.py
│   │       ├── torch\
│   │       ├── spacy\
│   │       └── ...       # Other large dependencies
│   └── ...             # Other embedded Python files (DLLs, Scripts, etc.)
│
└── uninstall.exe       # Deployed/created by the final installer build stage
└── ...                 # Potentially docs, licenses, other assets copied by installer
```

This structure clarifies that:
*   The `cx_Freeze` build (`ANPE.exe`, `library.zip`, core DLLs) resides in the root.
*   The full embedded Python environment, including large dependencies, resides in the `python\` subdirectory, managed entirely by the installer.
*   `launcher.py` (running inside `ANPE.exe`) must correctly locate this `python\` subdirectory relative to itself.

---

**Steps:**

1.  **Prerequisites: Install `cx_Freeze`**
    *   **Goal:** Ensure `cx_Freeze` is available for building the application bundle.
    *   **Action:** Run `pip install cx_Freeze`.
    *   **Status:** Completed.

2.  **Create `launcher.py` Script**
    *   **Goal:** Create the entry point script for the `cx_Freeze` application build.
    *   **Action:** Create `launcher.py` in the **project root** (`/`). Implement logic as previously defined (find embedded python relative to `ANPE.exe`, set env vars, run `anpe_gui` entry point like `anpe_gui.__main__`).
    *   **Caveat:** Assumes `ANPE.exe` will reside in the root install directory. Ensure `anpe_gui` entry point is correct.
    *   **Review:** Verify logic in `launcher.py`.

3.  **Create `setup.py` for `cx_Freeze` (Application Build)**
    *   **Goal:** Create the `cx_Freeze` build script for `ANPE.exe`.
    *   **Action:** Create `setup.py` in the **project root** (`/`). Configure `build_exe_options` (excludes, output dir `build/anpe_dist`). Define `Executable` pointing `script` to root `launcher.py`. Ensure `base="Win32GUI"`.
    *   **Caveat:** Ensure `excludes` list is correct. `anpe_gui` should NOT be in `include_files`.
    *   **Review:** Check `excludes`, `build_exe` path, `Executable` script path (`launcher.py`).

4.  **Perform Initial `cx_Freeze` Build (Application Bundle)**
    *   **Goal:** Generate the `ANPE.exe` application bundle.
    *   **Action:** Run `python setup.py build` from the project root.
    *   **Caveat:** Use the correct Python environment.
    *   **Review:** Examine `build/anpe_dist/`. Verify `ANPE.exe`, `library.zip`, DLLs are present. No `anpe_gui` source folder. Size should be relatively small.

5.  **Modify `installer_core.py`**
    *   **Goal:** Update installer logic to deploy the `cx_Freeze` bundle from assets.
    *   **Action:** Replace `copy_app_code` with `copy_built_app`. This function needs to find and copy the *contents* of the `anpe_dist` directory (which will be bundled *inside* the final installer by Step 8) to the `target_install_path`. Add error handling. Ensure `find_asset` or similar logic can locate the bundled `anpe_dist` data within the running installer executable.
    *   **Caveat:** Logic to access data files bundled within a PyInstaller/cx_Freeze executable is needed (e.g., checking `sys._MEIPASS`).
    *   **Review:** Verify old code removed, new copy logic targets the bundled asset path correctly.

6.  **Update Shortcut Creation in `installer_core.py`**
    *   **Goal:** Point shortcuts to `ANPE.exe`.
    *   **Action:** Modify `create_shortcuts` to target `os.path.join(target_install_path, "ANPE.exe")`.
    *   **Review:** Confirm shortcut target path.

7.  **Update Windows Registry Entries (in `setup_windows.pyw`)**
    *   **Goal:** Update Add/Remove Programs entries.
    *   **Action:** Update `_register_application` in `setup_windows.pyw` to set `DisplayIcon` to `os.path.join(install_path, "ANPE.exe")`.
    *   **Review:** Confirm registry paths referencing the executable.

8.  **Package the Distributable Installer (`ANPE_Installer.exe`)**
    *   **Goal:** Create the final single-file installer executable that end-users will download and run.
    *   **Action:** Choose and implement a method for packaging the installer scripts:
        *   **Option A (PyInstaller):** Install PyInstaller (`pip install pyinstaller`). Create a PyInstaller spec file or run `pyinstaller` command targeting `setup_windows.pyw`. Configure it to bundle `installer_core.py`, other necessary installer modules/scripts, the embedded Python zip asset, AND the entire `build/anpe_dist/` folder (output of Step 4) as data files (`--add-data "build/anpe_dist:anpe_dist"`).
        *   **Option B (Second `cx_Freeze` build):** Create `setup_installer.py`. Configure it to build `setup_windows.pyw`, including `installer_core.py` etc., the Python zip asset, AND the `build/anpe_dist` folder using `include_files`.
        *   **Option C (Inno Setup/NSIS):** Write an `.iss` or `.nsi` script to bundle the assets (Python zip, `build/anpe_dist/`) and potentially helper scripts. Compile using Inno Setup or NSIS tools.
    *   **Caveat:** Correctly bundling the `build/anpe_dist` folder as data accessible by `installer_core.py` (Step 5) is crucial. PyInstaller often uses `sys._MEIPASS` to locate bundled data at runtime.
    *   **Review:** Confirm the chosen method successfully creates a single installer executable. Verify that the installer, when run, can access and extract the embedded Python zip and the `anpe_dist` data.

9.  **End-to-End Testing**
    *   **Goal:** Verify the complete process using the final distributable installer.
    *   **Action:**
        *   Build the final `ANPE_Installer.exe` using the method from Step 8.
        *   Run `ANPE_Installer.exe` on a clean machine/VM.
        *   Verify installation creates the correct structure (e.g., `C:\Program Files\ANPE\` contains `ANPE.exe`, `library.zip`, `python\` folder). No `anpe_gui` source.
        *   Verify shortcuts.
        *   Launch `ANPE.exe`. Test functionality (ensure it uses embedded Python deps).
        *   Test uninstallation.
    *   **Caveat:** Clean environment testing is essential.
    *   **Review:** Confirm successful installation, launch, function, cleanup.

10. **Reflection:**
    *   **Goal:** Review the effectiveness of the entire process.
    *   **Action:** Assess if `cx_Freeze` bundled the app correctly, if the installer packaging worked, if the runtime linking to embedded Python is robust. Note any unexpected files, errors, or areas for improvement. Adjust configurations as needed.

--- 