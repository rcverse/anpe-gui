"""
Log handler for redirecting log messages to the GUI.
"""

import logging
from PyQt6.QtCore import QObject, pyqtSignal
import sys

class QtLogHandler(logging.Handler, QObject):
    """
    Log handler that redirects log messages to a QTextEdit widget.
    This allows log messages to be displayed in the GUI.
    """
    
    # Define a signal that emits the log message (str) and log level (int)
    log_signal = pyqtSignal(str, int)
    
    def __init__(self):
        """
        Initialize the log handler.
        """
        logging.Handler.__init__(self)
        QObject.__init__(self)
        
        # Set formatter
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        self.setFormatter(formatter)
    
    def emit(self, record):
        """
        Emit a log record by appending it to the text edit widget.
        
        Args:
            record: Log record to emit
        """
        try:
            msg = self.format(record)
            
            # Emit the log record as a signal
            self.log_signal.emit(msg, record.levelno)
            
        except Exception as e:
            # Fall back to stderr if something goes wrong
            print(f"Error in log handler: {e}", file=sys.stderr)
            print(record.getMessage(), file=sys.stderr) 