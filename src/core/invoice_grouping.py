import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set

import fitz


@dataclass
class InvoicePageGroup:
    invoice_int: int
    invoice_raw: str
    invoice_pad_len: int
    page_indices: List[int]


def _normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("\\u00A0", " ")
    text = text.replace("\u00A0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_candidate_regex(invoice_ints: List[int]) -> str:
    invoice_ints = sorted(set(i for i in invoice_ints if i > 0))
    parts = [f"0*{i}" for i in invoice_ints]
    return r"(?<!\d)(?:" + "|".join(parts) + r")(?!\d)"


def _tails_of_3_to_6_digits(num_str: str) -> List[int]:
    if not num_str or not num_str.isdigit():
        return []
    out: List[int] = []
    for L in range(3, 7):
        if len(num_str) >= L:
            out.append(int(num_str[-L:]))
    return out


def _extract_invoice_ints_from_text(text: str, candidate_ints: Set[int], candidate_regex: str) -> List[int]:
    text_norm = _normalize_text(text)
    if not text_norm:
        return []

    patterns = [
        r"(?is)(?:invoice\s*(?:no\.?|number|id)|inv\s*\.?\s*no\.?)\D{0,20}([0-9]{3,30})",
    ]

    labeled_digit_strings: List[str] = []
    for pat in patterns:
        labeled_digit_strings.extend(re.findall(pat, text_norm))

    hits: List[int] = []

    if labeled_digit_strings:
        for ds in labeled_digit_strings:
            for inv in _tails_of_3_to_6_digits(ds):
                if inv in candidate_ints:
                    hits.append(inv)
        if hits:
            return hits

    matches = re.findall(candidate_regex, text_norm)
    for m in matches:
        try:
            inv_int = int(m)
            if inv_int in candidate_ints:
                hits.append(inv_int)
        except Exception:
            continue

    return hits


def _choose_invoice_int_from_hits(hits: List[int]) -> int | None:
    if not hits:
        return None
    counts = Counter(hits)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def build_invoice_groups_from_pdf(file_path: str, invoice_ids: List[str]) -> List[InvoicePageGroup]:
    doc = fitz.open(file_path)
    page_count = doc.page_count
    if page_count <= 0:
        raise ValueError("Uploaded PDF is empty.")

    pad_len = 0  # No leading zeros as requested
    candidate_ints = sorted(set(int(x) for x in invoice_ids if x and x.isdigit() and int(x) > 0))
    if not candidate_ints:
        raise ValueError("No invoice candidates available.")

    candidate_ints_set = set(candidate_ints)
    candidate_regex = _build_candidate_regex(candidate_ints)

    if page_count % 3 == 0:
        chunk_count = page_count // 3
        groups: List[InvoicePageGroup] = []
        for chunk_index in range(chunk_count):
            start_page = chunk_index * 3
            texts = [doc.load_page(start_page + k).get_text("text") or "" for k in range(3)]

            matches_per_page = [_extract_invoice_ints_from_text(t, candidate_ints_set, candidate_regex) for t in texts]
            if not all(matches_per_page):
                raise ValueError(f"Invoice detection failed in chunk {chunk_index+1}")

            inter = set(matches_per_page[0]) & set(matches_per_page[1]) & set(matches_per_page[2])
            if not inter:
                raise ValueError(f"Invoice consistency failed in chunk {chunk_index+1}")

            chosen_int = sorted(inter, key=lambda inv: (-sum(lst.count(inv) for lst in matches_per_page), inv))[0]

            groups.append(InvoicePageGroup(
                invoice_int=chosen_int,
                invoice_raw=str(chosen_int),
                invoice_pad_len=pad_len,
                page_indices=[start_page, start_page + 1, start_page + 2],
            ))
        return groups

    # Flexible mode
    page_invoice_int: List[int | None] = []
    for page_index in range(page_count):
        text = doc.load_page(page_index).get_text("text") or ""
        hits = _extract_invoice_ints_from_text(text, candidate_ints_set, candidate_regex)
        chosen = _choose_invoice_int_from_hits(hits)
        page_invoice_int.append(chosen)

    # Forward and backward fill
    for i in range(1, page_count):
        if page_invoice_int[i] is None and page_invoice_int[i-1] is not None:
            page_invoice_int[i] = page_invoice_int[i-1]
    for i in range(page_count-2, -1, -1):
        if page_invoice_int[i] is None and page_invoice_int[i+1] is not None:
            page_invoice_int[i] = page_invoice_int[i+1]

    vals = [int(v) for v in page_invoice_int if v is not None]

    groups: List[InvoicePageGroup] = []
    start = 0
    current = vals[0]
    for i in range(1, page_count):
        if vals[i] != current:
            groups.append(InvoicePageGroup(
                invoice_int=current,
                invoice_raw=str(current),
                invoice_pad_len=pad_len,
                page_indices=list(range(start, i)),
            ))
            start = i
            current = vals[i]
    groups.append(InvoicePageGroup(
        invoice_int=current,
        invoice_raw=str(current),
        invoice_pad_len=pad_len,
        page_indices=list(range(start, page_count)),
    ))

    return groups


def validate_invoice_range(groups: List[InvoicePageGroup], from_int: int, to_int: int) -> Dict:
    available = {g.invoice_int for g in groups}
    if from_int not in available or to_int not in available:
        raise ValueError("Invoice range not found in uploaded PDF")

    expected = list(range(from_int, to_int + 1))
    by_int: Dict[int, List[InvoicePageGroup]] = defaultdict(list)
    for g in sorted(groups, key=lambda x: x.page_indices[0]):
        by_int[g.invoice_int].append(g)

    warnings: List[str] = []
    selected_groups: List[InvoicePageGroup] = []

    for inv in expected:
        chosen = sorted(by_int[inv], key=lambda x: x.page_indices[0])[0]
        if len(by_int[inv]) > 1:
            warnings.append(f"Invoice {inv} appears multiple times. Using earliest.")
        selected_groups.append(chosen)

    return {
        "selected_count": len(selected_groups),
        "from_invoice_int": from_int,
        "to_invoice_int": to_int,
        "pad_len": 0,
        "invoice_ids": [str(g.invoice_int) for g in selected_groups],
        "warnings": warnings,
        "groups": [
            {"invoice_int": g.invoice_int, "invoice_raw": str(g.invoice_int), "page_indices": g.page_indices}
            for g in selected_groups
        ]
    }
