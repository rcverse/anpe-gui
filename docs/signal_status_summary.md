# ANPE GUI Signal and Status System Summary

This document summarizes the signal and status management across the main components of the ANPE GUI application, focusing on `MainWindow`, `SettingsDialog`, `StatusBar`, and their associated worker threads.

## Overall Architecture

The GUI uses PyQt's signal-slot mechanism extensively for communication between UI components and background worker threads. This ensures the UI remains responsive during potentially long-running operations like text processing, model downloads, installations, and updates.

-   **`MainWindow`:** Acts as the central hub for core processing tasks. It manages the main input/output flow, initiates text/file processing using workers (`ExtractionWorker`, `BatchWorker`), and displays global status via the `StatusBar`. It also launches the `SettingsDialog`.
-   **`SettingsDialog`:** A separate window for managing application settings, core library updates, and model installations/management. It contains multiple pages (`ModelsPage`, `CorePage`), each managing its own specific tasks and UI updates, often using dedicated worker threads (`settings_workers.py`).
-   **`StatusBar`:** A dedicated widget within `MainWindow` providing visual feedback on the application's current state (ready, busy, error, success) and progress for ongoing tasks. It uses a text label, a progress bar, and a pulsing activity indicator.
-   **Workers (`workers/` directory):** `QObject` subclasses designed to run in separate `QThread`s. They perform the actual work (e.g., calling ANPE core functions, running pip, checking models) and communicate back to the UI thread using signals (e.g., `progress`, `finished`, `error`, `result`, `log_message`).

## Signal/Status Flow

1.  **Initialization:** `main.py` runs `ModelStatusChecker` first. The result (a dictionary containing found models and any initial error) is passed to the `MainWindow` constructor.
2.  **`MainWindow` State:** `MainWindow` uses this initial status to set its `extractor_ready` flag and display the initial status message (Ready, Warning, or Error) in the `StatusBar`. Processing buttons are enabled/disabled accordingly. If models are missing, a popup prompts the user.
3.  **Processing (`MainWindow`):**
    *   User initiates processing.
    *   Configuration is gathered.
    *   Appropriate worker (`ExtractionWorker` or `BatchWorker`) is started in a thread.
    *   `StatusBar` shows "busy" state and progress (indeterminate for single text, determinate for batch).
    *   Worker emits `progress`, `status_update`, `result`/`file_result`, `error`, and `finished` signals.
    *   `MainWindow` slots handle these signals to update the `StatusBar`, display results in the "Output" tab, log messages, and handle errors.
    *   On `finished`, `MainWindow` updates the `StatusBar` to success/error/info, enables/disables buttons, and potentially switches to the "Output" tab.
4.  **Settings (`SettingsDialog`):**
    *   User opens `SettingsDialog` from `MainWindow`. The initial model status known by `MainWindow` is passed to the dialog.
    *   `ModelsPage` and `CorePage` manage their respective actions (model install/uninstall, core update check/run).
    *   Each page uses its own workers (`settings_workers.py`) in separate threads.
    *   Page-specific UI elements (status labels, buttons, activity indicators) are updated via signals from these workers (`progress`, `finished`, `log_message`). Detailed command output is often streamed to a log dialog via `log_message`.
    *   The `SettingsDialog` prevents closing if a worker is active.
5.  **Interaction (`SettingsDialog` -> `MainWindow`):**
    *   When a model installation/uninstallation completes in `ModelsPage`, it emits the `models_changed` signal.
    *   When model usage preferences are changed in `ModelsPage`, it emits the `model_usage_changed` signal.
    *   `MainWindow` has slots connected to these signals.
    *   `on_models_changed`: `MainWindow` re-runs the `ModelStatusChecker` worker in the background to get the latest model status, then updates its own `extractor_ready` state and the `StatusBar`.
    *   `on_model_usage_preference_changed`: `MainWindow` currently just logs this; the preferences are read directly from `QSettings` when processing is next started.

## Collaboration vs. Independence

