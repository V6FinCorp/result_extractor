
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
        self.results = {
            "Sales": 0.0, "Expenses": 0.0, "PBT": 0.0, "PAT": 0.0, "EPS": 0.0, "OP": 0.0
        }
        self.found_priority = {k: 99 for k in self.results.keys()}
        self.helpers = {"Dep": 0.0, "Int": 0.0, "Other": 0.0, "TotalInc": 0.0}

    def get_rows(self, page):
        words = page.extract_words(x_tolerance=2, y_tolerance=2)
        if not words: return []
        rows = {}
        for w in words:
            y = round(w['top'], 0)
            found = False
            for ry in rows.keys():
                if abs(y - ry) < 5: rows[ry].append(w); found = True; break
            if not found: rows[y] = [w]
        
        res = []
        for y in sorted(rows.keys()):
            r_words = sorted(rows[y], key=lambda x: x['x0'])
            parts = []
            if r_words:
                c_txt, c_x0, c_x1 = r_words[0]['text'], r_words[0]['x0'], r_words[0]['x1']
                for i in range(1, len(r_words)):
                    w = r_words[i]
                    if (w['x0'] - c_x1) < 4: c_txt += w['text']; c_x1 = w['x1']
                    else: parts.append((c_txt, c_x0)); c_txt, c_x0, c_x1 = w['text'], w['x0'], w['x1']
                parts.append((c_txt, c_x0))
            res.append(parts)
        return res

    def parse_val(self, s):
        s = s.replace(',', '').replace('(', '-').replace(')', '').replace("'", '').strip()
        if not re.search(r'\d', s): return None
        if s.count('.') > 1:
            idx = s.rfind('.')
            s = s[:idx].replace('.', '') + s[idx:]
        try:
            m = re.search(r'-?\d+\.?\d*', s)
            return float(m.group()) if m else None
        except: return None

    def parse(self):
        with pdfplumber.open(self.path) as pdf:
            txt_all = "".join([p.extract_text() or "" for p in pdf.pages[:min(12, len(pdf.pages))]]).lower()
            self.target = "Consolidated" if "consolidated" in txt_all else "Standalone"
            
            # Global Scale Filter (prefer specific phrases)
            global_scale = 1.0
            if "crore" in txt_all: global_scale = 1.0
            elif any(x in txt_all for x in ["lakh", "lac", "lacs"]): global_scale = 100.0
            elif "million" in txt_all: global_scale = 10.0
            elif "thousand" in txt_all: global_scale = 1000.0

            mapping = {
                "Sales": [("revenuefromoperations", 1), ("incomefromoperations", 2), ("netsales", 3)],
                "TotalInc": [("totalincome", 1), ("totalrevenue", 1)],
                "Expenses": [("totalexpenses", 1), ("totalexpenditure", 2)],
                "PBT": [("profitbeforetax", 1), ("profitlossbeforetax", 2), ("pbt", 3), ("profitbeforeexceptional", 4)],
                "PAT": [("netprofit", 1), ("profitfortheperiod", 1), ("profitaftertax", 3), ("profitfortheyear", 1)],
                "EPS": [("basicearningspershare", 1), ("basiceps", 1), ("earningpershare", 2), ("basic", 3)],
                "Dep": [("depreciation", 1)], "Int": [("financecost", 1), ("interestcost", 1)], "Other": [("otherincome", 1)]
            }

            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                txt = text.lower()
                if "ended" not in txt and "particulars" not in txt: continue
                
                is_con = "consolidated" in txt
                prio = 1 if is_con else (2 if "standalone" in txt else 3)
                if self.target == "Consolidated" and prio == 2 and not is_con: continue

                # Page-specific scale
                page_scale = global_scale
                scale_area = re.search(r'in\s*(lakh|lac|crore|million|rs|rupee)', txt)
                if scale_area:
                    skw = scale_area.group(1)
                    if "crore" in skw: page_scale = 1.0
                    elif "million" in skw: page_scale = 10.0
                    elif "lakh" in skw or "lac" in skw: page_scale = 100.0

                rows = self.get_rows(page)
                anchor_x = None
                for r in rows[:20]:
                    for t, x in r:
                        tl = t.lower()
                        if ("30" in tl or "sep" in tl or "31" in tl or "mar" in tl) and "2025" in tl:
                            if "hy" not in tl and "year" not in tl:
                                anchor_x = x; break
                    if anchor_x: break
                
                for idx, r in enumerate(rows):
                    nums = []
                    for t, x in r:
                        v = self.parse_val(t)
                        if v is not None: nums.append((v, x))
                    
                    # Special for Thangamayil: if line looks like it contains numbers but they are merged incorrectly
                    # (Handled by get_rows merging already)

                    r_str = " ".join([p[0] for p in r])
                    match = re.search(r'-?\d', r_str)
                    lbl = normalize(r_str[:match.start()]) if match else normalize(r_str)
                    
                    target_key = None
                    for k, kws in mapping.items():
                        for kw, rk in kws:
                            if normalize(kw) in lbl:
                                if k == "Int" and "income" in lbl: continue
                                if k == "PAT" and any(x in lbl for x in ["comprehensive", "minority"]): continue
                                target_key = k; break
                        if target_key: break
                    
                    if target_key and nums:
                        clean = []
                        for i, (v, x) in enumerate(nums):
                            if i < 2 and abs(v) < 100 and v == int(v) and x < 300 and len(nums) > 2: continue
                            clean.append((v, x))
                        
                        if clean:
                            val = clean[0][0]
                            if anchor_x:
                                dlist = sorted([(abs(x-anchor_x), v) for v, x in clean])
                                if dlist[0][0] < 250: val = dlist[0][1]
                            
                            s_val = round(val / (1.0 if target_key == "EPS" else page_scale), 2)
                            
                            if target_key in ["Dep", "Int", "Other", "TotalInc"]:
                                if self.helpers[target_key] == 0: self.helpers[target_key] = s_val
                            else:
                                res_k = "PAT" if target_key == "PAT" else target_key
                                curr_prio = self.found_priority.get(res_k, 99)
                                if prio < curr_prio or (prio == curr_prio and self.results[res_k] == 0):
                                    self.results[res_k] = s_val
                                    self.found_priority[res_k] = prio
                                    if target_key == "EPS" and "basic" in lbl: self.found_priority[res_k] = 0

            # Fallback for Sales
            if self.results["Sales"] == 0 and self.helpers["TotalInc"] != 0:
                self.results["Sales"] = round(self.helpers["TotalInc"] - self.helpers["Other"], 2)
            
            # OP Calculation
            if self.results["Sales"] != 0:
                self.results["OP"] = round(self.results["PBT"] + self.helpers["Dep"] + self.helpers["Int"] - self.helpers["Other"], 2)
            
            return True

if __name__ == "__main__":
    import os
    for d in sorted([f for f in os.listdir("docs") if f.endswith(".pdf")]):
        rep = FinancialReport(os.path.join("docs", d))
        rep.parse()
        print(f"\n>>>> {rep.name}")
        for m in ["Sales", "Expenses", "PBT", "PAT", "EPS"]:
            print(f"{m:<10}: {rep.results[m]:>12,.2f}")
