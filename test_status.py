
import pdfplumber
import re
import pandas as pd
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
        self.found = {k: False for k in self.results.keys()}
        self.helpers = {"Dep": 0.0, "Int": 0.0, "Other": 0.0}

    def parse(self):
        try:
            with pdfplumber.open(self.path) as pdf:
                # 1. Mode Detection
                txt10 = "".join([(p.extract_text() or "") for p in pdf.pages[:min(10, len(pdf.pages))]]).lower()
                self.target = "Consolidated" if "consolidated" in txt10 else "Standalone"
                
                # 2. Find Best Page
                best_page = None
                max_score = -1
                for i, page in enumerate(pdf.pages):
                    txt = (page.extract_text() or "").lower()
                    if "quarter ended" not in txt and "particulars" not in txt: continue
                    score = (15 if self.target.lower() in txt else 0) + (10 if "particulars" in txt else 0) + (10 if "revenue" in txt or "income" in txt else 0)
                    if "standalone" in txt and self.target == "Consolidated": score -= 30
                    if score > max_score: max_score = score; best_page = page
                
                if not best_page: return False
                
                # 3. Scale Detection
                p_txt = (best_page.extract_text() or "").lower()
                if "lakh" in p_txt or "lakh" in txt10: self.scale = 100.0
                elif "million" in p_txt or "million" in txt10: self.scale = 10.0
                elif "in rs" in p_txt or "in rs" in txt10: self.scale = 10000000.0
                
                # 4. Process Words spatially
                words = best_page.extract_words()
                lines_dict = {}
                for w in words:
                    y = round(w['top'], 0)
                    found = False
                    for ly in lines_dict.keys():
                        if abs(y - ly) < 5: lines_dict[ly].append(w); found = True; break
                    if not found: lines_dict[y] = [w]
                
                mapping = {
                    "Sales": ["totalrevenuefrom", "incomefromoperations", "netsales", "revenuefromoperations", "totalincome"],
                    "Expenses": ["totalexpenses", "totalexpenditure"],
                    "PBT": ["profitbeforetax", "profitlossbeforetax", "pbt", "profitbeforeexceptional"],
                    "PAT": ["netprofit", "profitfortheperiod", "profitaftertax", "netprofitlossfortheperiod"],
                    "EPS": ["basicearningspershare", "basiceps", "earningpershare", "basic", "eps"],
                    "Dep": ["depreciation"], "Int": ["financecost", "interestcost"], "Other": ["otherincome"]
                }

                for y in sorted(lines_dict.keys()):
                    row_words = sorted(lines_dict[y], key=lambda x: x['x0'])
                    joined_parts = []
                    if row_words:
                        curr_p = row_words[0]['text']
                        curr_x1 = row_words[0]['x1']
                        for i in range(1, len(row_words)):
                            w = row_words[i]
                            if w['x0'] - curr_x1 < 4 or w['text'] in [',', '.']:
                                curr_p += w['text']
                                curr_x1 = w['x1']
                            else:
                                joined_parts.append(curr_p)
                                curr_p = w['text']
                                curr_x1 = w['x1']
                        joined_parts.append(curr_p)
                    
                    full_line = " ".join(joined_parts).lower()
                    line_norm = normalize(full_line)
                    
                    for key, kws in mapping.items():
                        if any(normalize(kw) in line_norm for kw in kws):
                            if key == "Int" and "income" in line_norm: continue
                            if key == "PAT" and any(x in line_norm for x in ["comprehensive", "minority", "attributable"]): continue
                            
                            nums = []
                            for p in joined_parts:
                                clean = p.replace(',', '').replace('(', '-').replace(')', '').replace(' ', '')
                                m = re.search(r'-?\d+\.?\d*', clean)
                                if m:
                                    try:
                                        n = float(m.group())
                                        if key != "EPS" and abs(n) < 100 and n == int(n): continue
                                        nums.append(n)
                                    except: pass
                            
                            if nums:
                                val = nums[0]
                                is_eps = (key == "EPS")
                                scaled = round(val / (1.0 if is_eps else self.scale), 2)
                                if key in ["Dep", "Int", "Other"]: self.helpers[key] = scaled
                                else:
                                    metric = "PAT" if key == "PAT" else key
                                    if key == "EPS" and "basic" in line_norm:
                                        self.results[metric] = scaled
                                        self.found[metric] = True
                                    elif not self.found[metric] or (scaled != 0 and self.results[metric] == 0):
                                        self.results[metric] = scaled
                                        self.found[metric] = (scaled != 0)

                if self.results["OP"] == 0:
                    self.results["OP"] = round(self.results["PBT"] + self.helpers["Dep"] + self.helpers["Int"] - self.helpers["Other"], 2)
                return True
        except:
            return False

if __name__ == "__main__":
    import os
    docs = sorted([f for f in os.listdir("docs") if f.endswith(".pdf")])
    summary = []
    for d in docs:
        rep = FinancialReport(os.path.join("docs", d))
        rep.parse()
        
        # Metrics
        s, ext, pbt, pat = rep.results["Sales"], rep.results["Expenses"], rep.results["PBT"], rep.results["PAT"]
        op = rep.results["OP"]
        opm = round((op / s * 100), 2) if s > 0 else 0.0
        
        # Status Logic
        if s > 0 and pbt != 0 and pat != 0:
            status = "Success"
        elif s > 0 or pbt != 0 or pat != 0:
            status = "Partial"
        else:
            status = "Failed"
            
        summary.append({
            "File": d,
            "Type": rep.target,
            "Sales": s,
            "Expenses": ext,
            "OPM%": f"{opm}%",
            "PBT": pbt,
            "PAT": pat,
            "EPS": rep.results["EPS"],
            "Status": status
        })
        
    df = pd.DataFrame(summary)
    print("\n=== LATEST EXTRACTION STATUS ===")
    print(df.to_string(index=False))
