import pdfplumber
import camelot
import pandas as pd
from pathlib import Path
import re
from tabulate import tabulate
import sys

# Set encoding for Windows terminal
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# =========================
# CONFIG
# =========================

PDF_PATH = "inputs/hbl.pdf"   # change if needed

# =========================
# STEP 1: IDENTIFY TABLE TYPE & PAGES
# =========================

def find_result_pages(pdf_path):
    consolidated_pages = []
    standalone_pages = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").lower()
                if "consolidated" in text and ("financial results" in text or "quarter ended" in text):
                    consolidated_pages.append(idx + 1)
                elif "standalone" in text and ("financial results" in text or "quarter ended" in text):
                    standalone_pages.append(idx + 1)
    except:
        return [1], "Unknown"
    
    if consolidated_pages:
        return consolidated_pages, "Consolidated"
    elif standalone_pages:
        return standalone_pages, "Standalone"
    else:
        return [1, 2], "Unknown"

# =========================
# STEP 2: EXTRACT TABLES
# =========================

def extract_main_table(pdf_path, pages):
    if not pages: return None
    
    all_tables = []
    page_str = ",".join(map(str, pages))
    
    for flavor in ['lattice', 'stream']:
        try:
            tables = camelot.read_pdf(pdf_path, pages=page_str, flavor=flavor)
            for t in tables:
                df = t.df
                if df.shape[1] < 3: continue
                
                text_content = " ".join(df.astype(str).values.flatten()).lower()
                
                # Scoring logic
                score = 0
                if 'particulars' in text_content: score += 1000
                if 'revenue from operations' in text_content: score += 2000
                if 'total income' in text_content: score += 1500
                if 'profit for the period' in text_content: score += 1000
                if 'segment' in text_content: score -= 1500 # Penalize segment tables
                
                # Add numerical density
                num_cells = df.map(lambda x: 1 if re.search(r'\d', str(x)) else 0).sum().sum()
                score += num_cells
                
                if score > 0:
                    all_tables.append((df, score))
        except: continue
    
    if not all_tables: return None
    
    # Sort by score and pick the best
    all_tables.sort(key=lambda x: x[1], reverse=True)
    return all_tables[0][0]

# =========================
# STEP 3: CLEANING & MERGING
# =========================

def clean_cell(text):
    if not isinstance(text, str): return text
    # Keep newlines for now to help with splitting if needed, but clean extra spaces
    text = re.sub(r'[ \t]+', ' ', text).strip()
    # Remove non-ASCII characters
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text

def format_table(df):
    if df is None or df.empty: return df
    
    # 1. Find the "Particulars" row
    particulars_row_idx = -1
    for i in range(min(10, len(df))):
        row_str = " ".join(df.iloc[i].astype(str)).lower()
        if 'particulars' in row_str:
            particulars_row_idx = i
            break
    
    if particulars_row_idx == -1:
        df.columns = [clean_cell(str(c)).replace('\n', ' ') for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
    else:
        new_columns = []
        for col in range(df.shape[1]):
            parts = []
            for row in range(particulars_row_idx + 1):
                val = clean_cell(str(df.iloc[row, col])).replace('\n', ' ')
                if val and val.lower() != 'nan' and val not in parts:
                    parts.append(val)
            col_name = " ".join(parts).strip()
            if not col_name: col_name = f"Col_{col}"
            new_columns.append(col_name)
        
        df.columns = new_columns
        df = df.iloc[particulars_row_idx + 1:].reset_index(drop=True)
    
    # Clean all data cells
    df = df.map(lambda x: clean_cell(str(x)))
    
    # 3. Merge split rows
    new_rows = []
    current_text = ""
    
    for i in range(len(df)):
        row = df.iloc[i].tolist()
        particulars = str(row[0]).strip()
        data_cols = [str(x).strip() for x in row[1:]]
        # Check if row has data (numbers)
        has_data = any(re.search(r'\d', x) for x in data_cols if x and x.lower() != 'nan' and x != '-')
        
        if not has_data and particulars:
            current_text = f"{current_text} {particulars}".strip()
        else:
            if current_text:
                row[0] = f"{current_text} {particulars}".strip()
                current_text = ""
            new_rows.append(row)
            
    if current_text:
        new_rows.append([current_text] + [""] * (df.shape[1] - 1))
        
    df = pd.DataFrame(new_rows, columns=df.columns)
    
    # Final cleanup: replace newlines with spaces in all cells for CSV/Display
    df = df.map(lambda x: str(x).replace('\n', ' '))
    
    # Filter noise
    df = df[~(df.astype(str).apply(lambda row: all(not v or v == 'nan' or v == '-' or v == '.' for v in row), axis=1))]
    
    return df

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print(f"\n--- Processing: {Path(PDF_PATH).name} ---")
    pages, r_type = find_result_pages(PDF_PATH)
    raw_df = extract_main_table(PDF_PATH, pages)
    
    if raw_df is not None:
        df = format_table(raw_df)
        print(f"\n{r_type.upper()} FINANCIAL RESULTS\n")
        
        # Improve terminal display by wrapping text in the first column
        display_df = df.copy()
        if len(display_df.columns) > 0:
            # Wrap the first column to 50 chars for terminal display
            display_df.iloc[:, 0] = display_df.iloc[:, 0].apply(lambda x: '\n'.join(re.findall(r'.{1,50}(?:\s|$)', str(x))))
        
        print(tabulate(display_df, headers='keys', tablefmt='grid', showindex=False))
        
        output_name = Path(PDF_PATH).stem + "_results.csv"
        try:
            df.to_csv(output_name, index=False, encoding='utf-8-sig')
            print(f"\n[SUCCESS] Extracted table saved to: {output_name}")
        except:
            print("\nCould not save CSV.")
    else:
        print("\nNo financial table found.")