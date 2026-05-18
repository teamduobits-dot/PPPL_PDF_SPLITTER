import re
from dataclasses import dataclass
from typing import Dict, List, Set

import fitz  # PyMuPDF


@dataclass
class PdfCandidateResult:
    page_count: int
    invoice_ids: List[str]      # padded strings, e.g. "00586"
    min_invoice_int: int
    max_invoice_int: int
    candidate_count: int


PAD_LEN = 5
MIN_INVOICE_INT = 100
MAX_INVOICE_INT = 999999


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00A0", " ")
    text = text.replace("\\u00A0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _candidate_ints_from_digit_string(num_str: str) -> List[int]:
    """
    Convert a digit string (usually captured after 'invoice' label) into candidate ints.
    """
    if not num_str or not num_str.isdigit():
        return []

    out: Set[int] = set()

    L = len(num_str)

    # If it's already 3..6 digits, keep as-is (after filtering)
    if 3 <= L <= 6:
        v = int(num_str)
        if MIN_INVOICE_INT <= v <= MAX_INVOICE_INT:
            out.add(v)

    # Also keep last 3..6 tails (helps when digits are concatenated)
    for tail_len in range(3, 7):
        if L >= tail_len:
            tail = num_str[-tail_len:]
            v = int(tail)
            if MIN_INVOICE_INT <= v <= MAX_INVOICE_INT:
                out.add(v)

    return sorted(out)


def _extract_invoice_digit_strings_from_labels(text: str) -> List[str]:
    """
    Extract digit sequences after invoice-like labels.
    """
    text_norm = _normalize_text(text)
    if not text_norm:
        return []

    patterns = [
        r"(?is)(?:invoice\s*(?:no\.?|number|id))\D{0,20}([0-9]{3,6})",
        r"(?is)(?:inv\s*\.?\s*no\.?)\D{0,20}([0-9]{3,6})",
    ]

    found: List[str] = []
    for pat in patterns:
        found.extend(re.findall(pat, text_norm))
    return found


def _extract_generic_invoice_ints(text: str) -> List[int]:
    """
    IMPORTANT FIX:
    - We ONLY want invoice numbers that look like padded IDs (with leading zeros).
    - This prevents picking '354' from 'SY NO. 354 ...'.

    Your invoice looks like: 00353, 00586, etc. (5 digits, starts with '00').
    """
    text_norm = _normalize_text(text)
    if not text_norm:
        return []

    # Primary: 5-digit invoice format starting with "00" => 00xxx (e.g., 00353)
    candidates_00xxx = re.findall(r"(?<!\d)0{2}\d{3}(?!\d)", text_norm)
    ints_00xxx: Set[int] = set()
    for tok in candidates_00xxx:
        v = int(tok)
        if MIN_INVOICE_INT <= v <= MAX_INVOICE_INT:
            ints_00xxx.add(v)

    if ints_00xxx:
        return sorted(ints_00xxx)

    # Secondary fallback: tokens that start with one or more zeros and then 3..6 digits.
    # This still avoids plain '354' (no leading zeros).
    candidates_leading0 = re.findall(r"(?<!\d)0+\d{3,6}(?!\d)", text_norm)
    ints: Set[int] = set()
    for tok in candidates_leading0:
        v = int(tok)
        if MIN_INVOICE_INT <= v <= MAX_INVOICE_INT:
            ints.add(v)

    return sorted(ints)


def _longest_consecutive_run(sorted_ints: List[int]) -> List[int]:
    if not sorted_ints:
        return []

    best_start = 0
    best_len = 1

    i = 0
    while i < len(sorted_ints):
        j = i
        while j + 1 < len(sorted_ints) and sorted_ints[j + 1] == sorted_ints[j] + 1:
            j += 1

        run_len = j - i + 1
        if run_len > best_len:
            best_len = run_len
            best_start = i

        i = j + 1

    return sorted_ints[best_start:best_start + best_len]


def analyze_pdf_candidates(file_path: str) -> PdfCandidateResult:
    doc = fitz.open(file_path)
    page_count = doc.page_count
    if page_count <= 0:
        raise ValueError("Uploaded PDF is empty.")

    pages_by_inv: Dict[int, Set[int]] = {}
    labeled_hits: Dict[int, int] = {}
    generic_hits: Dict[int, int] = {}

    for page_index in range(page_count):
        page = doc.load_page(page_index)
        text = page.get_text("text") or ""

        seen_on_page: Set[int] = set()

        # 1) Labeled extraction (best)
        label_digit_strings = _extract_invoice_digit_strings_from_labels(text)
        if label_digit_strings:
            for ds in label_digit_strings:
                for inv_int in _candidate_ints_from_digit_string(ds):
                    seen_on_page.add(inv_int)
                    labeled_hits[inv_int] = labeled_hits.get(inv_int, 0) + 1
        else:
            # 2) Generic extraction (fixed to avoid SY NO. noise)
            generic_ints = _extract_generic_invoice_ints(text)
            for inv_int in set(generic_ints):
                seen_on_page.add(inv_int)
                generic_hits[inv_int] = generic_hits.get(inv_int, 0) + 1

        for inv_int in seen_on_page:
            pages_by_inv.setdefault(inv_int, set()).add(page_index)

    # Noise control:
    # - Short docs: allow 1 page candidate
    # - Longer docs: require 2 pages to stabilize
    required_pages = 1 if page_count <= 3 else 2

    kept_ints = sorted([inv for inv, pages in pages_by_inv.items() if len(pages) >= required_pages])

    if not kept_ints:
        kept_ints = sorted([inv for inv in pages_by_inv.keys() if len(pages_by_inv[inv]) >= 1])

    if not kept_ints:
        raise ValueError(
            "No invoice candidates were found in Phase 3.\n"
            "If the PDF is scanned or text extraction is poor, OCR may be required."
        )

    # Selection:
    # - If short PDF: pick ONE best invoice (prevents ranges like 353-354 inside single-invoice docs)
    if page_count <= 3:
        def best_key(inv: int):
            pages_set = pages_by_inv.get(inv, set())
            return (
                len(pages_set),
                labeled_hits.get(inv, 0),
                generic_hits.get(inv, 0),
                -inv
            )

        best_inv = max(kept_ints, key=best_key)
        selected_ints = [best_inv]
    else:
        run = _longest_consecutive_run(kept_ints)
        if len(run) >= 2:
            selected_ints = run
        else:
            def best_key(inv: int):
                return (len(pages_by_inv.get(inv, set())), labeled_hits.get(inv, 0), generic_hits.get(inv, 0), -inv)

            best_inv = max(kept_ints, key=best_key)
            selected_ints = [best_inv]

    invoice_ids = [f"{inv:0{PAD_LEN}d}" for inv in selected_ints]

    return PdfCandidateResult(
        page_count=page_count,
        invoice_ids=invoice_ids,
        min_invoice_int=selected_ints[0],
        max_invoice_int=selected_ints[-1],
        candidate_count=len(invoice_ids),
    )