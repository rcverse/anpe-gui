import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import Qt

# Make sure the anpe_gui package is importable
try:
    from anpe_gui.widgets.activity_indicator import PulsingActivityIndicator
except ImportError:
    print("Error: Could not import PulsingActivityIndicator.")
    print("Ensure you are running this script from the workspace root directory")
    print("or that the 'anpe_gui' package is in your PYTHONPATH.")
    sys.exit(1)

class DebugWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Activity Indicator State Debug")
        self.setGeometry(300, 300, 250, 200) # Window position and size

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create the indicator
        self.indicator = PulsingActivityIndicator()
        # You can uncomment this to test with a larger size if needed
        # self.indicator.setFixedSize(60, 60)
        main_layout.addWidget(self.indicator, 0, Qt.AlignmentFlag.AlignCenter)

        # --- Control Buttons --- 
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.start_button = QPushButton("Start Active")
        self.start_button.setToolTip("Switch to blue ripple animation")
        self.start_button.clicked.connect(self.indicator.start)

        self.idle_button = QPushButton("Idle")
        self.idle_button.setToolTip("Switch to green idle glow animation")
        self.idle_button.clicked.connect(self.indicator.idle)

        self.warn_button = QPushButton("Warn")
        self.warn_button.setToolTip("Switch to yellow warning animation")
        self.warn_button.clicked.connect(self.indicator.warn)

        self.error_button = QPushButton("Error")
        self.error_button.setToolTip("Switch to red error animation")
        self.error_button.clicked.connect(self.indicator.error)

        self.checking_button = QPushButton("Checking")
        self.checking_button.setToolTip("Switch to yellow checking pulse")
        self.checking_button.clicked.connect(self.indicator.checking)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.idle_button)
        button_layout.addWidget(self.warn_button)
        button_layout.addWidget(self.error_button)
        button_layout.addWidget(self.checking_button)
        
        main_layout.addLayout(button_layout)
        self.setCentralWidget(container)

        # --- Set Initial State --- 
        # Start in the idle state
        self.indicator.idle()

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Optional: Apply theme if needed (though indicator pulls colors internally)
    # try:
    #     from anpe_gui.theme import apply_theme
    #     apply_theme(app)
    # except ImportError:
    #     print("Warning: Could not import and apply theme.")

    window = DebugWindow()
    window.show()
    sys.exit(app.exec()) 