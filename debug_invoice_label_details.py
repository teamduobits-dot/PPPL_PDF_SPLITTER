import re
import sys
import fitz

def normalize_text(t: str) -> str:
    if not t:
        return ""
    t = t.replace("\u00A0", " ")
    t = t.replace("\\u00A0", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def candidate_ints_from_digit_string_last3to6(ds: str):
    if not ds or not ds.isdigit():
        return []
    out = []
    for L in range(3, 7):
        if len(ds) >= L:
            out.append(int(ds[-L:]))
    return sorted(set(out))

PATTERNS = [
    # same style as your current pdf_reader patterns
    r"(?is)(?:invoice\s*(?:no\.?|number|id))\D{0,20}([0-9]{3,60})",
    r"(?is)(?:inv\s*\.?\s*no\.?)\D{0,20}([0-9]{3,60})",
]

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_invoice_label_details.py <pdf_path>")
        return

    pdf_path = sys.argv[1]
    doc = fitz.open(pdf_path)
    print("PDF:", pdf_path)
    print("page_count:", doc.page_count)
    print("--------------------------------------------------")

    for page_index in range(doc.page_count):
        text = doc.load_page(page_index).get_text("text") or ""
        text_norm = normalize_text(text)

        matches = []
        for pat in PATTERNS:
            matches.extend(re.findall(pat, text_norm))

        if matches:
            print(f"[Page {page_index+1}] Invoice-like label matches:")
            for ds in matches:
                print("  digit_string:", ds)
                print("  last3to6 ints:", candidate_ints_from_digit_string_last3to6(ds))
        else:
            print(f"[Page {page_index+1}] No invoice label matches found by regex.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
