"""
Log handler for redirecting log messages to the GUI.
"""

import logging
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QTextCursor
import sys

class QtLogHandler(logging.Handler):
    """
    Log handler that redirects log messages to a QTextEdit widget.
    This allows log messages to be displayed in the GUI.
    """
    
    def __init__(self, text_edit: QTextEdit):
        """
        Initialize the log handler.
        
        Args:
            text_edit: QTextEdit widget to display log messages
        """
        super().__init__()
        
        self.text_edit = text_edit
        
        # Set formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.setFormatter(formatter)
        
        # Add handler to the root logger
        logger = logging.getLogger()
        logger.addHandler(self)
        
        # Set level to match the root logger
        self.setLevel(logger.level)
    
    def emit(self, record):
        """
        Emit a log record by appending it to the text edit widget.
        
        Args:
            record: Log record to emit
        """
        try:
            # Format the log message
            msg = self.format(record)
            
            # Append to text edit
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            
            # Set text color based on log level
            if record.levelno >= logging.ERROR:
                self.text_edit.append(f"<span style='color:red'>{msg}</span>")
            elif record.levelno >= logging.WARNING:
                self.text_edit.append(f"<span style='color:orange'>{msg}</span>")
            elif record.levelno >= logging.INFO:
                self.text_edit.append(f"<span style='color:black'>{msg}</span>")
            else:  # DEBUG
                self.text_edit.append(f"<span style='color:gray'>{msg}</span>")
            
            # Make sure the new text is visible
            self.text_edit.ensureCursorVisible()
            
        except Exception as e:
            # Fall back to stderr if something goes wrong
            print(f"Error in log handler: {e}", file=sys.stderr)
            print(record.getMessage(), file=sys.stderr) 