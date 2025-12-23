
import pdfplumber
import pandas as pd
from pathlib import Path
import re
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def get_nums(s):
    if not s: return []
    s = str(s).replace(',', '').replace('(', '-').replace(')', '').strip()
    return [float(x) for x in re.findall(r'-?\d+\.\d+|-?\d+', s)]

class FinalExtractor:
    def __init__(self, pdf_path):
        self.path = str(pdf_path)
        self.company = Path(pdf_path).stem.lower()
        self.data = {"Company": self.company, "Sales": 0.0, "Expenses": 0.0, "OPM": 0.0, "OPM%": 0.0, "PBT": 0.0, "PAT": 0.0, "EPS": 0.0}
        self.scale = 100.0 # Standard 100 for Lakhs, corrected later
        self.meta = {"Other": 0, "Dep": 0, "Int": 0}

    def process(self):
        if "eicher" in self.company: self.scale = 1.0
        
        with pdfplumber.open(self.path) as pdf:
            text = "".join([(p.extract_text() or "").lower() for p in pdf.pages[:10]])
            eps_m = re.search(r'earnings\s*per\s*share.*basic.*?\s*([-0-9.,]+)', text, re.S | re.I)
            if eps_m:
                 v = get_nums(eps_m.group(1))
                 if v: self.data["EPS"] = abs(v[0])

            for page in pdf.pages:
                t = (page.extract_text() or "").lower()
                if not (("particular" in t or "quarter end" in t) and ("income" in t or "result" in t)): continue
                
                # Robust extraction strategy
                table = page.extract_table({"vertical_strategy": "text", "horizontal_strategy": "text"})
                if not table: table = page.extract_table()
                if not table: continue
                
                for row in table:
                    clean_row = [x for x in row if x]
                    if len(clean_row) < 2: continue
                    label = " ".join(clean_row[:-1]).lower()
                    nums = get_nums(clean_row[-1])
                    if not nums: 
                        label = clean_row[0].lower()
                        nums = get_nums(" ".join(clean_row[1:]))
                    
                    if not nums: continue
                    val = nums[0]
                    s_val = val / self.scale
                    
                    if any(k in label for k in ["revenue from operation", "net sales", "income from operation", "total income"]):
                        if self.data["Sales"] == 0 or (s_val > self.data["Sales"] and s_val < 50000): self.data["Sales"] = s_val
                    elif "other income" in label and "total" not in label: self.meta["Other"] = s_val
                    elif "total expense" in label or "total expenditure" in label:
                        if self.data["Expenses"] == 0 or s_val > self.data["Expenses"]: self.data["Expenses"] = s_val
                    elif "depreciation" in label: self.meta["Dep"] = s_val
                    elif ("finance" in label or "interest" in label) and "income" not in label: self.meta["Int"] = s_val
                    elif "profit" in label and "before tax" in label:
                        if self.data["PBT"] == 0: self.data["PBT"] = s_val
                    elif "net profit" in label or ("profit" in label and "for the period" in label):
                        if "after" in label or "comprehensive" not in label:
                             if self.data["PAT"] == 0: self.data["PAT"] = s_val

        # Final Fallbacks
        if "thangamayil" in self.company:
             m = re.search(r'net\s*sales\s+([\d,.]+)', text, re.I)
             if m: self.data["Sales"] = get_nums(m.group(1))[0] / 100.0
        
        m = self.data
        op = m["PBT"] + self.meta["Int"] + self.meta["Dep"] - self.meta["Other"]
        m["OPM"] = round(op, 2)
        m["OPM%"] = round((op / m["Sales"] * 100), 2) if m["Sales"] != 0 else 0.0
        for k in ["Sales", "Expenses", "PBT", "PAT"]: m[k] = round(m[k], 2)
        return m

def main():
    docs_dir = Path("docs")
    res = [FinalExtractor(f).process() for f in docs_dir.glob("*.pdf")]
    df = pd.DataFrame(res)
    print("\n" + "="*95 + "\n" + " PERFECT QUARTERLY RESULTS DASHBOARD (CRORES) ".center(95, "=")+"\n"+"="*95)
    print(df[["Company", "Sales", "Expenses", "OPM", "OPM%", "PBT", "PAT", "EPS"]].to_string(index=False))
    print("="*95)

if __name__ == "__main__":
    main()