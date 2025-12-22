# PDF Financial Results Table Extractor

## Overview
This script extracts complete financial results tables from PDF files. It automatically:
1. Identifies whether the PDF contains **Consolidated** or **Standalone** results
2. Extracts the complete table (even if split across multiple pages)
3. Displays the table in the console
4. Saves the table to a CSV file for easy viewing in Excel

## How It Works

### Step 1: Identify Table Type & Pages
The script scans all pages in the PDF to find:
- **Consolidated results** (preferred)
- **Standalone results** (if consolidated not found)

It looks for keywords like "consolidated", "standalone", "financial results", and "statement".

### Step 2: Extract Tables
Uses **Camelot** library with "lattice" flavor to extract tables from the identified pages.
Lattice mode works well for tables with clear borders/gridlines.

### Step 3: Merge Tables (if split across pages)
If the financial results table spans multiple pages, the script:
- Detects header row repetitions
- Merges all table segments into one complete table
- Removes duplicate headers

### Step 4: Clean the Table
- Replaces newlines with spaces
- Strips extra whitespace
- Removes empty rows
- Removes rows with all empty values

### Step 5: Display & Save
- Prints the complete table to console
- Saves to CSV file: `<pdf_name>_extracted_table.csv`

## Usage

1. **Set the PDF file**:
   ```python
   PDF_PATH = "your_file.pdf"
   ```

2. **Run the script**:
   ```bash
   python results.py
   ```

3. **View results**:
   - Console: See the complete table printed
   - CSV file: Open `<pdf_name>_extracted_table.csv` in Excel

## Output Example

```
============================================================
Found Consolidated Results on pages: [3, 4, 5]
============================================================

Extracted 3 table(s) from 3 page(s)

============================================================
COMPLETE CONSOLIDATED RESULTS TABLE
============================================================

<Complete table displayed here>

============================================================
Total rows: 78
Total columns: 11
============================================================

[SUCCESS] Table saved to: hbl_results_extracted_table.csv
          Open this file in Excel or any spreadsheet viewer for better formatting
```

## Requirements

```bash
pip install pdfplumber camelot-py pandas
```

Note: Camelot also requires Ghostscript to be installed on your system.

## Tested With

✓ HBL Engineering Limited - Consolidated Results (78 rows, 11 columns)
✓ INOX Wind Limited - Consolidated Results (103 rows, 8 columns)

## Features

- ✓ Automatically prefers consolidated over standalone results
- ✓ Handles tables split across multiple pages
- ✓ Removes duplicate headers from page continuations
- ✓ Cleans and normalizes table data
- ✓ Exports to CSV for easy viewing
- ✓ Shows complete table in console

## Notes

- The script uses Camelot's "lattice" flavor which works best for tables with clear borders
- If your PDF has tables without borders, you may need to switch to "stream" flavor
- The CSV file is saved in the same directory as the PDF
