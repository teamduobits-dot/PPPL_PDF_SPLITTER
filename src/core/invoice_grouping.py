import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set

import fitz  # PyMuPDF


@dataclass
class InvoicePageGroup:
    invoice_int: int
    invoice_raw: str          # padded, e.g. "00342"
    invoice_pad_len: int
    page_indices: List[int]  # variable length


def _normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("\\u00A0", " ")
    text = text.replace("\u00A0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_single_invoice_regex(invoice_int: int) -> str:
    # Prevent matching inside bigger digit tokens
    return rf"(?<!\d)(?:0*{invoice_int})(?!\d)"


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

    # Labeled extraction first
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

    # Fallback: candidate regex anywhere on the page (still constrained to candidates)
    matches = re.findall(candidate_regex, text_norm)
    for m in matches:
        try:
            inv_int = int(m)
        except Exception:
            continue
        if inv_int in candidate_ints:
            hits.append(inv_int)

    return hits


def _choose_invoice_int_from_hits(hits: List[int]) -> int | None:
    if not hits:
        return None
    counts = Counter(hits)
    # max count, tie-break smaller int
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def build_invoice_groups_from_pdf(file_path: str, invoice_ids: List[str]) -> List[InvoicePageGroup]:
    doc = fitz.open(file_path)
    page_count = doc.page_count
    if page_count <= 0:
        raise ValueError("Uploaded PDF is empty.")

    pad_len = 5  # keep consistent with Phase 3
    candidate_ints = sorted(set(int(x) for x in invoice_ids if x and x.isdigit() and int(x) > 0))
    if not candidate_ints:
        raise ValueError("No invoice candidates available to build page groups.")

    candidate_ints_set = set(candidate_ints)
    candidate_regex = _build_candidate_regex(candidate_ints)

    # ---------------- STRICT mode if divisible by 3 ----------------
    if page_count % 3 == 0:
        chunk_count = page_count // 3
        invoice_ints = candidate_ints

        # Positional lock only if counts match
        lock_by_position = (len(invoice_ints) == chunk_count)

        groups: List[InvoicePageGroup] = []
        for chunk_index in range(chunk_count):
            start_page = chunk_index * 3
            texts: List[str] = []
            for k in range(3):
                texts.append(doc.load_page(start_page + k).get_text("text") or "")

            chosen_int: int | None = None

            if lock_by_position:
                expected_inv = invoice_ints[chunk_index]
                exp_regex = _build_single_invoice_regex(expected_inv)

                def contains_expected(t: str) -> bool:
                    return re.search(exp_regex, _normalize_text(t)) is not None

                if contains_expected(texts[0]) and contains_expected(texts[1]) and contains_expected(texts[2]):
                    chosen_int = expected_inv

            if chosen_int is None:
                # Intersection strict check
                matches_per_page: List[List[int]] = []
                for k in range(3):
                    page_hits = _extract_invoice_ints_from_text(texts[k], candidate_ints_set, candidate_regex)
                    if not page_hits:
                        raise ValueError(
                            f"Invoice detection failed in 3-page chunk #{chunk_index+1} "
                            f"(pages {start_page+1}-{start_page+3})."
                        )
                    matches_per_page.append(page_hits)

                inter = set(matches_per_page[0]) & set(matches_per_page[1]) & set(matches_per_page[2])
                if not inter:
                    raise ValueError(
                        f"Invoice consistency failed in 3-page chunk #{chunk_index+1} "
                        f"(pages {start_page+1}-{start_page+3})."
                    )

                # choose by score across 3 pages
                def score(inv: int) -> int:
                    return sum(lst.count(inv) for lst in matches_per_page)

                chosen_int = sorted(inter, key=lambda inv: (-score(inv), inv))[0]

            groups.append(
                InvoicePageGroup(
                    invoice_int=chosen_int,
                    invoice_raw=f"{chosen_int:0{pad_len}d}",
                    invoice_pad_len=pad_len,
                    page_indices=[start_page, start_page + 1, start_page + 2],
                )
            )

        return groups

    # ---------------- FLEX mode for non-multiples of 3 ----------------
    page_invoice_int: List[int | None] = []
    for page_index in range(page_count):
        text = doc.load_page(page_index).get_text("text") or ""
        hits = _extract_invoice_ints_from_text(text, candidate_ints_set, candidate_regex)
        chosen = _choose_invoice_int_from_hits(hits)
        page_invoice_int.append(chosen)

    # forward fill
    for i in range(page_count):
        if page_invoice_int[i] is None and i > 0 and page_invoice_int[i - 1] is not None:
            page_invoice_int[i] = page_invoice_int[i - 1]
    # backward fill
    for i in range(page_count - 1, -1, -1):
        if page_invoice_int[i] is None and i + 1 < page_count and page_invoice_int[i + 1] is not None:
            page_invoice_int[i] = page_invoice_int[i + 1]

    if any(v is None for v in page_invoice_int):
        raise ValueError("Invoice detection failed on some pages in flexible mode.")

    # small smoothing: if one page differs but neighbors match, replace it
    vals = [int(v) for v in page_invoice_int]  # all not None now
    for i in range(1, page_count - 1):
        if vals[i] != vals[i - 1] and vals[i] != vals[i + 1] and vals[i - 1] == vals[i + 1]:
            vals[i] = vals[i - 1]

    # Build consecutive groups
    groups: List[InvoicePageGroup] = []
    start = 0
    current = vals[0]
    for i in range(1, page_count):
        if vals[i] != current:
            groups.append(
                InvoicePageGroup(
                    invoice_int=current,
                    invoice_raw=f"{current:0{pad_len}d}",
                    invoice_pad_len=pad_len,
                    page_indices=list(range(start, i)),
                )
            )
            start = i
            current = vals[i]

    groups.append(
        InvoicePageGroup(
            invoice_int=current,
            invoice_raw=f"{current:0{pad_len}d}",
            invoice_pad_len=pad_len,
            page_indices=list(range(start, page_count)),
        )
    )

    return groups


def validate_invoice_range(groups: List[InvoicePageGroup], from_int: int, to_int: int) -> Dict:
    if from_int > to_int:
        raise ValueError("Invalid invoice range selected")

    available: Set[int] = {g.invoice_int for g in groups}
    if from_int not in available or to_int not in available:
        raise ValueError("Invoice range not found in uploaded PDF")

    expected = list(range(from_int, to_int + 1))

    by_int: Dict[int, List[InvoicePageGroup]] = defaultdict(list)
    for g in sorted(groups, key=lambda x: x.page_indices[0]):
        by_int[g.invoice_int].append(g)

    warnings: List[str] = []
    selected_groups: List[InvoicePageGroup] = []

    for inv in expected:
        if inv not in by_int:
            raise ValueError("Invoice range not found in uploaded PDF")

        chosen = sorted(by_int[inv], key=lambda x: x.page_indices[0])[0]
        if len(by_int[inv]) > 1:
            warnings.append(f"Invoice {inv:06d} appears multiple times. Using earliest occurrence.")

        selected_groups.append(chosen)

    return {
        "selected_count": len(selected_groups),
        "from_invoice_int": from_int,
        "to_invoice_int": to_int,
        "pad_len": selected_groups[0].invoice_pad_len,
        "invoice_ids": [f"{g.invoice_int:0{selected_groups[0].invoice_pad_len}d}" for g in selected_groups],
        "warnings": warnings,
        "groups": [
            {"invoice_int": g.invoice_int, "invoice_raw": g.invoice_raw, "page_indices": g.page_indices}
            for g in selected_groups
        ]
    }
