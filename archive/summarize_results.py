
import pandas as pd
import re
from pathlib import Path
import os
import sys

# Force UTF-8 for prints to avoid charmap errors
sys.stdout.reconfigure(encoding='utf-8')

def clean_value(val):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan", ""]: return None
    s = str(val).replace(',', '').replace('(', '-').replace(')', '').strip()
    s = s.replace('Rs.', '').replace('₹', '')
    # Remove any alpha chars except for - and .
    s = re.sub(r'[a-zA-Z\s]', '', s)
    try:
        if s and s != '.' and s != '-':
            return float(s)
        return None
    except:
        return None

class FinancialSummarizer:
    def __init__(self, csv_path):
        self.df = pd.read_csv(csv_path)
        self.company = Path(csv_path).stem.split('_')[0]
        self.summary = {
            "Company": self.company,
            "Sales": None,
            "Expenses": None,
            "Other Income": 0.0,
            "Depreciation": 0.0,
            "Finance Cost": 0.0,
            "PBT": None,
            "PAT": None,
            "EPS": None
        }
        self.target_col_idx = -1
        self._find_target_column()

    def _find_target_column(self):
        """Find the column corresponding to the current quarter (preferably 2025)."""
        # Look for 2025 first
        for r_idx in range(min(15, len(self.df))):
            row = self.df.iloc[r_idx]
            for c_idx, val in enumerate(row):
                val_str = str(val).lower().replace(' ', '')
                if '30' in val_str and ('09' in val_str or 'sep' in val_str) and '2025' in val_str:
                    self.target_col_idx = c_idx
                    return
        
        # Fallback to 2024 if 2025 not found (old report)
        for r_idx in range(min(15, len(self.df))):
            row = self.df.iloc[r_idx]
            for c_idx, val in enumerate(row):
                val_str = str(val).lower().replace(' ', '')
                if '30' in val_str and ('09' in val_str or 'sep' in val_str) and '2024' in val_str:
                    self.target_col_idx = c_idx
                    return
        
        # Last fallback: search for 'Unaudited'
        for r_idx in range(min(12, len(self.df))):
            for c_idx, val in enumerate(self.df.iloc[r_idx]):
                if 'unaudited' in str(val).lower():
                    self.target_col_idx = c_idx
                    return

    def extract(self):
        if self.target_col_idx == -1: return self.summary
        target_col = self.df.columns[self.target_col_idx]
        
        for idx, row in self.df.iterrows():
            desc = " ".join([str(x) for x in row.iloc[:4] if pd.notna(x)]).lower()
            val = clean_value(row.iloc[self.target_col_idx])
            
            if val is None: continue
            
            # Anchor Keywords - Be picky
            if "revenue from operations" in desc or ("total income" in desc and "operations" in desc):
                if self.summary["Sales"] is None: 
                    self.summary["Sales"] = val
            elif "other income" in desc and "total" not in desc and len(desc) < 60:
                self.summary["Other Income"] = val
            elif "total expenses" in desc or "total expenditure" in desc:
                if self.summary["Expenses"] is None:
                    self.summary["Expenses"] = val
            elif "depreciation" in desc:
                self.summary["Depreciation"] = val
            elif ("finance cost" in desc or "interest" in desc) and "income" not in desc:
                self.summary["Finance Cost"] = val
            elif "profit" in desc and ("before tax" in desc or "before exceptional" in desc):
                if self.summary["PBT"] is None:
                    self.summary["PBT"] = val
            elif ("net profit" in desc or "profit for the period" in desc) and "before" not in desc:
                if "after tax" in desc or "total" not in desc:
                   if self.summary["PAT"] is None:
                       self.summary["PAT"] = val
            elif "eps" in desc or "earnings per share" in desc:
                if "basic" in desc and val < 500: # Sanity check for EPS
                    if self.summary["EPS"] is None:
                        self.summary["EPS"] = val

        # Final cleanup/calculations
        s = self.summary
        sales = s["Sales"] or 0.0
        pbt = s["PBT"] or 0.0
        fin = s["Finance Cost"] or 0.0
        dep = s["Depreciation"] or 0.0
        oth = s["Other Income"] or 0.0
        
        op_profit = pbt + fin + dep - oth
        s["OPM"] = round(op_profit, 2)
        if sales != 0:
            s["OPM%"] = round((op_profit / sales) * 100, 2)
        else:
            s["OPM%"] = 0.0
            
        return s

def main():
    outputs_dir = Path("outputs")
    results_csvs = list(outputs_dir.glob("*_Results.csv"))
    
    all_data = []
    for csv in results_csvs:
        summarizer = FinancialSummarizer(csv)
        all_data.append(summarizer.extract())
        
    summary_df = pd.DataFrame(all_data)
    cols = ["Company", "Sales", "Expenses", "OPM", "OPM%", "PBT", "PAT", "EPS"]
    summary_df = summary_df[[c for c in cols if c in summary_df.columns]]
    
    print("\n--- FINAL FINANCIAL DATA ---")
    print(summary_df.to_string(index=False))
    summary_df.to_csv("summary_metrics.csv", index=False)

if __name__ == "__main__":
    main()
