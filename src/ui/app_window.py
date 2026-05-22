from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Qt

from src.ui.styles import APP_STYLE
from src.ui.main_window import MainWindow
from src.ui.signed_rename_window import SignedRenameWindow


class AppWindow(QWidget):
    """
    Container with TOP tabs.
    Important: keep dark theme so your original MainWindow UI doesn't look "messed".
    """
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PPPL PDF Splitter - Multi Mode")
        self.setMinimumSize(1050, 780)

        # Apply the same base stylesheet to the container too
        self.setStyleSheet(APP_STYLE)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)
        tabs.setMovable(False)

        # Tabs styling: match your dark app background
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0b1220;
            }
            QTabBar::tab {
                background-color: #111827;
                color: #e5e7eb;
                padding: 10px 16px;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border: 1px solid rgba(255,255,255,0.10);
            }
            QTabBar::tab:selected {
                background-color: #1d4ed8;
                color: white;
                border: 1px solid rgba(255,255,255,0.18);
            }
        """)

        splitter_tab = MainWindow()
        signed_tab = SignedRenameWindow()

        tabs.addTab(splitter_tab, "PDF Splitter")
        tabs.addTab(signed_tab, "Signed Rename ZIP")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # IMPORTANT: remove extra white padding
        layout.setSpacing(0)
        layout.addWidget(tabs)
