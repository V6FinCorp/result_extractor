import re
import pdfplumber
import pandas as pd
from pathlib import Path

# =========================
# CONFIG
# =========================

PDF_PATH = "docs/pocl.pdf" 

REQUIRED_ROW_PATTERNS = {
    "income": [r"total income", r"total.*revenue", r"revenue from operations", r"income from operations"],
    "expenses": [r"total expenses"],
    "net_profit": [r"net profit", r"profit.*for the period", r"profit.*after tax"],
    "comp_income": [r"comprehensive income", r"total comprehensive"],
    "eps": [r"earning.*per share", r"eps", r"basic"]
}

METRIC_PATTERNS = {
    "Sales": [r"revenue from operation", r"income from operation", r"net sales"], 
    "Expenses": [r"total expenses"],
    "Other Income": [r"other income"],
    "PBT": [r"profit.*before.*tax", r"loss.*before.*tax"],
    "Net Profit": [r"net profit", r"profit.*after.*tax", r"profit.*for the period", r"profit.*for the year"],
    "EPS": [r"earning.*per share", r"basic.*eps", r"eps.*basic", r"basic.*earning"], 
    "Finance Costs": [r"finance costs", r"finance exp"], 
    "Depreciation": [r"depreciation", r"amortization"], 
}

# =========================
# UTILITIES
# =========================

