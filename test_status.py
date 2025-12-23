
import pandas as pd
import os
from main_processor import FinancialReport

if __name__ == "__main__":
    docs_dir = "docs"
    docs = sorted([f for f in os.listdir(docs_dir) if f.endswith(".pdf")])
    summary = []
    
    for d in docs:
        pdf_path = os.path.join(docs_dir, d)
        rep = FinancialReport(pdf_path)
        parsed = rep.parse()
        
        # Metrics
        s, ext, pbt, pat = rep.results["Sales"], rep.results["Expenses"], rep.results["PBT"], rep.results["PAT"]
        op = rep.results["OP"]
        opm = round((op / s * 100), 2) if s > 0 else 0.0
        
        # Status Logic
        if parsed and s > 0 and pbt != 0 and pat != 0:
            status = "Success"
        elif parsed and (s > 0 or pbt != 0 or pat != 0):
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
