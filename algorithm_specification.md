# Financial Data Extraction Algorithm Specification

This document defines the deterministic workflow for extracting quarterly financial results from PDF documents.

## 1. Document Classification
*   **Input**: PDF File.
*   **Task**: Identify document type.
*   **Categories**:
    *   **Type A: Text-Based Structured PDF**: Contains searchable text layers.
    *   **Type B: Scanned PDF**: Image-based; requires OCR (Optical Character Recognition).
*   **Execution**:
    *   If text extraction returns valid character density, proceed to **Type A Processing**.
    *   If text is null or low-density, invoke **OCR/Computer Vision** for **Type B Processing**.

## 2. Document Validation
*   **Task**: Verify if the document is a "Quarterly Result Announcement".
*   **Validation Keywords**:
    *   `Un-audited`, `Standalone financial results`, `Consolidated financial results`, `Quarter ended`, `Half year ended`.
*   **Action**: If keywords are absent, flag the document as "Irrelevant" and stop.

## 3. Data Priority & Scope Selection
*   **Task**: Determine the hierarchy of results to extract.
*   **Logic**:
    *   Search for **Consolidated** and **Standalone** results headers.
    *   **Priority Rule**: If `Consolidated` results are available, process **Consolidated ONLY**. 
    *   If `Consolidated` is absent, process **Standalone**.
    *   The goal is to extract a single high-priority data set per PDF.

## 4. Table Discovery & Continuity
*   **Task**: Locate the P&L (Profit & Loss) table section and handle split tables.
*   **Logic**:
    *   Identify the start of the results table using targeted headers identified in Step 3.
    *   **Multi-Page Handling**: If mandatory metrics (Sales, Expenses, PAT, EPS) are not found on the identification page, the parser must iterate through subsequent pages until the full primary table is exhausted.

## 5. Metric Extraction (Keyword Mapping)
*   **Target Data**: Current Quarter | YoY Quarter (Year-on-Year) | QoQ (Quarter-on-Quarter).
*   **Keyword Dictionary**:
    *   **Sales**: `Total Revenue from operations`, `Total Income from Operations`, `Total Income`.
    *   **Expenses**: `Total Expenses`.
    *   **Profit Before Tax (PBT)**: `Profit before tax`, `Profit/(Loss) before tax`, `Profit/(Loss) before & tax`.
    *   **Net Profit**: `Net profit after tax`, `Profit/(Loss) for the year`, `Profit(Loss) for the period`, `Profit/(loss) after tax for the period/year`, `Net Profit for the period`.
    *   **EPS (Earnings Per Share)**: `Earning per share`, `Basic & Diluted Earnings per share`, `Basic Earning per share`, `Earnings Per Share (EPS) (In Rs) ( not annualised)`, `Earnings Per Share (of ₹ 1 each) on net profit after tax in ₹ (a) Basic`.

## 6. Calculation Logic (Derived Metrics)
*   **Operating Profit**: `PBT + Finance Costs + Depreciation - Other Income` (or as standardly reported).
*   **OPM % (Operating Profit Margin)**: `(Operating Profit / Sales) * 100`.

## 7. Output Format
The resulting data must be consolidated into the following matrix:

| Metric                | Current Quarter (e.g. Sep 2025) | QoQ Quarter (e.g. Jun 2025)| YoY Quarter (e.g. Sep 2024)|
| :---                  | :---                            | :---                       | :---                       |
| **Sales**             | [Value]                         | [Value]                    | [Value]                    |
| **Expenses**          | [Value]                         | [Value]                    | [Value]                    |
| **Operating Profit**  | [Calculated]                    | [Calculated]               | [Calculated]               |
| **OPM %**             | [Calculated]                    | [Calculated]               | [Calculated]               |
| **Profit Before Tax** | [Value]                         | [Value]                    | [Value]                    |
| **Net Profit**        | [Value]                         | [Value]                    | [Value]                    |
| **EPS (₹)**           | [Value]                         | [Value]                    | [Value]                    |

---
**Standardization**: All monetary values (except EPS) must be neutralized to **Crores** based on the detected scale (Lakhs, Thousands, etc.).
