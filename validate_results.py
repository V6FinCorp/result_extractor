
import os
import re
from main_processor import FinancialReport

def get_ground_truth(file_name):
    # Mapping of files to their ground truth values (from text_table)
    # This is a manual summary for quick testing based on what the user provided.
    truth = {
        "eicher.pdf": {"Sales": 6171.59, "Expenses": 4878.41, "PBT": 1779.01, "PAT": 1369.45, "EPS": 49.93},
        "pocl.pdf": {"Sales": 640.37, "Expenses": 595.27, "PBT": 46.20, "PAT": 33.87, "EPS": 11.50},
        "inoxwind.pdf": {"Sales": 1119.18, "Expenses": 993.07, "PBT": 169.40, "PAT": 120.62, "EPS": 0.70},
        "frontspring.pdf": {"Sales": 82.74, "Expenses": 61.82, "PBT": 21.08, "PAT": 15.71, "EPS": 39.64},
        "thangamayil.pdf": {"Sales": 1704.60, "Expenses": 1632.51, "PBT": 78.39, "PAT": 58.51, "EPS": 18.82}
    }
    return truth.get(file_name)

if __name__ == "__main__":
    docs = sorted([f for f in os.listdir("docs") if f.endswith(".pdf")])
    print(f"{'File':<20} | {'Metric':<10} | {'Extracted':>10} | {'Truth':>10} | {'Status'}")
    print("-" * 65)
    
    for d in docs:
        rep = FinancialReport(os.path.join("docs", d))
        rep.parse()
        truth = get_ground_truth(d)
        if not truth: continue
        
        for m in ["Sales", "Expenses", "PBT", "PAT", "EPS"]:
            ext = rep.results[m]
            tru = truth[m]
            diff = abs(ext - tru)
            status = "PASS" if diff < 5.0 else "FAIL" 
            print(f"{d:<20} | {m:<10} | {ext:>10,.2f} | {tru:>10,.2f} | {status}")
        print("-" * 65)
