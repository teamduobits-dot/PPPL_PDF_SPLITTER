import os
import threading
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal
from pypdf import PdfReader

from src.core.pdf_reader import analyze_pdf_candidates
from src.core.invoice_grouping import build_invoice_groups_from_pdf, validate_invoice_range
from src.core.signature_safe_pdf_splitter import signature_safe_split_keep_pages
from src.core.zip_generator import create_asn_single_zip_from_invoice_bytes


class CancelAllSelected(Exception):
    pass


class PdfProcessingWorker(QObject):
    log = Signal(str)
    progress = Signal(int)

    analysis_complete = Signal(object)
    split_complete = Signal(object)

    error = Signal(str)
    finished = Signal(bool)

    request_duplicate = Signal(object)

    def __init__(
        self,
        mode: str,
        file_path: str,
        output_path: str,
        options: Dict[str, Any],
        from_invoice: str,
        to_invoice: str
    ):
        super().__init__()
        self.mode = mode
        self.file_path = file_path
        self.output_path = output_path
        self.options = options
        self.from_invoice = from_invoice
        self.to_invoice = to_invoice

        self._dup_event = threading.Event()
        self._dup_decision: Optional[str] = None

    def set_duplicate_decision(self, decision: str):
        self._dup_decision = decision
        self._dup_event.set()

    def _ask_user_duplicate(self, info: Dict[str, Any]) -> str:
        self._dup_decision = None
        self._dup_event.clear()
        self.request_duplicate.emit(info)
        self._dup_event.wait()
        if not self._dup_decision:
            raise ValueError("Duplicate decision was not provided by UI.")
        return self._dup_decision

    def run(self):
        try:
            if self.mode == "analyze":
                self._run_analyze()
                return
            if self.mode == "split_range":
                self._run_split_with_duplicates()
                return
            self.log.emit(f"Mode not implemented: {self.mode}")
            self.finished.emit(False)
        except CancelAllSelected:
            self.error.emit("Cancel All selected. No PDFs and no ZIPs were created.")
            self.finished.emit(False)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)

    def _run_analyze(self):
        self.log.emit("Reading PDF (Phase 3)...")
        self.progress.emit(10)

        result = analyze_pdf_candidates(self.file_path)

        payload = {
            "page_count": result.page_count,
            "invoice_ids": result.invoice_ids,
            "min_invoice_int": result.min_invoice_int,
            "max_invoice_int": result.max_invoice_int,
            "candidate_count": result.candidate_count
        }

        self.progress.emit(90)
        self.analysis_complete.emit(payload)
        self.progress.emit(100)
        self.log.emit("Phase 3 completed.")
        self.finished.emit(True)

    def _run_split_with_duplicates(self):
        self.log.emit("Processing started...")
        self.progress.emit(10)

        candidate_result = analyze_pdf_candidates(self.file_path)
        groups_obj = build_invoice_groups_from_pdf(self.file_path, invoice_ids=candidate_result.invoice_ids)
        payload_validation = validate_invoice_range(groups_obj, from_int=int(self.from_invoice), to_int=int(self.to_invoice))

        selected_groups = payload_validation.get("groups", [])
        selected_groups = sorted(selected_groups, key=lambda g: int(g["invoice_int"]))

        zip_only_enabled = bool(self.options.get("zip_only", False))
        individual_enabled = bool(self.options.get("individual_pdfs", False))

        created_pdf_paths = []
        created_zip_paths = []

        pdf_bytes_by_invoice_raw = {}

        for g in selected_groups:
            raw = str(g["invoice_int"])  # No leading zeros
            out_pdf = os.path.join(self.output_path, f"{raw}.pdf")

            signature_safe_split_keep_pages(
                input_pdf_path=self.file_path,
                output_pdf_path=out_pdf,
                keep_page_indices=list(g["page_indices"]),
                overwrite=True,
                log_cb=self.log.emit
            )
            created_pdf_paths.append(out_pdf)

            with open(out_pdf, "rb") as f:
                pdf_bytes_by_invoice_raw[raw] = f.read()

        if zip_only_enabled:
            mid = selected_groups[len(selected_groups)//2]["invoice_int"]
            created_zip_paths = create_asn_single_zip_from_invoice_bytes(
                output_path=self.output_path,
                zip_name_raw=str(mid),
                ordered_groups_for_contents=selected_groups,
                pdf_bytes_by_invoice_raw=pdf_bytes_by_invoice_raw,
                overwrite=True,
                log_cb=self.log.emit
            )

        self.progress.emit(100)
        self.split_complete.emit({
            "created_pdfs_count": len(created_pdf_paths),
            "created_zips_count": len(created_zip_paths),
            "created_pdf_paths": created_pdf_paths,
            "created_zip_paths": created_zip_paths
        })
        self.log.emit("Processing completed successfully.")
        self.finished.emit(True)
