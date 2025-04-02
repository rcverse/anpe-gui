"""
Structure filter widget for selecting NP structures to include.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QCheckBox, 
    QLabel, QFrame, QScrollArea
)
from PyQt6.QtCore import pyqtSignal, Qt


class StructureFilterWidget(QWidget):
    """
    Widget for selecting which NP structure types to include in extraction.
    Displays a grid of checkboxes with explanations for each structure type.
    """
    
    # Signal emitted when filter selection changes
    filterChanged = pyqtSignal(list)  # List of selected structure names
    
    def __init__(self, parent=None):
        """
        Initialize the structure filter widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Define structure types and their descriptions
        self.structures = [
            ("determiner", "Determiner", "NPs with determiners (the, a, an, this, that, these, those)"),
            ("adjectival_modifier", "Adjectival Modifier", "NPs with adjective modifiers"),
            ("prepositional_modifier", "Prepositional Modifier", "NPs with prepositional phrase modifiers"),
            ("compound", "Compound", "Compound nouns forming a single conceptual unit"),
            ("possessive", "Possessive", "Possessive constructions with markers or pronouns"),
            ("quantified", "Quantified", "Quantified NPs with numbers or quantity words"),
            ("coordinated", "Coordinated", "Coordinated elements joined by conjunctions"),
            ("appositive", "Appositive", "One NP renames or explains another"),
            ("relative_clause", "Relative Clause", "Clause that modifies a noun"),
            ("nonfinite_complement", "Nonfinite Complement", "Non-finite clause as a complement to a noun"),
            ("named_entity", "Named Entity", "Proper nouns and named entities"),
            ("standalone_noun", "Standalone Noun", "Single nouns without modifiers")
        ]
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel("Structure Filters")
        title_label.setProperty("subheading", True)
        main_layout.addWidget(title_label)
        
        # Help text
        help_label = QLabel("Select specific structure types to include (if none selected, all types are included)")
        help_label.setWordWrap(True)
        main_layout.addWidget(help_label)
        
        # Create scroll area for the grid
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Content widget for the scroll area
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        # Grid layout for checkboxes
        grid_layout = QGridLayout(content_widget)
        grid_layout.setColumnStretch(0, 0)  # Checkbox column
        grid_layout.setColumnStretch(1, 1)  # Name column
        grid_layout.setColumnStretch(2, 2)  # Description column
        
        # Add header
        grid_layout.addWidget(QLabel("<b>Include</b>"), 0, 0, Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(QLabel("<b>Structure Type</b>"), 0, 1)
        grid_layout.addWidget(QLabel("<b>Description</b>"), 0, 2)
        
        # Create checkboxes for each structure type
        self.checkboxes = {}
        
        for i, (value, name, description) in enumerate(self.structures, 1):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(self.update_filter)
            self.checkboxes[value] = checkbox
            grid_layout.addWidget(checkbox, i, 0, Qt.AlignmentFlag.AlignCenter)
            
            # Structure name
            name_label = QLabel(name)
            name_label.setToolTip(description)
            grid_layout.addWidget(name_label, i, 1)
            
            # Description
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            grid_layout.addWidget(desc_label, i, 2)
        
        # Add the scroll area to the main layout
        main_layout.addWidget(scroll_area)
    
    def update_filter(self):
        """Update filter based on checkbox states and emit signal."""
        selected = []
        
        for value, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected.append(value)
        
        self.filterChanged.emit(selected)
    
    def get_selected_structures(self):
        """
        Get the list of selected structure types.
        
        Returns:
            List of structure type identifiers
        """
        selected = []
        
        for value, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected.append(value)
        
        return selected
    
    def select_all(self):
        """Select all structure types."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
    
    def unselect_all(self):
        """Unselect all structure types."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
            
    def set_selected_structures(self, structures):
        """
        Set the selected structure types.
        
        Args:
            structures: List of structure type identifiers to select
        """
        # First unselect all
        self.unselect_all()
        
        # Then select the specified ones
        for value in structures:
            if value in self.checkboxes:
                self.checkboxes[value].setChecked(True) 