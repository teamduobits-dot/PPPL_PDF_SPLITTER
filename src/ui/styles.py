APP_STYLE = """
QWidget {
    background-color: #0b1220;
    color: #e5e7eb;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QLabel {
    color: #e5e7eb;
}

QGroupBox {
    border: 1px solid #ffffff;
    border-radius: 10px;
    margin-top: 10px;
    padding: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #ffffff;
    font-weight: 700;
}

QPushButton {
    background-color: #1d4ed8;
    color: white;
    border: 1px solid rgba(255,255,255,0.15);
    padding: 10px 14px;
    border-radius: 10px;
    font-weight: 700;
}

QPushButton:hover {
    background-color: #2563eb;
}

QPushButton:disabled {
    background-color: #334155;
    color: #94a3b8;
    border: 1px solid rgba(255,255,255,0.08);
}

QLineEdit, QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 10px;
    color: #e5e7eb;
}

QComboBox QAbstractItemView {
    background-color: #0f172a;
    border: 1px solid #334155;
    selection-background-color: #1d4ed8;
}

QCheckBox {
    spacing: 8px;
    font-weight: 700;
}

QTextEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 10px;
    color: #e5e7eb;
}

QProgressBar {
    background-color: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
    text-align: center;
    height: 22px;
}

QProgressBar::chunk {
    background-color: #22c55e;
    border-radius: 10px;
}
"""