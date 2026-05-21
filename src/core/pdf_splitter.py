import os
from typing import Any, Dict, List, Optional

from src.core.signature_safe_pdf_splitter import signature_safe_split_keep_pages


def split_invoice_groups_to_pdfs(
    file_path: str,
    output_path: str,
    groups: List[Dict[str, Any]],
    overwrite: bool = True,
    log_cb=None
) -> List[str]:
    """
    Signature-safe splitting into:
      {invoice_raw}.pdf
    """
    if not os.path.isdir(output_path):
        raise ValueError("Output path does not exist.")

    created_paths: List[str] = []

    for g in groups:
        invoice_raw = g["invoice_raw"]
        page_indices = g["page_indices"]  # expected 0-based indices
        out_file = os.path.join(output_path, f"{invoice_raw}.pdf")

        wrote = signature_safe_split_keep_pages(
            input_pdf_path=file_path,
            output_pdf_path=out_file,
            keep_page_indices=list(page_indices),
            overwrite=overwrite,
            incremental=True,
            log_cb=log_cb
        )

        if wrote:
            created_paths.append(out_file)

    return created_paths
