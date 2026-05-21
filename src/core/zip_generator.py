import os
import zipfile
from typing import Any, Callable, Dict, List, Optional


def create_asn_single_zip_from_invoice_bytes(
    output_path: str,
    zip_name_raw: str,
    ordered_groups_for_contents: List[Dict[str, Any]],
    pdf_bytes_by_invoice_raw: Dict[str, bytes],
    overwrite: bool,
    log_cb: Optional[Callable[[str], None]] = None
) -> List[str]:
    """
    Creates ONE ZIP file with a fixed name:
      {zip_name_raw}.zip

    ZIP content:
      {invoice_raw}.pdf   (NO integer-only names)
    """

    if not os.path.isdir(output_path):
        raise ValueError("Output path does not exist.")

    if not ordered_groups_for_contents:
        # avoid creating empty zip
        return []

    zip_path = os.path.join(output_path, f"{str(zip_name_raw)}.zip")

    if os.path.exists(zip_path) and not overwrite:
        if log_cb:
            log_cb(f"Skipping existing ZIP: {zip_path}")
        return []

    if os.path.exists(zip_path) and overwrite:
        if log_cb:
            log_cb(f"Overwriting existing ZIP: {zip_path}")

    if log_cb:
        inv_list = ", ".join([str(g["invoice_int"]) for g in ordered_groups_for_contents])
        log_cb(f"Creating SINGLE ZIP: {os.path.basename(zip_path)} (Invoices: {inv_list})")

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for g in ordered_groups_for_contents:
            raw = g["invoice_raw"]
            pdf_bytes = pdf_bytes_by_invoice_raw.get(raw)
            if pdf_bytes is None:
                raise ValueError(f"Missing PDF bytes for invoice raw={raw} while creating ZIP.")

            # keep leading zeros inside ZIP
            zf.writestr(f"{raw}.pdf", pdf_bytes)

    return [zip_path]
