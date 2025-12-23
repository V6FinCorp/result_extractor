
import pdfplumber
import re
from pathlib import Path

def normalize(s):
    return re.sub(r'[^a-zA-Z0-9]', '', str(s or "")).lower()

class FinancialReport:
    def __init__(self, pdf_path):
        self.path = pdf_path
        self.name = Path(pdf_path).name
        self.target = "Consolidated"
        self.scale = 1.0
        self.results = {
            "Sales": 0.0, "Expenses": 0.0, "PBT": 0.0, "PAT": 0.0, "EPS": 0.0, "OP": 0.0
        }

    def extract_numbers(self, line):
        line = re.sub(r'(\d)\s+([,.]\d)', r'\1\2', line)
        line = re.sub(r'(\d[,.])\s+(\d)', r'\1\2', line)
        line = re.sub(r'\((\d[\d,.]*)\)', r'-\1', line)
        nums = []
        for m in re.finditer(r'-?\d[\d,.]*', line):
            s = m.group().replace(',', '')
            if s.count('.') > 1:
                sp = s.split('.')
                s = "".join(sp[:-1]) + "." + sp[-1]
            try: nums.append(float(s))
            except: pass
        return nums

    def parse(self):
        with pdfplumber.open(self.path) as pdf:
            txt5 = "".join([(p.extract_text() or "") for p in pdf.pages[:min(10, len(pdf.pages))]]).lower()
            self.target = "Consolidated" if "consolidated" in txt5 else "Standalone"
            
            best_p = None; max_s = -1
            for i, page in enumerate(pdf.pages):
                txt = (page.extract_text() or "").lower()
                if "ended" not in txt: continue
                score = (10 if "particulars" in txt else 0) + (5 if "revenue" in txt else 0) + \
                        (5 if "expenses" in txt else 0) + (10 if self.target.lower() in txt else 0)
                if score > max_s: max_s = score; best_p = page
            
            if not best_p: return False
            p_txt = best_p.extract_text().lower()
            if "lakh" in p_txt or "lakh" in txt5: self.scale = 100.0
            elif "million" in p_txt or "million" in txt5: self.scale = 10.0
            elif "in rs" in p_txt or "in rs" in txt5: self.scale = 10000000.0
            
            rows = best_p.extract_table({"vertical_strategy": "text", "horizontal_strategy": "text"})
            if not rows: rows = [[l] for l in best_p.extract_text().split('\n')]
            
            mapping = {
                "Sales": ["totalrevenuefrom", "incomefromoperations", "netsales", "revenuefromoperations", "totalincome"],
                "Expenses": ["totalexpenses", "totalexpenditure"],
                "PBT": ["profitbeforetax", "profitlossbeforetax", "pbt", "profitbeforeexceptional"],
                "PAT": ["netprofit", "profitfortheperiod", "profitaftertax", "netprofitlossfortheperiod", "profitlossfortheperiod"],
                "EPS": ["basicearningspershare", "basiceps", "earningspershareof", "earningpershare", "basic", "eps"],
                "Dep": ["depreciation"], "Int": ["financecost", "interestcost"], "Other": ["otherincome"]
            }
            hlp = {"Dep": 0.0, "Int": 0.0, "Other": 0.0}

            for r in rows:
                if not r or not any(r): continue
                line = " ".join([str(c) if c else "" for c in r])
                nums = self.extract_numbers(line)
                if not nums: continue
                
                lbl = normalize(line[:re.search(r'-?\d', line).start()])
                for key, kws in mapping.items():
                    if any(normalize(kw) in lbl for kw in kws):
                        if key == "Int" and "income" in lbl: continue
                        if key == "PAT" and any(x in lbl for x in ["comprehensive", "minority", "attributable"]): continue
                        
                        # ADVANCED SKIPPER: Find the first significant number
                        val = 0.0
                        for n in nums:
                            # EPS can be small. Others should be larger or decimal.
                            if key == "EPS": val = n; break
                            if abs(n) > 50 or (n != int(n) and n != 0): val = n; break
                        
                        if val != 0:
                            scaled = round(val / (1.0 if key == "EPS" else self.scale), 2)
                            if key in hlp: hlp[key] = scaled
                            else:
                                if key == "EPS" and "basic" in lbl: self.results["EPS"] = scaled
                                elif self.results.get(key if key != "PAT" else "PAT", 0) == 0:
                                    self.results[key if key != "PAT" else "PAT"] = scaled

            if self.results["OP"] == 0:
                self.results["OP"] = round(self.results["PBT"] + hlp["Dep"] + hlp["Int"] - hlp["Other"], 2)
            return True

if __name__ == "__main__":
    import os
    docs = sorted([f for f in os.listdir("docs") if f.endswith(".pdf")])
    for d in docs:
        rep = FinancialReport(os.path.join("docs", d))
        if rep.parse():
            print(f"\n>>>> {rep.name} ({rep.target})")
            for m in ["Sales", "Expenses", "OP", "PBT", "PAT", "EPS"]:
                print(f"{m:<10}: {rep.results[m]:>12,.2f}")
