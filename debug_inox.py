import pdfplumber
import pandas as pd
import re

PDF_PATH = "docs/inoxwind.pdf"

def clean_text(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()

REQUIRED_ROW_PATTERNS = {
    "income": [r"total income", r"income from operations", r"revenue from operations"],
    "expenses": [r"total expenses"],
    "net_profit": [r"net profit", r"profit.*for the period", r"profit.*after tax"],
    "comp_income": [r"comprehensive income", r"total comprehensive"],
    "eps": [r"earning.*per share", r"eps", r"basic"]
}

with pdfplumber.open(PDF_PATH) as pdf:
    # Check first 8 pages
    print(f"Checking {PDF_PATH}")
    for i in range(min(8, len(pdf.pages))):
        print(f"\n--- PAGE {i} ---")
        p = pdf.pages[i]
        text_content = clean_text(p.extract_text() or "")
        print(f"Header: {text_content[:200]}")
        
        tables = p.extract_tables()
        for idx, t in enumerate(tables):
            df = pd.DataFrame(t)
            full_text = " ".join(df.astype(str).values.flatten()).lower()
            
            matches = []
            for key, patterns in REQUIRED_ROW_PATTERNS.items():
                for pat in patterns:
                    if re.search(pat, full_text):
                        matches.append(key)
                        break
            
            print(f"Table {idx}: Found {len(matches)}/5 keys: {matches}")
            if len(matches) < 5:
                # Print missing
                missing = set(REQUIRED_ROW_PATTERNS.keys()) - set(matches)
                print(f"Missing: {missing}")
                # Print a bit of content to see why
                print("Partial content:", full_text[:300])
