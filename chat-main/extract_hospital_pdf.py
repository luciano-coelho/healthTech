import pdfplumber
import pandas as pd
from pathlib import Path

# Quick extractor for hospital PDF remittance reports
# Usage: python extract_hospital_pdf.py "c:/path/file.pdf"

def normalize_text(s: str) -> str:
    return " ".join(str(s).split()) if s is not None else ""


def extract_tables(pdf_path: str, max_pages: int | None = None) -> pd.DataFrame:
    pdf_path = Path(pdf_path)
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for i, page in enumerate(pages, start=1):
            # Try tables first
            tables = page.extract_tables() or []
            for t_idx, table in enumerate(tables):
                for r_idx, row in enumerate(table):
                    rows.append({
                        "page": i,
                        "table": t_idx,
                        **{f"col_{c}": normalize_text(val) for c, val in enumerate(row)}
                    })
            # Also try extracting words to reconstruct rows heuristically
            words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
            for w in words:
                rows.append({
                    "page": i,
                    "table": "words",
                    "x0": w.get("x0"),
                    "top": w.get("top"),
                    "text": normalize_text(w.get("text")),
                })
    return pd.DataFrame(rows)


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_hospital_pdf.py <pdf_path>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    df = extract_tables(pdf_path)

    # Show a compact sample
    print("\n--- Tables (first 20 rows) ---")
    tables_df = df[df['table'] != 'words']
    print(tables_df.head(20).to_string(index=False))

    print("\n--- Words (first 40 rows) ---")
    words_df = df[df['table'] == 'words'].sort_values(["page", "top", "x0"]).head(40)
    print(words_df.to_string(index=False))

    # Save to CSV for offline inspection
    out_csv = Path(pdf_path).with_suffix('.extracted.csv')
    df.to_csv(out_csv, index=False, encoding='utf-8-sig')
    print(f"\nSaved full extraction to: {out_csv}")


if __name__ == "__main__":
    main()
