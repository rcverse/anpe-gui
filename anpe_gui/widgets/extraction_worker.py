"""
Worker class for asynchronous noun phrase extraction.
"""

from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, pyqtSlot
import traceback
import sys

class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread."""
    
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)


class ExtractionWorker(QRunnable):
    """Worker thread for running extraction tasks."""
    
    def __init__(self, extractor, text, metadata=False, include_nested=False):
        """
        Initialize the extraction worker.
        
        Args:
            extractor: ANPEExtractor instance
            text: Text to process
            metadata: Whether to include metadata
            include_nested: Whether to include nested NPs
        """
        super().__init__()
        
        self.extractor = extractor
        self.text = text
        self.metadata = metadata
        self.include_nested = include_nested
        
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        """Run the extraction task in a separate thread."""
        try:
            # Run the extraction
            result = self.extractor.extract(
                text=self.text,
                metadata=self.metadata,
                include_nested=self.include_nested
            )
            
            # Emit the result signal
            self.signals.result.emit(result)
            
        except Exception as e:
            # Print the error traceback to stderr
            traceback.print_exc()
            
            # Emit the error signal
            self.signals.error.emit(str(e))
            
        finally:
            # Emit the finished signal
            self.signals.finished.emit() 