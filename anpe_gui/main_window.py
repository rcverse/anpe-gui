"""
Main window implementation for the ANPE GUI application.
"""

import os
import sys
from typing import Optional, Dict, Any, List
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog, QSpinBox,
    QCheckBox, QComboBox, QGroupBox, QFormLayout, QLineEdit,
    QProgressBar, QMessageBox, QSplitter, QFrame
)
from PyQt6.QtGui import QIcon, QTextCursor, QPixmap

try:
    from anpe import ANPEExtractor, __version__ as anpe_version
except ImportError:
    QMessageBox.critical(
        None, 
        "Import Error", 
        "Could not import ANPE library. Please make sure it's installed."
    )
    sys.exit(1)

from anpe_gui.widgets.extraction_worker import ExtractionWorker
from anpe_gui.widgets.batch_worker import BatchWorker
from anpe_gui.widgets.log_handler import QtLogHandler
from anpe_gui.widgets.step_indicator import StepIndicator
from anpe_gui.widgets.file_list_widget import FileListWidget
from anpe_gui.widgets.structure_filter_widget import StructureFilterWidget
from anpe_gui.theme import PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR


class MainWindow(QMainWindow):
    """Main window for the ANPE GUI application."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("ANPE GUI - Another Noun Phrase Extractor")
        self.resize(1200, 800)
        
        # Set up the thread pool for background processing
        self.thread_pool = QThreadPool()
        
        # Set up the UI
        self.setup_ui()
        
        # Initialize extractor with default settings
        self.extractor = ANPEExtractor()
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage(f"ANPE GUI - Using ANPE v{anpe_version}")
        
        # Initialize progress bar in status bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def setup_ui(self):
        """Set up the main UI structure."""
        # Create the central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add header with banner (if available)
        self.setup_header()
        
        # Add step indicators
        self.setup_step_indicators()
        
        # Create a horizontal splitter for main content and log panel
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.main_splitter, 1)  # Give it stretch factor
        
        # Left side: Main workflow area with steps
        self.workflow_widget = QWidget()
        self.workflow_layout = QVBoxLayout(self.workflow_widget)
        self.workflow_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create stacked widget for different steps
        self.steps_stack = QStackedWidget()
        self.workflow_layout.addWidget(self.steps_stack, 1)  # Stretch
        
        # Add step pages
        self.config_page = self.create_config_page()
        self.input_page = self.create_input_page()
        self.output_page = self.create_output_page()
        
        self.steps_stack.addWidget(self.config_page)
        self.steps_stack.addWidget(self.input_page)
        self.steps_stack.addWidget(self.output_page)
        
        # Add navigation buttons
        self.setup_navigation()
        
        # Right side: Log panel
        self.log_panel = self.create_log_panel()
        
        # Add widgets to splitter
        self.main_splitter.addWidget(self.workflow_widget)
        self.main_splitter.addWidget(self.log_panel)
        
        # Set initial splitter sizes (70% workflow, 30% log)
        self.main_splitter.setSizes([700, 300])
    
    def setup_header(self):
        """Set up the application header with banner."""
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # Try to load banner image
        banner_paths = [
            "pics/banner.png",
            "../pics/banner.png",
            "../../pics/banner.png",
            os.path.join(os.path.dirname(__file__), "../pics/banner.png"),
            "c:/Users/b162274/Desktop/ANPE_public/pics/banner.png"
        ]
        
        banner_found = False
        for path in banner_paths:
            if os.path.exists(path):
                banner_label = QLabel()
                pixmap = QPixmap(path)
                scaled_pixmap = pixmap.scaled(400, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                banner_label.setPixmap(scaled_pixmap)
                header_layout.addWidget(banner_label)
                banner_found = True
                break
        
        # Fallback if no banner found
        if not banner_found:
            title_label = QLabel("ANPE - Another Noun Phrase Extractor")
            title_label.setProperty("heading", True)
            header_layout.addWidget(title_label)
        
        header_layout.addStretch(1)  # Push banner to the left
        
        # Add version info
        version_label = QLabel(f"Version: {anpe_version}")
        header_layout.addWidget(version_label)
        
        self.main_layout.addWidget(header_container)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {SECONDARY_COLOR};")
        self.main_layout.addWidget(separator)
    
    def setup_step_indicators(self):
        """Set up the step indicators for the workflow."""
        # Container for step indicators
        step_container = QWidget()
        step_layout = QHBoxLayout(step_container)
        step_layout.setContentsMargins(0, 5, 0, 15)
        
        # Create step indicators
        self.step_indicators = []
        steps = [
            "1. Configuration",
            "2. Input Selection",
            "3. Results & Export"
        ]
        
        # Add indicators with connecting lines
        for i, step_title in enumerate(steps):
            # Add step indicator
            indicator = StepIndicator(step_title, i == 0)  # First step is active initially
            self.step_indicators.append(indicator)
            step_layout.addWidget(indicator)
            
            # Add connecting line between steps (except after the last step)
            if i < len(steps) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet(f"background-color: {SECONDARY_COLOR};")
                line.setFixedWidth(50)  # Width of the connecting line
                step_layout.addWidget(line)
        
        step_layout.addStretch(1)  # Push everything to the left
        self.main_layout.addWidget(step_container)
    
    def setup_navigation(self):
        """Set up navigation buttons for moving between steps."""
        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 10, 0, 0)
        
        # Add spacer to push buttons to the right
        nav_layout.addStretch(1)
        
        # Back button
        self.back_btn = QPushButton("← Back")
        self.back_btn.setToolTip("Go back to the previous step")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)  # Disabled initially (at first step)
        nav_layout.addWidget(self.back_btn)
        
        # Next/Process button
        self.next_btn = QPushButton("Next →")
        self.next_btn.setToolTip("Proceed to the next step")
        self.next_btn.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_btn)
        
        self.workflow_layout.addWidget(nav_container)
    
    def create_config_page(self):
        """Create the configuration page (Step 1)."""
        config_page = QWidget()
        config_layout = QVBoxLayout(config_page)
        
        # Page title
        title_label = QLabel("Step 1: Configure Extraction Settings")
        title_label.setProperty("heading", True)
        config_layout.addWidget(title_label)
        
        # Description
        description = QLabel("Configure how noun phrases will be extracted and filtered.")
        description.setWordWrap(True)
        config_layout.addWidget(description)
        
        # Filtering options group
        filter_group = QGroupBox("Filtering Options")
        filter_layout = QFormLayout(filter_group)
        
        # Minimum length
        min_length_layout = QHBoxLayout()
        self.min_length_cb = QCheckBox("Apply minimum length:")
        min_length_layout.addWidget(self.min_length_cb)
        self.min_length = QSpinBox()
        self.min_length.setMinimum(1)
        self.min_length.setMaximum(100)
        self.min_length.setValue(2)
        self.min_length.setEnabled(False)
        self.min_length_cb.toggled.connect(lambda state: self.min_length.setEnabled(state))
        min_length_layout.addWidget(self.min_length)
        min_length_layout.addStretch(1)
        filter_layout.addRow(min_length_layout)
        
        # Maximum length
        max_length_layout = QHBoxLayout()
        self.max_length_cb = QCheckBox("Apply maximum length:")
        max_length_layout.addWidget(self.max_length_cb)
        self.max_length = QSpinBox()
        self.max_length.setMinimum(1)
        self.max_length.setMaximum(100)
        self.max_length.setValue(10)
        self.max_length.setEnabled(False)
        self.max_length_cb.toggled.connect(lambda state: self.max_length.setEnabled(state))
        max_length_layout.addWidget(self.max_length)
        max_length_layout.addStretch(1)
        filter_layout.addRow(max_length_layout)
        
        # Accept pronouns
        self.accept_pronouns = QCheckBox("Accept Pronouns")
        self.accept_pronouns.setChecked(True)
        self.accept_pronouns.setToolTip("Include single-word pronouns as valid noun phrases")
        filter_layout.addRow(self.accept_pronouns)
        
        # Treat newlines as sentence boundaries
        self.newline_breaks = QCheckBox("Treat Newlines as Sentence Boundaries")
        self.newline_breaks.setChecked(True)
        self.newline_breaks.setToolTip("Consider each new line as a potential sentence boundary")
        filter_layout.addRow(self.newline_breaks)
        
        config_layout.addWidget(filter_group)
        
        # Structure filter widget
        self.structure_filter = StructureFilterWidget()
        config_layout.addWidget(self.structure_filter)
        
        # Metadata options
        metadata_group = QGroupBox("Output Options")
        metadata_layout = QVBoxLayout(metadata_group)
        
        self.include_metadata = QCheckBox("Include Metadata (length and structure analysis)")
        self.include_metadata.setChecked(True)
        metadata_layout.addWidget(self.include_metadata)
        
        self.include_nested = QCheckBox("Include Nested Noun Phrases")
        metadata_layout.addWidget(self.include_nested)
        
        config_layout.addWidget(metadata_group)
        
        # Logging options
        log_group = QGroupBox("Logging Options")
        log_layout = QFormLayout(log_group)
        
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentText("INFO")
        log_layout.addRow("Log Level:", self.log_level)
        
        log_dir_layout = QHBoxLayout()
        self.log_dir = QLineEdit()
        log_dir_layout.addWidget(self.log_dir)
        self.browse_log_dir_btn = QPushButton("Browse...")
        self.browse_log_dir_btn.clicked.connect(self.browse_log_directory)
        log_dir_layout.addWidget(self.browse_log_dir_btn)
        log_layout.addRow("Log Directory (optional):", log_dir_layout)
        
        config_layout.addWidget(log_group)
        
        # Add spacer at the bottom
        config_layout.addStretch(1)
        
        return config_page
    
    def create_input_page(self):
        """Create the input page (Step 2)."""
        input_page = QWidget()
        input_layout = QVBoxLayout(input_page)
        
        # Page title
        title_label = QLabel("Step 2: Select Input")
        title_label.setProperty("heading", True)
        input_layout.addWidget(title_label)
        
        # Description
        description = QLabel("Select text to process either by direct input or file selection.")
        description.setWordWrap(True)
        input_layout.addWidget(description)
        
        # Input options
        input_options = QGroupBox("Input Method")
        input_options_layout = QVBoxLayout(input_options)
        
        # Text input option
        self.text_radio = QCheckBox("Text Input")
        self.text_radio.setChecked(True)
        self.text_radio.toggled.connect(self.toggle_input_method)
        input_options_layout.addWidget(self.text_radio)
        
        # Text input area
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Enter text to extract noun phrases from...")
        self.text_input.setMinimumHeight(150)
        input_options_layout.addWidget(self.text_input)
        
        # File input option
        self.file_radio = QCheckBox("File Input")
        self.file_radio.toggled.connect(self.toggle_input_method)
        input_options_layout.addWidget(self.file_radio)
        
        # File list widget (initially disabled)
        self.file_list_widget = FileListWidget()
        self.file_list_widget.setEnabled(False)
        input_options_layout.addWidget(self.file_list_widget)
        
        input_layout.addWidget(input_options)
        
        # Output format selection
        format_group = QGroupBox("Output Format")
        format_layout = QHBoxLayout(format_group)
        
        format_layout.addWidget(QLabel("Select format:"))
        self.output_format = QComboBox()
        self.output_format.addItems(["txt", "csv", "json"])
        self.output_format.setToolTip("Format for exporting extraction results")
        format_layout.addWidget(self.output_format)
        format_layout.addStretch(1)
        
        input_layout.addWidget(format_group)
        
        # Add spacer at the bottom
        input_layout.addStretch(1)
        
        return input_page
    
    def create_output_page(self):
        """Create the output page (Step 3)."""
        output_page = QWidget()
        output_layout = QVBoxLayout(output_page)
        
        # Page title
        title_label = QLabel("Step 3: Results and Export")
        title_label.setProperty("heading", True)
        output_layout.addWidget(title_label)
        
        # Results display
        results_group = QGroupBox("Extraction Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)
        
        output_layout.addWidget(results_group)
        
        # Export options
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout(export_group)
        
        # Export directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Export Directory:"))
        self.export_dir = QLineEdit()
        dir_layout.addWidget(self.export_dir)
        self.browse_export_dir_btn = QPushButton("Browse...")
        self.browse_export_dir_btn.clicked.connect(self.browse_export_directory)
        dir_layout.addWidget(self.browse_export_dir_btn)
        export_layout.addLayout(dir_layout)
        
        # Export button
        export_btn_layout = QHBoxLayout()
        export_btn_layout.addStretch(1)
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        export_btn_layout.addWidget(self.export_btn)
        export_layout.addLayout(export_btn_layout)
        
        output_layout.addWidget(export_group)
        
        # Process new input button
        new_input_layout = QHBoxLayout()
        new_input_layout.addStretch(1)
        self.new_input_btn = QPushButton("Process New Input")
        self.new_input_btn.setToolTip("Start over with new input")
        self.new_input_btn.clicked.connect(self.reset_workflow)
        new_input_layout.addWidget(self.new_input_btn)
        output_layout.addLayout(new_input_layout)
        
        # Add spacer at the bottom
        output_layout.addStretch(1)
        
        return output_page
    
    def create_log_panel(self):
        """Create the log panel widget."""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        # Title
        title_label = QLabel("Log Output")
        title_label.setProperty("subheading", True)
        log_layout.addWidget(title_label)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text, 1)  # Stretch
        
        # Set up log handler
        self.log_handler = QtLogHandler(self.log_text)
        
        # Clear log button
        clear_layout = QHBoxLayout()
        clear_layout.addStretch(1)
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        clear_layout.addWidget(self.clear_log_btn)
        log_layout.addLayout(clear_layout)
        
        return log_widget
    
    def go_back(self):
        """Navigate to the previous step."""
        current_index = self.steps_stack.currentIndex()
        if current_index > 0:
            self.steps_stack.setCurrentIndex(current_index - 1)
            self.update_navigation()
            self.update_step_indicators()
    
    def go_next(self):
        """Navigate to the next step or process based on current step."""
        current_index = self.steps_stack.currentIndex()
        
        if current_index == 0:  # Configuration step
            # Apply configuration
            self.apply_configuration()
            
            # Move to next step
            self.steps_stack.setCurrentIndex(1)
            self.update_navigation()
            self.update_step_indicators()
            
        elif current_index == 1:  # Input step
            # Process the input
            self.process_input()
            
        # Note: If on the last step, button is handled separately
    
    def update_navigation(self):
        """Update navigation buttons based on current step."""
        current_index = self.steps_stack.currentIndex()
        
        # Back button
        self.back_btn.setEnabled(current_index > 0)
        
        # Next button
        if current_index == 2:  # Last step
            self.next_btn.setText("Process New Input")
            self.next_btn.clicked.disconnect()
            self.next_btn.clicked.connect(self.reset_workflow)
        else:
            self.next_btn.setText("Next →")
            
            # Disconnect any existing connections
            try:
                self.next_btn.clicked.disconnect()
            except:
                pass
                
            self.next_btn.clicked.connect(self.go_next)
    
    def update_step_indicators(self):
        """Update the step indicators based on current step."""
        current_index = self.steps_stack.currentIndex()
        
        for i, indicator in enumerate(self.step_indicators):
            indicator.animate_activation(i == current_index)
    
    def toggle_input_method(self, checked):
        """Toggle between text input and file input."""
        if not checked:
            return
            
        sender = self.sender()
        
        if sender == self.text_radio:
            self.file_radio.setChecked(False)
            self.text_input.setEnabled(True)
            self.file_list_widget.setEnabled(False)
        elif sender == self.file_radio:
            self.text_radio.setChecked(False)
            self.text_input.setEnabled(False)
            self.file_list_widget.setEnabled(True)
    
    def browse_log_directory(self):
        """Open directory dialog to select a log directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Log Directory"
        )
        if dir_path:
            self.log_dir.setText(dir_path)
    
    def browse_export_directory(self):
        """Open directory dialog to select an export directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Export Directory"
        )
        if dir_path:
            self.export_dir.setText(dir_path)
    
    def apply_configuration(self):
        """Apply configuration settings to the extractor."""
        try:
            config = {}
            
            # Set log level
            config["log_level"] = self.log_level.currentText()
            
            # Set log directory if provided
            if self.log_dir.text():
                config["log_dir"] = self.log_dir.text()
            
            # Set filtering options
            if self.min_length_cb.isChecked():
                config["min_length"] = self.min_length.value()
            
            if self.max_length_cb.isChecked():
                config["max_length"] = self.max_length.value()
            
            config["accept_pronouns"] = self.accept_pronouns.isChecked()
            config["newline_breaks"] = self.newline_breaks.isChecked()
            
            # Set structure filters
            structures = self.structure_filter.get_selected_structures()
            if structures:
                config["structure_filters"] = structures
            
            # Create the extractor with the new configuration
            self.extractor = ANPEExtractor(config)
            
            # Update status bar
            self.status_bar.showMessage("Configuration applied successfully", 3000)
            
            # Log
            self.log_text.append("Configuration applied: " + str(config))
            
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Error applying configuration: {str(e)}")
            self.log_text.append(f"Error applying configuration: {str(e)}")
    
    def process_input(self):
        """Process the selected input source."""
        try:
            if self.text_radio.isChecked():
                # Get text input
                text = self.text_input.toPlainText()
                if not text:
                    QMessageBox.warning(self, "Input Error", "Please enter some text to process.")
                    return
                
                # Process single text
                self.process_single_text(text)
                
            elif self.file_radio.isChecked():
                # Get file paths
                file_paths = self.file_list_widget.get_files()
                if not file_paths:
                    QMessageBox.warning(self, "Input Error", "Please select at least one file to process.")
                    return
                
                # Process files
                if len(file_paths) == 1:
                    # Single file
                    with open(file_paths[0], 'r', encoding='utf-8') as f:
                        text = f.read()
                    self.process_single_text(text)
                else:
                    # Multiple files
                    self.process_multiple_files(file_paths)
            
            # Move to output step
            self.steps_stack.setCurrentIndex(2)
            self.update_navigation()
            self.update_step_indicators()
            
        except Exception as e:
            QMessageBox.warning(self, "Processing Error", f"Error processing input: {str(e)}")
            self.log_text.append(f"Error processing input: {str(e)}")
    
    def process_single_text(self, text):
        """Process a single text input."""
        # Show progress
        self.progress_bar.setMaximum(0)  # Indeterminate progress
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Extracting noun phrases...")
        
        # Get extraction parameters
        metadata = self.include_metadata.isChecked()
        include_nested = self.include_nested.isChecked()
        
        # Create worker for background processing
        worker = ExtractionWorker(
            self.extractor, 
            text, 
            metadata, 
            include_nested
        )
        
        worker.signals.result.connect(self.handle_extraction_result)
        worker.signals.error.connect(self.handle_extraction_error)
        worker.signals.finished.connect(self.handle_extraction_finished)
        
        # Execute
        self.thread_pool.start(worker)
    
    def process_multiple_files(self, file_paths):
        """Process multiple files."""
        # Show progress
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Processing files...")
        
        # Create a dictionary to store results
        self.multi_file_results = {}
        
        # Get extraction parameters
        metadata = self.include_metadata.isChecked()
        include_nested = self.include_nested.isChecked()
        
        # Process files one by one
        total_files = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            try:
                # Update progress
                self.progress_bar.setValue(int((i / total_files) * 100))
                self.status_bar.showMessage(f"Processing file {i+1} of {total_files}: {os.path.basename(file_path)}")
                self.log_text.append(f"Processing file: {file_path}")
                
                # Read file
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # Extract noun phrases
                result = self.extractor.extract(
                    text=text,
                    metadata=metadata,
                    include_nested=include_nested
                )
                
                # Store result
                self.multi_file_results[os.path.basename(file_path)] = result
                
                self.log_text.append(f"Completed processing file: {file_path}")
                
            except Exception as e:
                self.log_text.append(f"Error processing file {file_path}: {str(e)}")
        
        # Combine all results for display
        self.handle_multi_file_results()
    
    def handle_extraction_result(self, result):
        """Handle the result of an extraction operation."""
        # Store result for export
        self.current_results = result
        
        # Display results
        self.display_results(result)
    
    def handle_multi_file_results(self):
        """Handle results from multiple files."""
        # Store results for export
        self.current_results = self.multi_file_results
        
        # Display summary
        self.results_text.clear()
        self.results_text.append("Batch Processing Results")
        self.results_text.append("=======================")
        self.results_text.append(f"Total files processed: {len(self.multi_file_results)}")
        self.results_text.append("")
        
        # Show summary of each file
        for filename, result in self.multi_file_results.items():
            np_count = len(result.get('results', []))
            self.results_text.append(f"File: {filename}")
            self.results_text.append(f"Noun phrases found: {np_count}")
            self.results_text.append("")
        
        # Show sample results from first file
        if self.multi_file_results:
            first_file = next(iter(self.multi_file_results))
            first_result = self.multi_file_results[first_file]
            
            self.results_text.append(f"Sample results from {first_file}:")
            self.results_text.append("----------------------------------")
            self.format_results_for_display(first_result)
        
        # Finish processing
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Batch processing completed", 3000)
    
    def handle_extraction_error(self, error):
        """Handle an error during extraction."""
        QMessageBox.warning(self, "Extraction Error", f"Error during extraction: {str(error)}")
        self.log_text.append(f"Error during extraction: {str(error)}")
        
        # Reset UI
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Extraction failed", 3000)
    
    def handle_extraction_finished(self):
        """Handle completion of extraction."""
        # Reset UI
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Extraction completed", 3000)
    
    def display_results(self, data):
        """Display extraction results in the results text area."""
        self.results_text.clear()
        self.format_results_for_display(data)
    
    def format_results_for_display(self, data):
        """Format extraction results for display."""
        self.results_text.append("ANPE Noun Phrase Extraction Results")
        self.results_text.append("==================================")
        self.results_text.append(f"Timestamp: {data['metadata'].get('timestamp')}")
        self.results_text.append(f"Includes Nested NPs: {data['metadata'].get('includes_nested')}")
        self.results_text.append(f"Includes Metadata: {data['metadata'].get('includes_metadata')}")
        self.results_text.append("")
        
        # Display noun phrases
        self.format_np_for_display(data["results"])
    
    def format_np_for_display(self, np_items, level=0):
        """Recursively format noun phrases for display."""
        for np_item in np_items:
            bullet = "•" if level == 0 else "◦"
            indent = "  " * level
            
            self.results_text.append(f"{indent}{bullet} [{np_item['id']}] {np_item['noun_phrase']}")
            
            if "metadata" in np_item:
                metadata = np_item["metadata"]
                if "length" in metadata:
                    self.results_text.append(f"{indent}  Length: {metadata['length']}")
                if "structures" in metadata:
                    structures_str = ", ".join(metadata['structures']) if isinstance(metadata['structures'], list) else metadata['structures']
                    self.results_text.append(f"{indent}  Structures: [{structures_str}]")
            
            if "children" in np_item and np_item["children"]:
                self.format_np_for_display(np_item["children"], level + 1)
    
    def export_results(self):
        """Export results to a file."""
        try:
            # Check if results exist
            if not hasattr(self, 'current_results'):
                QMessageBox.warning(self, "Export Error", "No extraction results to export.")
                return
            
            # Get export directory
            export_dir = self.export_dir.text()
            if not export_dir:
                QMessageBox.warning(self, "Export Error", "Please select an export directory.")
                return
            
            # Get export format
            export_format = self.output_format.currentText()
            
            # Export results
            from anpe.utils.export import ANPEExporter
            exporter = ANPEExporter()
            
            # Determine file type to export
            if isinstance(self.current_results, dict) and not 'results' in self.current_results:
                # Multi-file results
                for filename, result in self.current_results.items():
                    # Use the filename (without extension) as the output filename
                    base_name = os.path.splitext(filename)[0]
                    file_export_path = os.path.join(export_dir, f"{base_name}.{export_format}")
                    
                    # Export to file
                    exporter.export(result, format=export_format, export_path=file_export_path)
                    
                    self.log_text.append(f"Exported results for {filename} to {file_export_path}")
                
                QMessageBox.information(
                    self, 
                    "Export Successful", 
                    f"Results for {len(self.current_results)} files exported to {export_dir}"
                )
            else:
                # Single file/text results
                exporter.export(self.current_results, format=export_format, export_dir=export_dir)
                
                self.log_text.append(f"Results exported to {export_dir} in {export_format} format")
                
                QMessageBox.information(
                    self, 
                    "Export Successful", 
                    f"Results exported successfully to {export_dir}"
                )
            
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Error exporting results: {str(e)}")
            self.log_text.append(f"Error exporting results: {str(e)}")
    
    def reset_workflow(self):
        """Reset the workflow to start over with new input."""
        # Clear results
        if hasattr(self, 'current_results'):
            delattr(self, 'current_results')
        
        if hasattr(self, 'multi_file_results'):
            delattr(self, 'multi_file_results')
        
        # Clear text areas
        self.text_input.clear()
        self.results_text.clear()
        
        # Clear file list
        self.file_list_widget.clear_files()
        
        # Reset to first step
        self.steps_stack.setCurrentIndex(0)
        self.update_navigation()
        self.update_step_indicators()
        
        # Log
        self.log_text.append("Workflow reset to start new extraction")
        
        # Update status bar
        self.status_bar.showMessage("Ready for new extraction", 3000)
    
    def clear_log(self):
        """Clear the log text area."""
        self.log_text.clear() 