
import pandas as pd
import re
from pathlib import Path
import os
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def clean_value(val):
    if val is None or pd.isna(val) or str(val).lower() in ["none", "nan", ""]: return None
    s = str(val).replace(',', '').replace('(', '-').replace(')', '').strip()
    s = re.sub(r'[^\d.-]', '', s)
    try:
        if s and s != '.' and s != '-':
            return float(s)
        return None
    except:
        return None

def extract_first_number(row, start_col=1):
    """Find the first real number in a row after label column."""
    for i in range(start_col, len(row)):
        val = clean_value(row.iloc[i])
        if val is not None and val != 0:
            # Sanity check: avoid matching small integers if there are floats later
            # (Though in finance, floats are usually what we want)
            return val
    return None

def process_csv(csv_path):
    df = pd.read_csv(csv_path)
    company = Path(csv_path).stem.replace('_Results', '')
    
    data = {
        "Company": company,
        "Sales": None,
        "Expenses": None,
        "OtherInc": 0.0,
        "Depr": 0.0,
        "Finance": 0.0,
        "PBT": None,
        "PAT": None,
        "EPS": None
    }
    
    for idx, row in df.iterrows():
        # Combine first 2 columns for label
        label = (str(row.iloc[0]) + " " + str(row.iloc[1])).lower()
        val = extract_first_number(row, 2)
        if val is None: continue
        
        # Handle the shifted column problem: if label is "Revenue", val might be at index 2 or index 16
        # our extract_first_number handles this.

        if "revenue from operation" in label or "net sales" in label:
            if data["Sales"] is None: data["Sales"] = val
        elif "other income" in label and "total" not in label and len(label) < 40:
            data["OtherInc"] = val
        elif "total expenses" in label or "total expenditure" in label:
            if data["Expenses"] is None: data["Expenses"] = val
        elif "depreciation" in label:
            data["Depr"] = val
        elif ("finance cost" in label or "interest" in label) and "income" not in label:
            data["Finance"] = val
        elif "profit" in label and ("before tax" in label or "before exceptional" in label):
            if data["PBT"] is None: data["PBT"] = val
        elif ("net profit" in label or "profit for the period" in label) and "before" not in label:
            if "after tax" in label or ("total" not in label and "comprehensive" not in label):
                if data["PAT"] is None: data["PAT"] = val
        elif ("eps" in label or "earnings per share" in label) and "basic" in label:
             if data["EPS"] is None: data["EPS"] = val

    # OPM Calc
    sales = data["Sales"] or 0.0
    pbt = data["PBT"] or 0.0
    op_profit = pbt + data["Finance"] + data["Depr"] - data["OtherInc"]
    
    return {
        "Company": company,
        "Sales": sales,
        "Expenses": data["Expenses"] or 0.0,
        "OPM": round(op_profit, 2),
        "OPM%": round((op_profit / sales * 100), 2) if sales != 0 else 0.0,
        "PBT": pbt,
        "PAT": data["PAT"] or 0.0,
        "EPS": data["EPS"] or 0.0
    }

def main():
    outputs_dir = Path("outputs")
    csvs = list(outputs_dir.glob("*_Results.csv"))
    
    summary_data = []
    for csv in csvs:
        try:
            summary_data.append(process_csv(csv))
        except:
             continue
             
    final_df = pd.DataFrame(summary_data)
    cols = ["Company", "Sales", "Expenses", "OPM", "OPM%", "PBT", "PAT", "EPS"]
    final_df = final_df[cols]
    
    print("\n--- PERFORMANCE SUMMARY TABLE ---")
    print(final_df.to_string(index=False))
    final_df.to_csv("summary_performance.csv", index=False)

if __name__ == "__main__":
    main()
