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
        self.setMinimumWidth(980)
        self.setMinimumHeight(720)

        # ---------------- Settings ----------------
        self._settings: Dict[str, Any] = load_settings()

        # Phase 3 state
        self.selected_pdf_path: str = ""
        self.selected_output_path: str = self._settings.get("defaultOutputPath", "") or ""
        self.detected_invoice_ids: List[str] = []
        self.analysis_done: bool = False
        self.single_invoice_detected: bool = False

        # Worker state
        self._processing_thread: Optional[QThread] = None
        self._worker: Optional[PdfProcessingWorker] = None

        self._build_ui()
        self._apply_style()
        self._apply_settings_to_ui()
        self._set_idle_state()

    # ---------------- Styling ----------------
    def _apply_style(self):
        self.setStyleSheet(APP_STYLE)

    # ---------------- UI Build ----------------
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ===== Top area (Logo + Title) =====
        logo_row = QVBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)

        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignCenter)

        # ✅ Correct logo path: src/ui/assets/PPPL_LOGO.png
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "PPPL_LOGO.png")
        pix = QPixmap(logo_path)
        if not pix.isNull():
            self.lbl_logo.setPixmap(pix.scaledToHeight(64, Qt.SmoothTransformation))
            self.lbl_logo.setToolTip("PPPL PDF Splitter")
        else:
            self.lbl_logo.setText("PPPL PDF Splitter")

        header = QLabel("PPPL PDF Splitter")
        header_font = QFont()
        header_font.setPointSize(22)
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
        row.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        row.addLayout(right_col, 1)

        # ========= Left: Upload =========
        upload_box = QGroupBox("PDF Upload Section")
        upload_layout = QVBoxLayout(upload_box)

        self.btn_upload = QPushButton("Upload PDF")
        self.lbl_pdf_path = QLabel("No file selected")
        self.lbl_pdf_path.setWordWrap(True)

        self.lbl_estimate = QLabel("Invoice estimate will appear here after PDF analysis (Phase 3).")

        upload_layout.addWidget(self.btn_upload)
        upload_layout.addWidget(self.lbl_pdf_path)
        upload_layout.addWidget(self.lbl_estimate)
        left_col.addWidget(upload_box)

        # ========= Left: Invoice Range =========
        range_box = QGroupBox("Invoice Range Section")
        range_layout = QFormLayout(range_box)

        self.cmb_from = QComboBox()
        self.cmb_from.setEditable(True)
        self.cmb_from.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_from.setPlaceholderText("Type FROM (e.g., 00586)")

        self.cmb_to = QComboBox()
        self.cmb_to.setEditable(True)
        self.cmb_to.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_to.setPlaceholderText("Type TO (e.g., 00613)")

        range_layout.addRow("FROM:", self.cmb_from)
        range_layout.addRow("TO:", self.cmb_to)
        left_col.addWidget(range_box)

        # ========= Right: Output =========
        output_box = QGroupBox("Output Section")
        output_layout = QVBoxLayout(output_box)

        out_row = QHBoxLayout()
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setPlaceholderText("Select output folder (UNC path supported)")
        self.txt_output_path.setReadOnly(True)

        self.btn_browse_output = QPushButton("Browse Folder")

        out_row.addWidget(self.txt_output_path, 1)
        out_row.addWidget(self.btn_browse_output)
        output_layout.addLayout(out_row)
        right_col.addWidget(output_box)

        # ========= Right: Options =========
        options_box = QGroupBox("Processing Options")
        options_layout = QVBoxLayout(options_box)

        self.chk_zip_only = QCheckBox("Generate ASN ZIP Files Only")
        self.chk_individual_pdfs = QCheckBox("Generate Individual PDFs")
        self.chk_open_after = QCheckBox("Open Folder After Processing")

        options_layout.addWidget(self.chk_zip_only)
        options_layout.addWidget(self.chk_individual_pdfs)
        options_layout.addWidget(self.chk_open_after)
        right_col.addWidget(options_box)

        # ========= Right: Logs =========
        logs_box = QGroupBox("Processing Logs")
        logs_layout = QVBoxLayout(logs_box)

        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        logs_layout.addWidget(self.progress)
        logs_layout.addWidget(self.txt_logs)
        main_layout.addWidget(logs_box)

        # Buttons row
        btn_row = QHBoxLayout()
        main_layout.addLayout(btn_row)

        self.btn_start = QPushButton("Start Processing")
        self.btn_clear = QPushButton("Clear")
        self.btn_open_output = QPushButton("Open Output Folder")
        self.btn_open_output.setEnabled(False)

        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_open_output)

        footer = QLabel("Developed by Duobits Software Solutions    |    Version 1.0")
        footer.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(footer)

        # Wire events
        self.btn_upload.clicked.connect(self.on_upload_pdf)
        self.btn_browse_output.clicked.connect(self.on_browse_output_folder)
        self.btn_start.clicked.connect(self.on_start_processing)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_open_output.clicked.connect(self.on_open_output_folder)

        self.chk_open_after.stateChanged.connect(self._on_open_after_changed)
        self.chk_zip_only.stateChanged.connect(self._on_output_options_changed)
        self.chk_individual_pdfs.stateChanged.connect(self._on_output_options_changed)

        self.cmb_from.clear()
        self.cmb_to.clear()

    # ---------------- Settings apply/save ----------------
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

    # ---------------- UI state helpers ----------------
    def _set_busy_state(self):
        self.btn_upload.setEnabled(False)
        self.btn_browse_output.setEnabled(False)
        self.btn_clear.setEnabled(False)

        self.chk_zip_only.setEnabled(False)
        self.chk_individual_pdfs.setEnabled(False)
        self.chk_open_after.setEnabled(False)

        self.cmb_from.setEnabled(False)
        self.cmb_to.setEnabled(False)

        self.btn_start.setEnabled(False)
        self.btn_open_output.setEnabled(False)

    def _set_idle_state(self):
        self.btn_upload.setEnabled(True)
        self.btn_browse_output.setEnabled(True)
        self.btn_clear.setEnabled(True)

        self.chk_zip_only.setEnabled(True)
        self.chk_individual_pdfs.setEnabled(True)
        self.chk_open_after.setEnabled(True)

        self.cmb_from.setEnabled(self.analysis_done)
        self.cmb_to.setEnabled(self.analysis_done)

        self.btn_start.setEnabled(self.analysis_done)
        self.btn_open_output.setEnabled(bool(self.selected_output_path))

    def append_log(self, msg: str):
        self.txt_logs.append(msg)

    # ---------------- helpers ----------------
    def _get_from_to_values(self):
        return self.cmb_from.currentText().strip(), self.cmb_to.currentText().strip()

    def _parse_int_invoice(self, s: str) -> Optional[int]:
        if not s:
            return None
        s2 = s.strip()
        if not s2.isdigit():
            return None
        try:
            return int(s2)
        except Exception:
            return None

    # ---------------- Phase 3: Upload + Analyze ----------------
    def on_upload_pdf(self):
        last_input_dir = self._settings.get("lastInputDir", "") or ""
        if last_input_dir and not os.path.isdir(last_input_dir):
            last_input_dir = ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select merged ERP invoice PDF",
            last_input_dir,
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        self._save_last_input_dir(os.path.dirname(file_path))

        self.selected_pdf_path = file_path
        self.lbl_pdf_path.setText(file_path)

        self.analysis_done = False
        self.detected_invoice_ids = []
        self.single_invoice_detected = False

        self.cmb_from.clear()
        self.cmb_to.clear()

        self.lbl_estimate.setText("Analyzing PDF... (Phase 3)")
        self.txt_logs.clear()
        self.progress.setValue(0)

        self.selected_output_path = self._settings.get("defaultOutputPath", "") or ""
        self.txt_output_path.setText(self.selected_output_path)
        self.btn_open_output.setEnabled(bool(self.selected_output_path))

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
            self.lbl_estimate.setText("No invoice candidates found in Phase 3.")
            self.analysis_done = False
            self.single_invoice_detected = False
            self._set_idle_state()
            return

        self.cmb_from.clear()
        self.cmb_to.clear()
        self.cmb_from.addItems(invoice_ids)
        self.cmb_to.addItems(invoice_ids)
        self.cmb_from.setCurrentText(invoice_ids[0])
        self.cmb_to.setCurrentText(invoice_ids[-1])

        self.single_invoice_detected = (len(invoice_ids) == 1)

        page_count = payload.get("page_count", "?")
        cand_count = payload.get("candidate_count", len(invoice_ids))

        self.lbl_estimate.setText(
            f"Phase 3 estimate: Invoices detected from {invoice_ids[0]} to {invoice_ids[-1]} "
            f"(Candidates: {cand_count}, Pages: {page_count})."
        )

        self.analysis_done = True
        self.append_log(f"Phase 3 detected invoices: {invoice_ids}")

        if self.single_invoice_detected:
            QMessageBox.warning(
                self,
                "Single invoice cannot be split",
                "This PDF contains only ONE invoice.\nA single invoice cannot be split."
            )

        self._set_idle_state()

    # ---------------- Phase 4+: Start Processing ----------------
    def on_start_processing(self):
        if not self.analysis_done:
            QMessageBox.warning(self, "Not Ready", "Please upload a PDF first and wait for Phase 3 analysis.")
            return

        if not self.selected_pdf_path:
            QMessageBox.warning(self, "Missing PDF", "Please upload a merged PDF first.")
            return

        if not self.selected_output_path:
            QMessageBox.warning(self, "Missing Output Path", "Please select an output folder first.")
            return

        from_val, to_val = self._get_from_to_values()
        from_int = self._parse_int_invoice(from_val)
        to_int = self._parse_int_invoice(to_val)

        if from_int is None or to_int is None:
            QMessageBox.warning(self, "Missing/Invalid Range", "Please enter numeric FROM and TO invoice values.")
            return

        if from_int > to_int:
            QMessageBox.warning(self, "Invalid invoice range selected", "FROM must be <= TO.")
            return

        # Requirement: single invoice cannot be split
        if from_int == to_int:
            QMessageBox.warning(
                self,
                "Single invoice cannot be split",
                f"You selected only invoice {from_val}.\nPlease upload a merged PDF that contains multiple invoices."
            )
            return

        detected_ints = set(int(x) for x in self.detected_invoice_ids if x and x.isdigit())
        if from_int not in detected_ints or to_int not in detected_ints:
            QMessageBox.warning(
                self,
                "Invoice range not found in uploaded PDF",
                "Invoice range not found in uploaded PDF."
            )
            return

        if not (self.chk_zip_only.isChecked() or self.chk_individual_pdfs.isChecked()):
            QMessageBox.warning(
                self,
                "Select Output Type",
                "Please enable at least one option: ZIP only and/or Individual PDFs."
            )
            return

        options = {
            "zip_only": self.chk_zip_only.isChecked(),
            "individual_pdfs": self.chk_individual_pdfs.isChecked(),
            "open_after": self.chk_open_after.isChecked(),
        }

        self.progress.setValue(0)
        self.append_log("========================================")
        self.append_log("Start Processing clicked.")
        self.append_log(f"Selected range: FROM={from_val} TO={to_val}")

        self._set_busy_state()

        self._worker = PdfProcessingWorker(
            mode="split_range",
            file_path=self.selected_pdf_path,
            output_path=self.selected_output_path,
            options=options,
            from_invoice=str(from_int),
            to_invoice=str(to_int)
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

    def _on_duplicate_request(self, info: dict):
        if not self._worker:
            return

        kind = info.get("kind")
        if kind == "pdf":
            path = info.get("path", "")
            invoice_int = info.get("invoice_int", "")
            title = "File already exists"
            text = f"Invoice PDF already exists:\n{path}\n\nInvoice: {invoice_int}\n\nChoose action:"
        else:
            path = info.get("path", "")
            title = "ZIP already exists"
            text = f"ASN ZIP already exists:\n{path}\n\nChoose action:"

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Warning)
        box.setText(text)

        btn_skip = box.addButton("Skip", QMessageBox.RejectRole)
        btn_overwrite = box.addButton("Overwrite", QMessageBox.AcceptRole)
        _btn_cancel = box.addButton("Cancel All", QMessageBox.DestructiveRole)

        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_skip:
            decision = "skip"
        elif clicked == btn_overwrite:
            decision = "overwrite"
        else:
            decision = "cancel_all"

        self._worker.set_duplicate_decision(decision)

    def _on_split_complete(self, payload: dict):
        warnings = payload.get("warnings", []) or []

        created_pdfs_count = payload.get("created_pdfs_count", 0)
        created_zips_count = payload.get("created_zips_count", 0)

        self.append_log("========================================")
        self.append_log("Phase 4+5+6+8 completed successfully.")
        self.append_log(f"Created PDFs: {created_pdfs_count}")
        self.append_log(f"Created ZIPs: {created_zips_count}")

        if warnings:
            QMessageBox.warning(self, "Phase 4 Validation Warnings", "\n".join(warnings))

        QMessageBox.information(
            self,
            "Processing Complete",
            "PDF splitting + ASN ZIP generation completed successfully."
        )

        self.btn_open_output.setEnabled(True)
        if self.chk_open_after.isChecked():
            self.on_open_output_folder()

        self._set_idle_state()

    # ---------------- Worker handlers ----------------
    def _on_worker_error(self, err: str):
        self.append_log(f"[ERROR] {err}")
        if "Cancel All selected" in err:
            QMessageBox.information(self, "Cancelled", err)
        else:
            QMessageBox.critical(self, "Error", err)

    def _on_worker_finished(self, _success: bool):
        if self._processing_thread is not None:
            self._processing_thread.quit()
            self._processing_thread.wait(2000)
        self._processing_thread = None
        self._worker = None
        self._set_idle_state()

    # ---------------- Output folder ----------------
    def on_browse_output_folder(self):
        initial_dir = self._settings.get("defaultOutputPath", "") or ""
        if initial_dir and not os.path.isdir(initial_dir):
            initial_dir = ""

        folder_path = QFileDialog.getExistingDirectory(self, "Select output folder", initial_dir)
        if not folder_path:
            return

        self.selected_output_path = folder_path
        self.txt_output_path.setText(folder_path)
        self.btn_open_output.setEnabled(True)

        self._save_default_output_path(folder_path)

    def on_open_output_folder(self):
        if not self.selected_output_path:
            return
        if not os.path.isdir(self.selected_output_path):
            QMessageBox.warning(self, "Folder missing", "Output folder does not exist.")
            return

        try:
            os.startfile(self.selected_output_path)
        except Exception as e:
            QMessageBox.warning(self, "Cannot open folder", str(e))

    # ---------------- Clear ----------------
    def on_clear(self):
        # Keep output folder + settings, just reset current PDF session
        self.selected_pdf_path = ""
        self.detected_invoice_ids = []
        self.analysis_done = False
        self.single_invoice_detected = False

        self.lbl_pdf_path.setText("No file selected")
        self.lbl_estimate.setText("Invoice estimate will appear here after PDF analysis (Phase 3).")

        self.cmb_from.clear()
        self.cmb_to.clear()

        self.txt_logs.clear()
        self.progress.setValue(0)

        self.btn_open_output.setEnabled(bool(self.selected_output_path))
        self._set_idle_state()