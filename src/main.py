import sys
from PySide6.QtWidgets import QApplication
from src.ui.app_window import AppWindow

def main():
    app = QApplication(sys.argv)
    w = AppWindow()
    w.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
