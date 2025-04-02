"""
Worker class for batch processing of multiple files.
"""

import os
import traceback
import sys
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, pyqtSlot

class BatchWorkerSignals(QObject):
    """Defines the signals available from a batch processing worker thread."""
    
    started = pyqtSignal()
    progress = pyqtSignal(int, int)  # current, total
    file_started = pyqtSignal(str)  # filename
    file_completed = pyqtSignal(str, object)  # filename, result
    file_error = pyqtSignal(str, str)  # filename, error message
    finished = pyqtSignal()
    error = pyqtSignal(str)
    results = pyqtSignal(object)  # combined results


class BatchWorker(QRunnable):
    """Worker thread for batch processing multiple files."""
    
    def __init__(self, extractor, directory, metadata=False, include_nested=False):
        """
        Initialize the batch processing worker.
        
        Args:
            extractor: ANPEExtractor instance
            directory: Directory containing text files to process
            metadata: Whether to include metadata
            include_nested: Whether to include nested NPs
        """
        super().__init__()
        
        self.extractor = extractor
        self.directory = directory
        self.metadata = metadata
        self.include_nested = include_nested
        
        self.signals = BatchWorkerSignals()
    
    @pyqtSlot()
    def run(self):
        """Run the batch processing task in a separate thread."""
        try:
            self.signals.started.emit()
            
            # Get list of text files in the directory
            text_files = []
            for root, _, files in os.walk(self.directory):
                for file in files:
                    if file.endswith('.txt'):
                        text_files.append(os.path.join(root, file))
            
            # Check if any files were found
            if not text_files:
                self.signals.error.emit("No text files found in the directory")
                return
            
            # Process each file
            results = {}
            total_files = len(text_files)
            
            for i, file_path in enumerate(text_files):
                try:
                    # Emit progress
                    self.signals.progress.emit(i, total_files)
                    
                    # Get filename for display
                    filename = os.path.basename(file_path)
                    
                    # Emit file started signal
                    self.signals.file_started.emit(filename)
                    
                    # Read the file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    
                    # Process the file
                    result = self.extractor.extract(
                        text=text,
                        metadata=self.metadata,
                        include_nested=self.include_nested
                    )
                    
                    # Store result
                    results[filename] = result
                    
                    # Emit file completed signal
                    self.signals.file_completed.emit(filename, result)
                    
                except Exception as e:
                    # Print the error traceback to stderr
                    traceback.print_exc()
                    
                    # Emit file error signal
                    self.signals.file_error.emit(filename, str(e))
            
            # Emit final progress
            self.signals.progress.emit(total_files, total_files)
            
            # Emit combined results
            self.signals.results.emit(results)
            
        except Exception as e:
            # Print the error traceback to stderr
            traceback.print_exc()
            
            # Emit the error signal
            self.signals.error.emit(str(e))
            
        finally:
            # Emit the finished signal
            self.signals.finished.emit() 