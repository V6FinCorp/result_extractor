
import pdfplumber
import camelot
import pandas as pd
import re
from pathlib import Path
import os
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def clean_val(val):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan", ""]: return None
    s = str(val).strip()
    
    # Split by | or multiple spaces to avoid merging multiple columns
    parts = re.split(r'\||\s{2,}', s)
    s = parts[0].strip() # Take the first part as current quarter
    
    # Clean the numeric string
    s = s.replace(',', '').replace('(', '-').replace(')', '').replace('Rs.', '').replace('₹', '')
    s = re.sub(r'[^\d.-]', '', s)
    try:
        if s and s != '.' and s != '-':
            return float(s)
        return None
    except:
        return None

def extract_numbers(row):
    """Process a row and return a list of cleaned values."""
    results = []
    for cell in row:
        s = str(cell).strip()
        # Split merged cells from OCR/Camelot
        parts = re.split(r'\||\s{2,}', s)
        for p in parts:
            v = clean_val(p)
            if v is not None:
                results.append(v)
    return results

class FinalExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = str(pdf_path)
        self.company = Path(pdf_path).stem
        self.data = {
            "Company": self.company,
            "Sales": 0.0,
            "Expenses": 0.0,
            "OPM": 0.0,
            "OPM%": 0.0,
            "PBT": 0.0,
            "PAT": 0.0,
            "EPS": 0.0
        }
        self.other_inc = 0.0
        self.finance = 0.0
        self.depr = 0.0

    def run(self):
        target_pages = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").lower()
                if "particulars" in text and ("revenue from" in text or "total income" in text or "income from operations" in text):
                    if "independent auditor" not in text:
                        target_pages.append(i + 1)
        
        if not target_pages:
            return self.data

        # Sometimes P&L is split over 2 pages
        pg_str = ",".join(map(str, target_pages[:2]))
        tables = camelot.read_pdf(self.pdf_path, pages=pg_str, flavor="stream")
        
        for table in tables:
            df = table.df
            for _, row in df.iterrows():
                # Label is the concat of the first 2-3 columns that are not fully numeric
                label_candidates = [str(row.iloc[i]) for i in range(min(3, len(row)))]
                label = " ".join(label_candidates).lower().strip()
                
                nums = extract_numbers(row)
                if not nums: continue
                
                # Sanity check: if label is "S.No", the first num is the index
                val = nums[0]
                if len(nums) > 1 and label.startswith(str(int(val))) and val < 50:
                    val = nums[1]

                # Specific checks
                if "revenue" in label or "income from operation" in label or "net sales" in label:
                    if self.data["Sales"] == 0: self.data["Sales"] = val
                elif "other income" in label and "total" not in label:
                    self.other_inc = val
                elif "total expenses" in label or "total expenditure" in label:
                    if self.data["Expenses"] == 0: self.data["Expenses"] = val
                elif "depreciation" in label: self.depr = val
                elif ("finance cost" in label or "interest" in label) and "income" not in label:
                    self.finance = val
                elif "profit" in label and ("before tax" in label or "before exceptional" in label):
                    if self.data["PBT"] == 0: self.data["PBT"] = val
                elif ("net profit" in label or "profit for the period" in label) and "before" not in label:
                    if "after tax" in label or ("total" not in label and "comprehensive" not in label):
                        if self.data["PAT"] == 0: self.data["PAT"] = val
                elif ("eps" in label or "earnings per share" in label) and "basic" in label:
                    if self.data["EPS"] == 0: self.data["EPS"] = val

        # Post-process
        sales = self.data["Sales"] or 0.0
        pbt = self.data["PBT"] or 0.0
        op_profit = pbt + self.finance + self.depr - self.other_inc
        self.data["OPM"] = round(op_profit, 2)
        if sales != 0:
            self.data["OPM%"] = round((op_profit / sales * 100), 2)
        
        return self.data

def main():
    docs_dir = Path("docs")
    pdfs = list(docs_dir.glob("*.pdf"))
    results = []
    for pdf in pdfs:
        print(f"Processing {pdf.name}...")
        results.append(FinalExtractor(pdf).run())
        
    df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("FINANCIAL PERFORMANCE DASHBOARD (Current Quarter)")
    print("="*80)
    print(df.to_string(index=False))
    print("="*80)
    df.to_csv("performance_dashboard.csv", index=False)

if __name__ == "__main__":
    main()