def clean_text(text):
    if not isinstance(text, str): return ""
    text = text.replace('\n', ' ')
    text = re.sub(r"^[0-9\(\)\.a-zA-Z]{1,3}\s+", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()

def parse_currency(value_str):
    if not value_str or pd.isna(value_str): return []
    v = str(value_str).strip()
    v = re.sub(r"(\d)\s+(?=[,\d])", r"\1", v)
    v = re.sub(r"(?<=,)\s+(\d)", r"\1", v)
    parts = v.split()
    results = []
    for p in parts:
        neg = False
        if "(" in p and ")" in p:
            neg = True
            p = p.replace("(", "").replace(")", "")
        p = p.replace(",", "")
        p = re.sub(r"[^0-9\.\-]", "", p)
        if not p or p in [".", "-", ".-"]: continue
        try:
            num = float(p)
            if num > 50000000 and float(num).is_integer(): continue 
            results.append(-num if neg else num)
        except: continue
    return results

def detect_unit_scale(page_text):
    t = page_text.lower()
    if re.search(r"in lakh", t) or re.search(r"rs\.* in lakh", t): return 100000.0
    if re.search(r"in crore", t) or re.search(r"rs\.* in crore", t): return 10000000.0
    return 1.0 

# =========================
# LOGIC
# =========================

def score_table(df, page_text):
    txt = " ".join(df.astype(str).values.flatten()).lower()
    matches = 0
    found = []
    for k, pats in REQUIRED_ROW_PATTERNS.items():
        if any(re.search(p, txt) for p in pats):
            matches += 1
            found.append(k)
    is_console = "consolidated" in page_text.lower()
    score = matches * 10
    if is_console: score += 30 
    if "particulars" in txt: score += 5
    if "liabilities" in txt: score -= 20
    return score, found, is_console

def find_target_table(pdf_path):
    candidates = []
    with pdfplumber.open(pdf_path) as pdf:
        chain = []
        for i in range(min(12, len(pdf.pages))):
            page = pdf.pages[i]
            tables = page.extract_tables() or []
            if not tables:
                tables = page.extract_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"}) or []
            
            raw_txt = page.extract_text() or ""
            sc_txt = clean_text(raw_txt)
            
            for t in tables:
                df = pd.DataFrame(t)
                if df.empty: continue
                score, keys, _ = score_table(df, sc_txt)
                
                start = "income" in keys or "expenses" in keys
                end = "net_profit" in keys or "eps" in keys
                
                if start and end: 
                    candidates.append((score, df, raw_txt))
                    chain = []
                elif start: chain = [(df, raw_txt)]
                elif end and chain:
                    chain.append((df, raw_txt))
                    m_df = pd.concat([x[0] for x in chain], ignore_index=True)
                    m_score, _, _ = score_table(m_df, chain[0][1])
                    candidates.append((m_score, m_df, chain[0][1]))
                    chain = []
                elif score > 10: candidates.append((score, df, raw_txt))

    if not candidates: return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates[0][0] < 30: return None, None
    return candidates[0][1], candidates[0][2]

def extract_row_value(df, patterns, is_net_profit=False):
    is_eps = any("eps" in p or "earning" in p for p in patterns)
    for idx, row in df.iterrows():
        cells = [str(x) if x is not None else "" for x in row.values]
        txt = " ".join([clean_text(c) for c in cells])
        
        hit_pat = None
        for p in patterns:
            if re.search(p, txt):
                if is_net_profit and "comprehensive" in txt and "net profit" not in p: continue
                if is_eps and ("capital" in txt or "reserve" in txt): continue
                hit_pat = p
                break
        
        if hit_pat:
            l_idx = -1
            for ci, cv in enumerate(cells):
                if re.search(hit_pat, clean_text(cv)):
                    l_idx = ci
                    break
            if l_idx == -1: l_idx = 0
            
            cands = []
            for i in range(l_idx, len(cells)):
                cands.extend(parse_currency(cells[i]))
            
            if cands and abs(cands[0]) <= 50 and float(cands[0]).is_integer():
                if len(cands) > 1: cands.pop(0)

            if not is_eps and not any(abs(c) >= 50 for c in cands):
                if idx + 1 < len(df):
                    for nc in df.iloc[idx+1].values:
                        cands.extend(parse_currency(nc))

            if is_eps: cands = [c for c in cands if abs(c) < 2000]
            if cands: return cands[0]
    return 0.0

def process_pdf(pdf_path):
    df, txt = find_target_table(pdf_path)
    if df is None: return "Error: Target financial table not found."
    
    sc = detect_unit_scale(txt)
    cr = sc / 10000000.0
    
    vals = {
        "Sales": extract_row_value(df, METRIC_PATTERNS["Sales"]),
        "Expenses": extract_row_value(df, METRIC_PATTERNS["Expenses"]),
        "Other": extract_row_value(df, METRIC_PATTERNS["Other Income"]),
        "PBT": extract_row_value(df, METRIC_PATTERNS["PBT"]),
        "Net": extract_row_value(df, METRIC_PATTERNS["Net Profit"], True),
        "EPS": extract_row_value(df, METRIC_PATTERNS["EPS"])
    }
    
    s_cr = vals["Sales"] * cr
    e_cr = vals["Expenses"] * cr
    o_cr = vals["Other"] * cr
    p_cr = vals["PBT"] * cr
    n_cr = vals["Net"] * cr
    eps = vals["EPS"]
    
    if s_cr > 0 and o_cr > s_cr: o_cr = 0.0 
    if eps > 1000: eps = 0.0
    
    op_cr = s_cr - e_cr if s_cr > 0 else 0.0
    opm = (op_cr / s_cr * 100) if s_cr > 0 else 0.0
        
    def f(v): return f"{v:.2f}"
    
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    title = "Financial Results"
    for l in lines:
        if "results" in l.lower() or "quarter ended" in l.lower():
            if 20 < len(l) < 200: title = l.title().strip(); break
            
    name = "Unknown Company"
    if lines:
        n = lines[0]
        if len(n) < 5 and len(lines) > 1: n = lines[1]
        for s in ["CIN", "Regd", "Website", "Email", "Ph."]:
            if s in n: n = n.split(s)[0]
            if s.upper() in n: n = n.split(s.upper())[0]
        name = n.strip(" :,-").title()
            
    return f"Company Name: {name}\nTitle: {title}\nSales  : {f(s_cr)}\nExpenses  : {f(e_cr)}\nOperating  Profit : {f(op_cr)}\nOPM % : {f(opm)}\nOther Income : {f(o_cr)}\nProfit before tax : {f(p_cr)}\nNet Profit  : {f(n_cr)}\nEPS : {f(eps)}"

if __name__ == "__main__":
    if Path(PDF_PATH).exists():
        print("\n--- EXTRACTING ---")
        print(process_pdf(PDF_PATH))
    else: print("File not found.")