-   **Collaboration:** `MainWindow` and `SettingsDialog` collaborate through the initial status passing and the `models_changed` / `model_usage_changed` signals. This ensures `MainWindow` is aware of potential changes affecting its processing readiness.
-   **Independence:** During operations *within* `SettingsDialog` (like installing a model or updating the core), the status updates are generally confined to that dialog's specific page UI (labels, indicators). The global `StatusBar` in `MainWindow` is *not* typically updated by actions within `SettingsDialog`. Each maintains its own context for ongoing background tasks. Error reporting uses `QMessageBox` popups within the relevant window context.

---

## Tables

### Table 1: MainWindow / StatusBar Signal & Status System

| Signal Emitted (by Worker)        | Status/Timing                                   | Corresponding Visuals (MainWindow / StatusBar)                                                                                                                               |
| :-------------------------------- | :---------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ModelStatusChecker.status_checked` | After background model check completes successfully | **StatusBar:** Text updated (e.g., "ANPE Ready" or "Missing models..."), style set ('ready'/'warning'). **Indicator:** `idle()` or `warn()`. **MainWindow:** `process_button` enabled/disabled. Optional popup if models missing. |
| `ModelStatusChecker.error_occurred` | If background model check fails critically      | **StatusBar:** Text updated ("Error checking status..."), style set ('error'). **Indicator:** `error()`. **MainWindow:** `process_button` disabled.                       |
| `ExtractionWorker.signals.result`   | Single text processing completes successfully   | **Output Tab:** Results displayed via `ResultDisplayWidget`. **MainWindow:** `export_button` enabled. (Final status bar/indicator update handled by `finished` signal).                      |
| `BatchWorker.signals.file_result`   | One file in batch completes successfully        | **Output Tab:** File added to selector combo; if first result, displayed via `ResultDisplayWidget`. **Log Panel:** "Processed file: ..." message.                              |
| `BatchWorker.signals.progress`      | During batch processing                         | **StatusBar:** Progress bar percentage updated. Text shows percentage. **Indicator:** `start()`.                                                                          |
| `BatchWorker.signals.status_update` | During batch processing (e.g., init/file read) | **StatusBar:** Text message updated (e.g., "Initializing ANPE...", "Reading file X..."). Progress bar state unchanged. **Indicator:** `start()`.                              |
| `Worker.signals.error`            | If any worker encounters an error               | **StatusBar:** Text shows error message, style 'error'. Progress stops. **Indicator:** `error()`. **MainWindow:** `QMessageBox` warning shown. `processing_error_occurred` flag set.                  |
| `Worker.signals.finished`         | When any worker thread finishes (single/batch)  | **StatusBar:** Shows "Processing complete" / "Processing finished with errors" / "...(No results)", style 'success'/'error'/'info'. **Indicator:** `idle()` or `error()` or `warn()` (if no results?). Resets to idle after timeout. **MainWindow:** `process_button` re-enabled (if `extractor_ready`). `export_button` enabled/disabled based on results/error. Input fields cleared. Switches to Output Tab on success with results. |
| *(Status Label Click)*            | User clicks the text label in StatusBar         | **MainWindow:** Toggles visibility of the `log_panel` splitter pane.                                                                                                          |

### Table 2: SettingsDialog Signal & Status System

| Signal Emitted (by Worker)           | Status/Timing                                                | Corresponding Visuals (SettingsDialog Page)                                                                                                                                |
| :----------------------------------- | :----------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ModelActionWorker.progress`         | During model install/uninstall                               | **ModelsPage:** `model_action_status_label` updated (e.g., "Downloading/installing...", "Attempting to uninstall..."). **Indicator:** `start()` (within page).                                                   |
| `InstallDefaultsWorker.progress`     | During default model install                                 | **ModelsPage:** `model_action_status_label` updated (e.g., "Starting default model setup..."). **Indicator:** `start()` (within page).                                                                           |
| `CleanWorker.progress`               | During model cleanup                                         | **ModelsPage:** `model_action_status_label` updated (e.g., "Starting model cleanup process...", "Cleaning spaCy models..."). **Indicator:** `start()` (within page).                                              |
| `CoreUpdateWorker.check_finished`    | After core version check from PyPI completes                 | **CorePage:** `latest_version_label` updated. `status_label` updated. `check_update_button` text/state changed ("Up to Date", "Update ANPE Core (...)"). **Indicator:** `idle()` (within page). |
| `CoreUpdateWorker.update_progress`   | During core update via pip                                   | **CorePage:** `status_label` updated (e.g., "Starting update process..."). **Indicator:** `start()` (within page).                                                                           |
| `Worker.log_message`                 | During subprocess execution (pip, spacy download, etc.)      | **ModelsPage/CorePage:** Message appended to internal `log_text`; if log dialog is open, `QTextEdit` inside it is updated.                                                 |
| `ModelActionWorker.finished`         | After model install/uninstall attempt completes              | **ModelsPage:** `QMessageBox` (Info/Warning/Error) shown. **Indicator:** `idle()` / `warn()` / `error()` (based on outcome). Calls `refresh_status`. Emits `models_changed`. |
| `InstallDefaultsWorker.finished`     | After default model install attempt completes                | **ModelsPage:** `QMessageBox` (Info/Warning/Error) shown. **Indicator:** `idle()` / `warn()` / `error()` (based on outcome). Calls `refresh_status`. Emits `models_changed`.                       |
| `CleanWorker.finished`               | After model cleanup attempt completes                        | **ModelsPage:** `QMessageBox` (Info/Warning/Error) shown. **Indicator:** `idle()` / `warn()` / `error()` (based on outcome). Calls `refresh_status`. Emits `models_changed`.                       |
| `CoreUpdateWorker.update_finished`   | After core update attempt completes                          | **CorePage:** `QMessageBox` (Info/Warning/Error) shown. **Indicator:** `idle()` / `warn()` / `error()` (based on outcome). `status_label`, etc. updated.      |
| `ModelsPage.models_changed`          | Emitted by `ModelsPage` after a model action worker finishes | *(Signal handled by MainWindow, see Table 3)*                                                                                                                             |
| `ModelsPage.model_usage_changed`     | Emitted by `ModelsPage` when usage combo box changes         | **ModelsPage:** Calls `save_usage_settings`. *(Signal handled by MainWindow, see Table 3)*                                                                               |
| *(Alt Key Press/Release)*           | When Alt key state changes while ModelsPage is active        | **ModelsPage:** `install_clean_button` text, tooltip, and 'danger' property updated ("Install Defaults" <> "Clean All").                                               |
| *(Button Clicks)*                   | User clicks Install/Uninstall/Clean/Refresh/Check etc.       | **ModelsPage/CorePage:** Relevant worker started. Buttons disabled. Status label updated ("Starting..."). **Indicator:** `start()` (within page).                               |

