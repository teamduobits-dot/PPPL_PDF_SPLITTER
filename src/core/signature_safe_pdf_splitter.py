import os
import shutil
from typing import Callable, List, Optional

import pikepdf


def signature_safe_split_keep_pages(
    input_pdf_path: str,
    output_pdf_path: str,
    keep_page_indices: List[int],
    overwrite: bool = True,
    log_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    New approach using copy_foreign to better preserve signature appearance.
    This usually keeps the "Authorised Signatory" box visible.
    """
    if not os.path.isfile(input_pdf_path):
        raise ValueError(f"Input PDF missing: {input_pdf_path}")

    if not keep_page_indices:
        raise ValueError("No pages to keep.")

    out_dir = os.path.dirname(output_pdf_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if os.path.exists(output_pdf_path) and not overwrite:
        if log_cb:
            log_cb(f"Skipping existing file: {output_pdf_path}")
        return False

    tmp_output = output_pdf_path + ".tmp"
    try:
        if os.path.exists(tmp_output):
            os.remove(tmp_output)

        with pikepdf.open(input_pdf_path) as src:
            dst = pikepdf.Pdf.new()

            for page_idx in sorted(set(keep_page_indices)):
                page = src.pages[page_idx]
                dst.pages.append(page)   # This uses copy_foreign internally

            dst.save(tmp_output, compress_streams=True, force_version="1.7")

        if os.path.exists(output_pdf_path):
            os.remove(output_pdf_path)
        os.replace(tmp_output, output_pdf_path)

        if log_cb:
            log_cb(f"Created: {os.path.basename(output_pdf_path)}")
        return True

    finally:
        if os.path.exists(tmp_output):
            try:
                os.remove(tmp_output)
            except Exception:
                pass
