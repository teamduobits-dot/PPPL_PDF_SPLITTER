import os
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QCheckBox,
    QTextEdit, QProgressBar, QComboBox, QMessageBox, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QLineEdit
)

from src.ui.styles import APP_STYLE
from src.core.worker import PdfProcessingWorker
from src.core.settings_manager import load_settings, save_settings


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PPPL PDF Splitter")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(760)

        self._settings: Dict[str, Any] = load_settings()
        self.selected_pdf_path: str = ""
        self.selected_output_path: str = self._settings.get("defaultOutputPath", "") or ""
        self.detected_invoice_ids: List[str] = []
        self.analysis_done: bool = False

        self._processing_thread: Optional[QThread] = None
        self._worker: Optional[PdfProcessingWorker] = None

        self._build_ui()
        self._apply_style()
        self._apply_settings_to_ui()
        self._set_idle_state()

    def _apply_style(self):
        self.setStyleSheet(APP_STYLE)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        logo_row = QVBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)
        self.lbl_logo = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "PPPL_LOGO.png")
        pix = QPixmap(logo_path)
        if not pix.isNull():
            self.lbl_logo.setPixmap(pix.scaledToHeight(64, Qt.SmoothTransformation))
        self.lbl_logo.setAlignment(Qt.AlignCenter)

        header = QLabel("PPPL PDF Splitter")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)

        license_label = QLabel("Licensed by: Praditi Pressparts Pvt. Ltd.")
        license_label.setAlignment(Qt.AlignCenter)

        logo_row.addWidget(self.lbl_logo)
        logo_row.addWidget(header)
        logo_row.addWidget(license_label)
        main_layout.addLayout(logo_row)

        row = QHBoxLayout()
        main_layout.addLayout(row)
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        row.addLayout(left_col, 1)
        row.addLayout(right_col, 1)

        upload_box = QGroupBox("PDF Upload Section")
        upload_layout = QVBoxLayout(upload_box)
        self.btn_upload = QPushButton("Upload Merged PDF")
        self.lbl_pdf_path = QLabel("No file selected")
        self.lbl_pdf_path.setWordWrap(True)
        self.lbl_estimate = QLabel("Invoice estimate will appear here after analysis.")
        upload_layout.addWidget(self.btn_upload)
        upload_layout.addWidget(self.lbl_pdf_path)
        upload_layout.addWidget(self.lbl_estimate)
        left_col.addWidget(upload_box)

        range_box = QGroupBox("Invoice Range Section")
        range_layout = QFormLayout(range_box)
        self.cmb_from = QComboBox()
        self.cmb_from.setEditable(True)
        self.cmb_to = QComboBox()
        self.cmb_to.setEditable(True)
        range_layout.addRow("FROM:", self.cmb_from)
        range_layout.addRow("TO:", self.cmb_to)
        left_col.addWidget(range_box)

        output_box = QGroupBox("Output Section")
        output_layout = QVBoxLayout(output_box)
        out_row = QHBoxLayout()
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setReadOnly(True)
        self.btn_browse_output = QPushButton("Browse Folder")
        out_row.addWidget(self.txt_output_path, 1)
        out_row.addWidget(self.btn_browse_output)
        output_layout.addLayout(out_row)
        right_col.addWidget(output_box)

        options_box = QGroupBox("Processing Options")
        options_layout = QVBoxLayout(options_box)
        self.chk_zip_only = QCheckBox("Generate ASN ZIP Files Only")
        self.chk_individual_pdfs = QCheckBox("Generate Individual PDFs")
        self.chk_open_after = QCheckBox("Open Folder After Processing")
        options_layout.addWidget(self.chk_zip_only)
        options_layout.addWidget(self.chk_individual_pdfs)
        options_layout.addWidget(self.chk_open_after)
        right_col.addWidget(options_box)

        logs_box = QGroupBox("Processing Logs")
        logs_layout = QVBoxLayout(logs_box)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.progress = QProgressBar()
        logs_layout.addWidget(self.progress)
        logs_layout.addWidget(self.txt_logs)
        main_layout.addWidget(logs_box)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Processing")
        self.btn_clear = QPushButton("Clear")
        self.btn_open_output = QPushButton("Open Output Folder")
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_open_output)
        main_layout.addLayout(btn_row)

        footer = QLabel("Developed by Duobits Software Solutions | Version 1.0")
        footer.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(footer)

        self.btn_upload.clicked.connect(self.on_upload_pdf)
        self.btn_browse_output.clicked.connect(self.on_browse_output_folder)
        self.btn_start.clicked.connect(self.on_start_processing)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_open_output.clicked.connect(self.on_open_output_folder)

        self.chk_open_after.stateChanged.connect(self._on_open_after_changed)
        self.chk_zip_only.stateChanged.connect(self._on_output_options_changed)
        self.chk_individual_pdfs.stateChanged.connect(self._on_output_options_changed)

    def _apply_settings_to_ui(self):
        self.txt_output_path.setText(self.selected_output_path)
        self.btn_open_output.setEnabled(bool(self.selected_output_path))
        self.chk_open_after.setChecked(bool(self._settings.get("openFolderAfterProcessing", True)))
        self.chk_zip_only.setChecked(bool(self._settings.get("lastZipOnly", False)))
        self.chk_individual_pdfs.setChecked(bool(self._settings.get("lastIndividualPdfs", False)))

    def _on_open_after_changed(self, _state):
        self._settings["openFolderAfterProcessing"] = bool(self.chk_open_after.isChecked())
        save_settings(self._settings)

    def _on_output_options_changed(self, _state):
        self._settings["lastZipOnly"] = bool(self.chk_zip_only.isChecked())
        self._settings["lastIndividualPdfs"] = bool(self.chk_individual_pdfs.isChecked())
        save_settings(self._settings)

    def _save_default_output_path(self, folder_path: str):
        self._settings["defaultOutputPath"] = folder_path
        save_settings(self._settings)

    def _save_last_input_dir(self, input_dir: str):
        self._settings["lastInputDir"] = input_dir
        save_settings(self._settings)

    def _set_busy_state(self):
        self.btn_upload.setEnabled(False)
        self.btn_browse_output.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_open_output.setEnabled(False)
        self.chk_zip_only.setEnabled(False)
        self.chk_individual_pdfs.setEnabled(False)
        self.chk_open_after.setEnabled(False)
        self.cmb_from.setEnabled(False)
        self.cmb_to.setEnabled(False)

    def _set_idle_state(self):
        self.btn_upload.setEnabled(True)
        self.btn_browse_output.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_open_output.setEnabled(bool(self.selected_output_path))
        self.chk_zip_only.setEnabled(True)
        self.chk_individual_pdfs.setEnabled(True)
        self.chk_open_after.setEnabled(True)
        self.cmb_from.setEnabled(self.analysis_done)
        self.cmb_to.setEnabled(self.analysis_done)
        self.btn_start.setEnabled(self.analysis_done)

    def append_log(self, msg: str):
        self.txt_logs.append(msg)

    def on_upload_pdf(self):
        last_input_dir = self._settings.get("lastInputDir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select merged ERP invoice PDF", last_input_dir, "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        self._save_last_input_dir(os.path.dirname(file_path))
        self.selected_pdf_path = file_path
        self.lbl_pdf_path.setText(file_path)
        self.analysis_done = False
        self.detected_invoice_ids = []
        self.cmb_from.clear()
        self.cmb_to.clear()
        self.lbl_estimate.setText("Analyzing PDF... (Phase 3)")
        self.txt_logs.clear()
        self.progress.setValue(0)
        self._set_busy_state()

        self._worker = PdfProcessingWorker(
            mode="analyze",
            file_path=self.selected_pdf_path,
            output_path=self.selected_output_path,
            options={},
            from_invoice="",
            to_invoice=""
        )

        self._processing_thread = QThread(self)
        self._worker.moveToThread(self._processing_thread)
        self._processing_thread.started.connect(self._worker.run)

        self._worker.log.connect(self.append_log)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.analysis_complete.connect(self._on_analysis_complete)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)

        self._processing_thread.start()

    def _on_analysis_complete(self, payload: dict):
        invoice_ids = payload.get("invoice_ids", [])
        self.detected_invoice_ids = invoice_ids

        if not invoice_ids:
            self.lbl_estimate.setText("No invoice candidates found.")
            self._set_idle_state()
            return

        self.cmb_from.clear()
        self.cmb_to.clear()
        self.cmb_from.addItems(invoice_ids)
        self.cmb_to.addItems(invoice_ids)
        self.cmb_from.setCurrentText(invoice_ids[0])
        self.cmb_to.setCurrentText(invoice_ids[-1])

        page_count = payload.get("page_count", "?")
        self.lbl_estimate.setText(
            f"Detected invoices from {invoice_ids[0]} to {invoice_ids[-1]} (Pages: {page_count})"
        )
        self.analysis_done = True
        self.append_log(f"Phase 3 completed. Invoices: {invoice_ids}")
        self._set_idle_state()

    def on_start_processing(self):
        if not self.analysis_done:
            QMessageBox.warning(self, "Not Ready", "Please upload a PDF first.")
            return
        if not self.selected_output_path:
            QMessageBox.warning(self, "Missing Output", "Please select output folder.")
            return

        from_val = self.cmb_from.currentText().strip()
        to_val = self.cmb_to.currentText().strip()

        if not from_val or not to_val:
            QMessageBox.warning(self, "Invalid Range", "Please select FROM and TO values.")
            return

        options = {
            "zip_only": self.chk_zip_only.isChecked(),
            "individual_pdfs": self.chk_individual_pdfs.isChecked(),
            "open_after": self.chk_open_after.isChecked(),
        }

        self.txt_logs.clear()
        self.progress.setValue(0)
        self._set_busy_state()

        self._worker = PdfProcessingWorker(
            mode="split_range",
            file_path=self.selected_pdf_path,
            output_path=self.selected_output_path,
            options=options,
            from_invoice=from_val,
            to_invoice=to_val
        )

        self._processing_thread = QThread(self)
        self._worker.moveToThread(self._processing_thread)
        self._processing_thread.started.connect(self._worker.run)

        self._worker.log.connect(self.append_log)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.split_complete.connect(self._on_split_complete)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.request_duplicate.connect(self._on_duplicate_request)

        self._processing_thread.start()

    def _on_split_complete(self, payload: dict):
        self.append_log("Processing completed successfully.")
        QMessageBox.information(self, "Success", "PDF Splitter finished.")
        self.btn_open_output.setEnabled(True)
        if self.chk_open_after.isChecked():
            self.on_open_output_folder()
        self._set_idle_state()

    def _on_duplicate_request(self, info: dict):
        box = QMessageBox(self)
        box.setWindowTitle("File already exists")
        box.setText(f"{info.get('path')}\n\nChoose action:")
        btn_skip = box.addButton("Skip", QMessageBox.RejectRole)
        btn_overwrite = box.addButton("Overwrite", QMessageBox.AcceptRole)
        box.addButton("Cancel All", QMessageBox.DestructiveRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_skip:
            decision = "skip"
        elif clicked == btn_overwrite:
            decision = "overwrite"
        else:
            decision = "cancel_all"

        self._worker.set_duplicate_decision(decision)

    def _on_worker_error(self, err: str):
        self.append_log(f"[ERROR] {err}")
        QMessageBox.critical(self, "Error", err)

    def _on_worker_finished(self, _success: bool):
        if self._processing_thread:
            self._processing_thread.quit()
            self._processing_thread.wait(1500)
        self._processing_thread = None
        self._worker = None
        self._set_idle_state()

    def on_browse_output_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select output folder", self.selected_output_path)
        if folder_path:
            self.selected_output_path = folder_path
            self.txt_output_path.setText(folder_path)
            self.btn_open_output.setEnabled(True)
            self._save_default_output_path(folder_path)

    def on_open_output_folder(self):
        if self.selected_output_path and os.path.isdir(self.selected_output_path):
            try:
                os.startfile(self.selected_output_path)
            except Exception as e:
                QMessageBox.warning(self, "Cannot open folder", str(e))

    def on_clear(self):
        self.selected_pdf_path = ""
        self.lbl_pdf_path.setText("No file selected")
        self.lbl_estimate.setText("Invoice estimate will appear here after analysis.")
        self.cmb_from.clear()
        self.cmb_to.clear()
        self.txt_logs.clear()
        self.progress.setValue(0)
        self.analysis_done = False
        self._set_idle_state()

    def _save_default_output_path(self, folder_path: str):
        self._settings["defaultOutputPath"] = folder_path
        save_settings(self._settings)

    def _save_last_input_dir(self, input_dir: str):
        self._settings["lastInputDir"] = input_dir
        save_settings(self._settings)
