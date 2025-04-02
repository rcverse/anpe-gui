"""
Theme and styling for the ANPE GUI application.
"""
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt

# Color scheme constants
PRIMARY_COLOR = "#1a5276"      # Dark blue
SECONDARY_COLOR = "#2980b9"    # Medium blue
ACCENT_COLOR = "#3498db"       # Light blue
BACKGROUND_COLOR = "#f5f9fc"   # Very light blue
TEXT_COLOR = "#2c3e50"         # Dark slate
SUCCESS_COLOR = "#27ae60"      # Green
WARNING_COLOR = "#f39c12"      # Orange
ERROR_COLOR = "#c0392b"        # Red

# Application stylesheet
STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {BACKGROUND_COLOR};
}}

QTabWidget::pane {{
    border: 1px solid #d0d0d0;
    background-color: white;
}}

QTabBar::tab {{
    background-color: #e0e0e0;
    border: 1px solid #c0c0c0;
    border-bottom: none;
    padding: 8px 15px;
    min-width: 100px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {ACCENT_COLOR};
    color: white;
}}

QTabBar::tab:hover:!selected {{
    background-color: #e8e8e8;
}}

QPushButton {{
    background-color: {SECONDARY_COLOR};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 25px;
}}

QPushButton:hover {{
    background-color: {ACCENT_COLOR};
}}

QPushButton:pressed {{
    background-color: {PRIMARY_COLOR};
}}

QPushButton:disabled {{
    background-color: #cccccc;
    color: #666666;
}}

QLineEdit, QTextEdit, QSpinBox, QComboBox {{
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 4px;
    background-color: white;
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT_COLOR};
}}

QGroupBox {{
    border: 1px solid #d0d0d0;
    border-radius: 5px;
    margin-top: 20px;
    font-weight: bold;
    background-color: white;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    background-color: white;
    color: {PRIMARY_COLOR};
}}

QLabel {{
    color: {TEXT_COLOR};
}}

QLabel[heading="true"] {{
    font-size: 14pt;
    font-weight: bold;
    color: {PRIMARY_COLOR};
    margin-bottom: 10px;
}}

QLabel[subheading="true"] {{
    font-size: 12pt;
    color: {SECONDARY_COLOR};
    margin-top: 5px;
    margin-bottom: 5px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT_COLOR};
    border: 1px solid {ACCENT_COLOR};
    image: url(:/images/checkmark.png);  /* Would need to add this image */
}}

QProgressBar {{
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    background-color: white;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ACCENT_COLOR};
    width: 10px;
}}

/* Special styling for step indicators */
QFrame#StepIndicator {{
    background-color: #e0e0e0;
    border-radius: 15px;
    padding: 10px;
}}

QFrame#StepIndicator[active="true"] {{
    background-color: {ACCENT_COLOR};
}}

QFrame#StepIndicator QLabel {{
    color: {TEXT_COLOR};
}}

QFrame#StepIndicator[active="true"] QLabel {{
    color: white;
    font-weight: bold;
}}

/* Splitter styling */
QSplitter::handle {{
    background-color: #d0d0d0;
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* File list styling */
QListView {{
    border: 1px solid #c0c0c0;
    background-color: white;
}}

QListView::item {{
    padding: 4px;
}}

QListView::item:selected {{
    background-color: {ACCENT_COLOR};
    color: white;
}}
"""

def apply_theme(app):
    """
    Apply the ANPE GUI theme to the application.
    
    Args:
        app: QApplication instance
    """
    # Set the application style sheet
    app.setStyleSheet(STYLESHEET)
    
    # Set default palette colors
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND_COLOR))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_COLOR))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f5f5"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_COLOR))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_COLOR))
    palette.setColor(QPalette.ColorRole.Button, QColor(SECONDARY_COLOR))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_COLOR))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette) 