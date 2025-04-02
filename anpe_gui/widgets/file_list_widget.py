"""
File list widget for selecting and managing files for processing.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QLabel, QMessageBox
)
from PyQt6.QtCore import pyqtSignal


class FileListWidget(QWidget):
    """
    Widget for selecting and managing multiple files for processing.
    Supports adding individual files, directories of files, and removing files.
    """
    
    # Signal emitted when the file list changes
    filesChanged = pyqtSignal(list)  # List of file paths
    
    def __init__(self, parent=None):
        """
        Initialize the file list widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # File paths
        self.file_paths = []
        
        # Set up the UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Files to Process")
        title_label.setProperty("subheading", True)
        main_layout.addWidget(title_label)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(150)
        main_layout.addWidget(self.file_list)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("Add Files...")
        self.add_files_btn.setToolTip("Select one or more files to add to the processing list")
        self.add_files_btn.clicked.connect(self.add_files)
        
        self.add_dir_btn = QPushButton("Add Directory...")
        self.add_dir_btn.setToolTip("Add all text files from a directory")
        self.add_dir_btn.clicked.connect(self.add_directory)
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setToolTip("Remove selected files from the list")
        self.remove_btn.clicked.connect(self.remove_selected)
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setToolTip("Remove all files from the list")
        self.clear_btn.clicked.connect(self.clear_files)
        
        button_layout.addWidget(self.add_files_btn)
        button_layout.addWidget(self.add_dir_btn)
        button_layout.addWidget(self.remove_btn)
        button_layout.addWidget(self.clear_btn)
        
        main_layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("No files selected")
        main_layout.addWidget(self.status_label)
    
    def add_files(self):
        """Add files to the list using a file dialog."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Process", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_paths:
            for path in file_paths:
                if path not in self.file_paths:
                    self.file_paths.append(path)
                    item = QListWidgetItem(os.path.basename(path))
                    item.setToolTip(path)  # Show full path on hover
                    self.file_list.addItem(item)
            
            self.update_status()
            self.filesChanged.emit(self.file_paths)
    
    def add_directory(self):
        """Add all text files from a directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Directory with Text Files"
        )
        
        if dir_path:
            # Find all .txt files in the directory
            text_files = []
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.endswith('.txt'):
                        text_files.append(os.path.join(root, file))
            
            # Add files to the list
            for path in text_files:
                if path not in self.file_paths:
                    self.file_paths.append(path)
                    item = QListWidgetItem(os.path.basename(path))
                    item.setToolTip(path)  # Show full path on hover
                    self.file_list.addItem(item)
            
            # Show message if no text files found
            if not text_files:
                QMessageBox.information(
                    self, "No Text Files", 
                    f"No text files (.txt) found in directory: {dir_path}"
                )
            
            self.update_status()
            self.filesChanged.emit(self.file_paths)
    
    def remove_selected(self):
        """Remove selected files from the list."""
        selected_items = self.file_list.selectedItems()
        
        for item in selected_items:
            index = self.file_list.row(item)
            self.file_list.takeItem(index)
            file_path = self.file_paths[index]
            self.file_paths.remove(file_path)
        
        self.update_status()
        self.filesChanged.emit(self.file_paths)
    
    def clear_files(self):
        """Clear all files from the list."""
        self.file_list.clear()
        self.file_paths = []
        self.update_status()
        self.filesChanged.emit(self.file_paths)
    
    def update_status(self):
        """Update the status label with file count."""
        count = len(self.file_paths)
        
        if count == 0:
            self.status_label.setText("No files selected")
        elif count == 1:
            self.status_label.setText("1 file selected")
        else:
            self.status_label.setText(f"{count} files selected")
    
    def get_files(self):
        """
        Get the list of selected file paths.
        
        Returns:
            List of file paths
        """
        return self.file_paths.copy() 