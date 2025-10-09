import sys
from pathlib import Path
import re
import pdfplumber

PDF_PATH = Path(r"c:\Users\lucia_csx8nlz\Downloads\Relat_1539 (13) (1).PDF")

if not PDF_PATH.exists():
    print(f"PDF not found: {PDF_PATH}")
    sys.exit(1)

DATE_PATTERNS = [
    re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"),
    re.compile(r"\b(\d{2}/\d{2}/\d{2})\b"),
    re.compile(r"\b(\d{2}-\d{2}-\d{4})\b"),
    re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b"),
    re.compile(r"\b(\d{2}\s*(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s*\d{2,4})\b", re.IGNORECASE),
]

with pdfplumber.open(str(PDF_PATH)) as pdf:
    print(f"Pages: {len(pdf.pages)}")
    for pi, page in enumerate(pdf.pages, start=1):
        print("\n=== PAGE", pi, "===")
        text = page.extract_text() or ''
        # Show first 15 lines
        lines = [l for l in text.splitlines() if l.strip()]
        for ln in lines[:15]:
            print("TXT:", ln)
        # Words for header hunting
        words = page.extract_words(x_tolerance=2, y_tolerance=2) or []
        prof_lines = []
        for w in words:
            t = w.get('text','')
            if re.search(r"Profissional|Especialidade|M[eé]dico|M[ée]dica", t, re.IGNORECASE):
                prof_lines.append((t, w.get('top'), w.get('x0')))
        if prof_lines:
            print("-- Header-ish words (Profissional/Especialidade):")
            for t, top, x0 in prof_lines[:20]:
                print(f"  {t!r} @ top={top:.1f} x0={x0:.1f}")
        # Dates in text
        found_dates = set()
        for pat in DATE_PATTERNS:
            for m in pat.finditer(text):
                found_dates.add(m.group(1))
        if found_dates:
            print("-- Dates detected in text:", sorted(found_dates)[:15])
        # Sample tables
        tables = page.extract_tables() or []
        print(f"Tables found: {len(tables)}")
        for ti, table in enumerate(tables[:1], start=1):
            print(f"Table {ti} rows: {len(table)} sample 3:")
            for row in table[:3]:
                print("  ROW:", [c.strip() if c else '' for c in row])
