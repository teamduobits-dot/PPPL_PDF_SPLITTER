import os
from typing import Any, Dict, List

from pypdf import PdfReader, PdfWriter


def split_invoice_groups_to_pdfs(
    file_path: str,
    output_path: str,
    groups: List[Dict[str, Any]],
    overwrite: bool = True,
    log_cb=None
) -> List[str]:
    """
    Splits the uploaded PDF into one output PDF per invoice group.

    groups item example:
      {
        "invoice_int": 586,
        "invoice_raw": "00586",
        "page_indices": [0,1,2]
      }
    """
    if not os.path.isdir(output_path):
        raise ValueError("Output path does not exist.")

    reader = PdfReader(file_path)

    created_paths: List[str] = []

    for g in groups:
        invoice_raw = g["invoice_raw"]
        page_indices = g["page_indices"]  # expected 0-based indices
        out_file = os.path.join(output_path, f"{invoice_raw}.pdf")

        if os.path.exists(out_file) and not overwrite:
            if log_cb:
                log_cb(f"Skipping existing file: {out_file}")
            continue

        if log_cb:
            log_cb(f"Creating PDF: {invoice_raw}.pdf")

        writer = PdfWriter()
        for idx in page_indices:
            # pypdf pages are 0-based
            writer.add_page(reader.pages[idx])

        with open(out_file, "wb") as f:
            writer.write(f)

        created_paths.append(out_file)

    return created_paths