### Table 3: Signal Interaction (MainWindow <> SettingsDialog)

| Signal Emitted                 | Emitter           | Status/Timing                                       | Receiver          | Corresponding Visuals / Action (Receiver)                                                                                                                               |
| :----------------------------- | :---------------- | :-------------------------------------------------- | :---------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `models_changed`               | `SettingsDialog` (via `ModelsPage`) | After a model install/uninstall/clean action completes | `MainWindow`      | **MainWindow:** Calls `on_models_changed` -> Starts `ModelStatusChecker` worker. **StatusBar:** Shows "Checking model status...", then updates based on check result (see Table 1). |
| `model_usage_changed`          | `SettingsDialog` (via `ModelsPage`) | When model usage combo box value changes          | `MainWindow`      | **MainWindow:** Calls `on_model_usage_preference_changed` -> Logs the event. (Preferences are read later when processing starts).                                           |
| *(Dialog Initialization)*     | `MainWindow`      | When `SettingsDialog` is created                  | `SettingsDialog`  | **SettingsDialog:** Receives initial `model_status` dict from `MainWindow`. **ModelsPage:** Uses this status for initial UI setup (button states, status labels, combo population). |

---

## Indicator State Mapping

The `PulsingActivityIndicator` (used in the main `StatusBar` and potentially within `SettingsDialog` pages) now reflects the application state more granularly:

-   **Idle (Green Breathing):** Application is ready, processing completed successfully, or an operation finished with an informational status.
-   **Active (Blue Ripple):** A background task is currently in progress (processing text/files, downloading/installing models, checking for updates, running pip).
-   **Warning (Orange Faster Breathing):** Potential issues detected that don't prevent core functionality but require attention (e.g., missing optional models, non-critical check failures).
-   **Error (Red Blinking):** A critical error occurred (e.g., processing failed, installation failed, core component error).
