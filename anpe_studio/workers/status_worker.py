import logging
from PyQt6.QtCore import QObject, pyqtSignal

class ModelStatusChecker(QObject):
    """
    Worker thread to check the status of required models (spaCy, Benepar)
    without blocking the main GUI thread.
    """
    status_checked = pyqtSignal(dict)  # Emits dict with model status on success
    error_occurred = pyqtSignal(str)   # Emits error message string on failure
    progress_update = pyqtSignal(str)  # Emits progress step name

    def __init__(self, parent=None):
        super().__init__(parent)
        logging.debug("ModelStatusChecker worker initialized.")

    def run(self):
        """Checks for required models and emits the result or error."""
        logging.info("ModelStatusChecker: Starting model status check...")
        # Emit initial progress
        self.progress_update.emit('start')
        
        status = {
            'spacy_models': [],
            'benepar_models': [],
            'error': None
        }
        try:
            # Import necessary functions within the run method
            # This isolates potential ImportErrors if anpe is not fully installed
            self.progress_update.emit('check_models')
            from anpe.utils.model_finder import find_installed_spacy_models, find_installed_benepar_models
            logging.debug("ModelStatusChecker: ANPE utilities imported successfully.")

            # --- Perform Checks ---
            logging.debug("ModelStatusChecker: Checking spaCy models...")
            self.progress_update.emit('spacy_model')
            status['spacy_models'] = find_installed_spacy_models()
            logging.debug(f"ModelStatusChecker: Found spaCy models: {status['spacy_models']}")

            logging.debug("ModelStatusChecker: Checking Benepar models...")
            self.progress_update.emit('benepar_model')
            status['benepar_models'] = find_installed_benepar_models()
            logging.debug(f"ModelStatusChecker: Found Benepar models: {status['benepar_models']}")

            # Determine if core models are present
            has_spacy = len(status['spacy_models']) > 0
            has_benepar = len(status['benepar_models']) > 0
            
            # Debug log for troubleshooting
            logging.debug(f"ModelStatusChecker: Model detection results - spaCy: {has_spacy} (models={status['spacy_models']}), Benepar: {has_benepar} (models={status['benepar_models']})")

            if not (has_spacy and has_benepar): 
                missing = []
                if not has_spacy: missing.append("spaCy")
                if not has_benepar: missing.append("Benepar")
                warning_msg = f"Missing required models: {', '.join(missing)}"
                # Store as an 'error' for consistent handling, but it's a warning state
                status['error'] = warning_msg
                logging.warning(f"ModelStatusChecker: {warning_msg}")
                # Emit status_checked even with missing models, let receiver decide how to handle
                self.progress_update.emit('complete')
                logging.info(f"Background status check complete: {status}")
                self.status_checked.emit(status)
            else:
                logging.info("ModelStatusChecker: All required models/data found.")
                self.progress_update.emit('complete')
                logging.info(f"Background status check complete: {status}")
                self.status_checked.emit(status) # Emit successful status

        except ImportError as ie:
            error_msg = f"Initialization failed: Could not import ANPE components ({ie}). Ensure 'anpe' is installed correctly."
            logging.error(error_msg, exc_info=False) # Keep log concise
            status['error'] = error_msg
            # Emit error_occurred for critical import issues
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred during model status check: {e}"
            logging.error(error_msg, exc_info=True)
            status['error'] = error_msg
            # Emit error_occurred for other unexpected errors
            self.error_occurred.emit(error_msg)

        logging.debug("ModelStatusChecker: run() method finished.") 