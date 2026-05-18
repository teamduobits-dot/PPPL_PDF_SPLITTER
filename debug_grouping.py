import sys
from src.core.pdf_reader import analyze_pdf_candidates
from src.core.invoice_grouping import build_invoice_groups_from_pdf, validate_invoice_range

def main():
    if len(sys.argv) < 4:
        print("Usage: python debug_grouping.py <pdf_path> <from_int> <to_int>")
        return

    pdf_path = sys.argv[1]
    from_int = int(sys.argv[2])
    to_int = int(sys.argv[3])

    print("==== Phase 3 candidates ====")
    cand = analyze_pdf_candidates(pdf_path)
    print("page_count:", cand.page_count)
    print("candidate_count:", cand.candidate_count)
    print("min_invoice_int:", cand.min_invoice_int)
    print("max_invoice_int:", cand.max_invoice_int)
    print("invoice_ids (sample):", cand.invoice_ids[:30])

    print("\n==== Phase 4 grouping ====")
    groups = build_invoice_groups_from_pdf(pdf_path, invoice_ids=cand.invoice_ids)
    print("groups_count:", len(groups))

    print("\nFirst 10 groups:")
    for g in groups[:10]:
        print("invoice_int:", g.invoice_int, "invoice_raw:", g.invoice_raw, "pages:", g.page_indices)

    print("\n==== Phase 4 validate range ====")
    payload = validate_invoice_range(groups, from_int=from_int, to_int=to_int)
    print("Validation selected_count:", payload.get("selected_count"))
    print("pad_len:", payload.get("pad_len"))
    print("invoice_ids (selected):", payload.get("invoice_ids"))
    print("warnings:", payload.get("warnings"))

if __name__ == "__main__":
    main()
