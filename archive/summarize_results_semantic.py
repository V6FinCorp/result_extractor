
import pdfplumber
import re
from pathlib import Path
import os
import pandas as pd
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def get_numbers_from_line(line):
    # Match numbers like 6,071.19, (50.62), 14,941.99, -456.78
    # Improved regex to handle spaces within numbers if any, and leading -
    matches = re.findall(r'\(?[\d,.]+\)?', line)
    results = []
    for m in matches:
        # Check if it actually contains a digit
        if not any(c.isdigit() for c in m): continue
        clean = m.replace(',', '').replace('(', '-').replace(')', '').strip()
        # Remove trailing . or -
        clean = clean.strip('.')
        if not clean or clean == '-': continue
        try:
            results.append(float(clean))
        except:
            continue
    return results

class SemanticExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.company = Path(pdf_path).stem
        self.results = {
            "Company": self.company,
            "Sales": None,
            "Expenses": None,
            "PBT": None,
            "PAT": None,
            "EPS": None,
            "Finance": 0.0,
            "Depr": 0.0,
            "OtherInc": 0.0
        }

    def process(self):
        with pdfplumber.open(self.pdf_path) as pdf:
            pnl_page = -1
            # Search for the main results page
            for i, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").lower()
                if "particulars" in text and ("financial results" in text or "profit and loss" in text or "statement of income" in text):
                    # Exclude auditor reports
                    if not any(kw in text for kw in ["independent auditor", "review report", "we have reviewed"]):
                        pnl_page = i
                        break
            
            # If still not found, try a broader search for "Particulars" and dates
            if pnl_page == -1:
                for i, page in enumerate(pdf.pages):
                    text = (page.extract_text() or "").lower()
                    if "particulars" in text and ("2025" in text or "2024" in text):
                         pnl_page = i
                         break

            if pnl_page == -1:
                return self.results
            
            lines = pdf.pages[pnl_page].extract_text().split('\n')
            for line in lines:
                l_low = line.lower().strip()
                nums = get_numbers_from_line(line)
                if not nums: continue
                
                # We usually want the first number (current quarter)
                # But we should do a sanity check to avoid small indices or year numbers
                val = nums[0]
                # If first num is like 1, 2, 3 (index), try second
                if val < 20 and len(nums) > 1 and l_low.startswith(str(int(val))):
                    val = nums[1]

                # SALES
                if self.results["Sales"] is None:
                    if "revenue from operation" in l_low or "net sales" in l_low or "total income from operations" in l_low:
                        if "total" not in l_low or "total revenue" in l_low or "total income from operations" in l_low:
                            self.results["Sales"] = val
                
                # OTHER INCOME
                if "other income" in l_low and "total" not in l_low and len(l_low) < 50:
                    self.results["OtherInc"] = val
                
                # EXPENSES
                if self.results["Expenses"] is None:
                    if "total expenses" in l_low or "total expenditure" in l_low:
                        self.results["Expenses"] = val
                
                # DEPR / FINANCE
                if "depreciation" in l_low: self.results["Depr"] = val
                if ("finance cost" in l_low or "interest" in l_low) and "income" not in l_low:
                    self.results["Finance"] = val
                    
                # PBT
                if self.results["PBT"] is None:
                    if "profit" in l_low and ("before tax" in l_low or "before exceptional" in l_low):
                        self.results["PBT"] = val
                
                # PAT
                if self.results["PAT"] is None:
                    if ("net profit" in l_low or "profit for the period" in l_low) and "before" not in l_low:
                        if "after tax" in l_low or ("total" not in l_low and "comprehensive" not in l_low):
                           self.results["PAT"] = val
                
                # EPS
                if self.results["EPS"] is None:
                    if "eps" in l_low or "earnings per share" in l_low:
                        if "basic" in l_low and val < 1000:
                            self.results["EPS"] = val

        # Handle edge cases (e.g. Sales marked as Total Income)
        r = self.results
        if r["Sales"] is None and r["PBT"] is not None and r["Expenses"] is not None:
             r["Sales"] = r["PBT"] + r["Expenses"] - r["OtherInc"]

        # Calc OPM
        sales = r["Sales"] or 0.0
        pbt = r["PBT"] or 0.0
        op_profit = pbt + (r["Finance"] or 0.0) + (r["Depr"] or 0.0) - (r["OtherInc"] or 0.0)
        r["OPM"] = round(op_profit, 2)
        if sales != 0:
            r["OPM%"] = round((op_profit / sales) * 100, 2)
        else:
            r["OPM%"] = 0.0
            
        return r

def main():
    docs_dir = Path("docs")
    pdf_files = list(docs_dir.glob("*.pdf"))
    all_data = []
    for pdf in pdf_files:
        print(f"Extraction for {pdf.name}...")
        all_data.append(SemanticExtractor(pdf).process())
        
    df = pd.DataFrame(all_data)
    cols = ["Company", "Sales", "Expenses", "OPM", "OPM%", "PBT", "PAT", "EPS"]
    df = df[cols]
    
    print("\n" + "="*80)
    print("FINAL CONSOLIDATED FINANCIAL REPORT (Current Quarter)")
    print("="*80)
    print(df.to_string(index=False))
    print("="*80)
    df.to_csv("final_company_summary.csv", index=False)

if __name__ == "__main__":
    main()
