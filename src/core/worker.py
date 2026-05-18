import os
import threading
from io import BytesIO
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal
from pypdf import PdfReader, PdfWriter

from src.core.pdf_reader import analyze_pdf_candidates
from src.core.invoice_grouping import build_invoice_groups_from_pdf, validate_invoice_range
from src.core.zip_generator import create_asn_single_zip_from_invoice_bytes


class CancelAllSelected(Exception):
    pass


class PdfProcessingWorker(QObject):
    """
    Modes:
      - "analyze" (Phase 3)
      - "split_range" (Phase 4+5+6+8: validate + PDFs + ONE ZIP + duplicate handling)
    """

    log = Signal(str)
    progress = Signal(int)

    analysis_complete = Signal(object)
    split_complete = Signal(object)

    error = Signal(str)
    finished = Signal(bool)

    # Ask UI for duplicate decision
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

    def _compute_zip_name_int_from_groups(self, groups: List[Dict[str, Any]]) -> int:
        if not groups:
            raise ValueError("Cannot compute zip name from empty groups.")
        mid_index = (len(groups) - 1) // 2
        return int(groups[mid_index]["invoice_int"])

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

        if not self.file_path or not os.path.isfile(self.file_path):
            raise ValueError("Uploaded PDF file is missing or invalid.")

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

        self.log.emit("PDF analysis completed (Phase 3).")
        self.finished.emit(True)

    def _run_split_with_duplicates(self):
        self.log.emit("Validating invoice range (Phase 4) + creating PDFs (Phase 5) + one ZIP (Phase 6) + duplicates (Phase 8)...")
        self.progress.emit(5)

        if not self.file_path or not os.path.isfile(self.file_path):
            raise ValueError("Uploaded PDF file is missing or invalid.")
        if not self.output_path or not os.path.isdir(self.output_path):
            raise ValueError("Output folder is missing or invalid.")

        if not self.from_invoice or not self.to_invoice:
            raise ValueError("Invalid invoice range selected")

        try:
            from_int = int(self.from_invoice)
            to_int = int(self.to_invoice)
        except Exception:
            raise ValueError("Invalid invoice range selected")

        if from_int <= 0 or to_int <= 0:
            raise ValueError("Invalid invoice range selected")

        # Re-analyze candidates
        self.log.emit("Re-checking invoice candidates (Phase 3 inside Phase 4)...")
        self.progress.emit(20)

        candidate_result = analyze_pdf_candidates(self.file_path)
        invoice_ids = candidate_result.invoice_ids

        self.progress.emit(35)
        groups_obj = build_invoice_groups_from_pdf(self.file_path, invoice_ids=invoice_ids)

        self.progress.emit(55)
        payload_validation = validate_invoice_range(groups_obj, from_int=from_int, to_int=to_int)

        warnings = payload_validation.get("warnings", []) or []
        selected_groups: List[Dict[str, Any]] = payload_validation.get("groups", []) or []
        invoice_ids = payload_validation.get("invoice_ids", []) or []

        if not selected_groups:
            raise ValueError("No invoice groups matched the selected range.")

        # sort by invoice_int ascending (stable)
        selected_groups = sorted(selected_groups, key=lambda g: int(g["invoice_int"]))

        # Options
        zip_only_enabled = bool(self.options.get("zip_only", False))
        individual_enabled = bool(self.options.get("individual_pdfs", False))

        if not (zip_only_enabled or individual_enabled):
            raise ValueError("No output option selected. Enable PDF and/or ZIP.")

        # -------- Pre-flight duplicates (decide first, write later) --------

        pdf_should_create: Dict[str, bool] = {}  # invoice_raw -> bool
        created_pdf_paths: List[str] = []
        created_zip_paths: List[str] = []

        # ZIP name is based on FULL selected range (unfiltered)
        zip_name_int_preview = self._compute_zip_name_int_from_groups(selected_groups)
        zip_path_preview = os.path.join(self.output_path, f"{zip_name_int_preview}.zip")

        # 1) PDF duplicates (only if individual PDFs are enabled)
        if individual_enabled:
            self.log.emit("Checking duplicate PDF files (Phase 8)...")
            for g in selected_groups:
                raw = g["invoice_raw"]
                inv_int = int(g["invoice_int"])
                out_pdf = os.path.join(self.output_path, f"{inv_int}.pdf")

                if os.path.exists(out_pdf):
                    self.log.emit(f"Duplicate found: {os.path.basename(out_pdf)}")
                    decision = self._ask_user_duplicate({
                        "kind": "pdf",
                        "path": out_pdf,
                        "invoice_int": inv_int,
                        "invoice_raw": raw
                    })

                    if decision == "cancel_all":
                        raise CancelAllSelected()
                    elif decision == "skip":
                        pdf_should_create[raw] = False
                    elif decision == "overwrite":
                        pdf_should_create[raw] = True
                    else:
                        raise ValueError(f"Unknown duplicate decision: {decision}")
                else:
                    pdf_should_create[raw] = True

        # 2) ZIP duplicates (only if ZIP enabled)
        zip_should_create = False
        if zip_only_enabled:
            zip_should_create = True  # default if no duplicates
            if os.path.exists(zip_path_preview):
                self.log.emit(f"Duplicate found: {os.path.basename(zip_path_preview)}")
                decision = self._ask_user_duplicate({
                    "kind": "zip",
                    "path": zip_path_preview,
                    "zip_name_int": zip_name_int_preview
                })

                if decision == "cancel_all":
                    raise CancelAllSelected()
                elif decision == "skip":
                    zip_should_create = False
                elif decision == "overwrite":
                    zip_should_create = True
                else:
                    raise ValueError(f"Unknown duplicate decision: {decision}")

        # Determine which groups we will actually create PDFs for / include in ZIP
        groups_for_pdf_create: List[Dict[str, Any]] = []
        if individual_enabled:
            for g in selected_groups:
                if pdf_should_create.get(g["invoice_raw"], True):
                    groups_for_pdf_create.append(g)

        # ZIP contents selection:
        # - if ZIP disabled => no zip
        # - if ZIP enabled AND individual disabled (zip-only) => include all invoices
        # - if ZIP enabled AND individual enabled => include only the PDFs that will be created
        groups_for_zip_contents: List[Dict[str, Any]] = []
        if zip_only_enabled and zip_should_create:
            if individual_enabled:
                groups_for_zip_contents = groups_for_pdf_create
            else:
                groups_for_zip_contents = selected_groups

        if zip_only_enabled and zip_should_create and not groups_for_zip_contents:
            self.log.emit("All PDFs were skipped; ZIP content is empty. ZIP creation skipped.")
            zip_should_create = False

        self.progress.emit(75)

        # -------- Write stage (after decisions) --------
        reader = PdfReader(self.file_path)

        # Generate PDF bytes in-memory for invoices that we need in output
        groups_needed_for_bytes: List[Dict[str, Any]] = []
        if individual_enabled and groups_for_pdf_create:
            groups_needed_for_bytes.extend(groups_for_pdf_create)
        if zip_should_create and groups_for_zip_contents:
            # zip-only uses all; both uses only pdf-create groups
            groups_needed_for_bytes.extend(groups_for_zip_contents)

        # Deduplicate by invoice_raw
        seen_raw: Set[str] = set()
        unique_needed: List[Dict[str, Any]] = []
        for g in groups_needed_for_bytes:
            raw = g["invoice_raw"]
            if raw not in seen_raw:
                seen_raw.add(raw)
                unique_needed.append(g)

        self.log.emit("Generating PDF bytes (in-memory)...")
        total = len(unique_needed) if unique_needed else 1
        done = 0

        pdf_bytes_by_invoice_raw: Dict[str, bytes] = {}

        for g in unique_needed:
            raw = g["invoice_raw"]
            page_indices = g["page_indices"]

            writer = PdfWriter()
            for idx in page_indices:
                writer.add_page(reader.pages[idx])

            buf = BytesIO()
            writer.write(buf)
            pdf_bytes_by_invoice_raw[raw] = buf.getvalue()

            done += 1
            percent = 75 + int(done * 15 / total)
            self.progress.emit(min(percent, 90))

        # Save individual PDFs (Phase 5)
        if individual_enabled and groups_for_pdf_create:
            self.log.emit("Saving individual PDFs (Phase 5)...")
            for g in groups_for_pdf_create:
                raw = g["invoice_raw"]
                inv_int = int(g["invoice_int"])
                out_pdf = os.path.join(self.output_path, f"{inv_int}.pdf")

                pdf_bytes = pdf_bytes_by_invoice_raw.get(raw)
                if pdf_bytes is None:
                    continue

                # Overwrite always (skip/overwrite decided in pre-flight)
                with open(out_pdf, "wb") as f:
                    f.write(pdf_bytes)

                created_pdf_paths.append(out_pdf)
                self.log.emit(f"Created PDF: {os.path.basename(out_pdf)}")

        # Create ONE ZIP (Phase 6)
        if zip_only_enabled and zip_should_create:
            self.log.emit("Creating ONE ASN ZIP (Phase 6)...")
            self.progress.emit(95)

            created_zip_paths = create_asn_single_zip_from_invoice_bytes(
                output_path=self.output_path,
                zip_name_int=zip_name_int_preview,
                ordered_groups_for_contents=groups_for_zip_contents,
                pdf_bytes_by_invoice_raw=pdf_bytes_by_invoice_raw,
                overwrite=True,
                log_cb=self.log.emit
            )
        else:
            self.log.emit("ZIP creation skipped (ZIP option unchecked or skipped due to duplicates).")

        self.progress.emit(100)

        out = {
            "from_invoice_int": from_int,
            "to_invoice_int": to_int,
            "pad_len": payload_validation.get("pad_len"),
            "invoice_ids": invoice_ids,
            "warnings": warnings,
            "created_pdfs_count": len(created_pdf_paths),
            "created_zips_count": len(created_zip_paths),
            "created_pdf_paths": created_pdf_paths,
            "created_zip_paths": created_zip_paths
        }

        self.split_complete.emit(out)
        self.log.emit("Phase 4+5+6+8 completed successfully.")
        self.finished.emit(True)
