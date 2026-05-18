import sys
from src.core.pdf_reader import analyze_pdf_candidates

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_extract.py <pdf_path>")
        return

    pdf_path = sys.argv[1]
    result = analyze_pdf_candidates(pdf_path)

    print("==== Phase 3 Debug Result ====")
    print("page_count:", result.page_count)
    print("candidate_count:", result.candidate_count)
    print("min_invoice_int:", result.min_invoice_int)
    print("max_invoice_int:", result.max_invoice_int)
    print("invoice_ids_sample:", result.invoice_ids[:20])
    print("================================")

if __name__ == "__main__":
    main()
