# Treasury AI

**Reconciliation that explains itself.**

An AI-powered autonomous treasury & reconciliation platform for SMEs.
Upload invoices and bank statements — Treasury AI matches payments
across currencies, detects fraud, explains every discrepancy with AI,
and generates a professional PDF audit report.

> Core principle: reconciliation matching is **deterministic, auditable
> code**. The AI only explains and advises — it never decides the
> numbers. An analyst, not a calculator.

---

## Features

- **Smart Document Upload** — CSV, Excel and digital PDF
- **AI Data Extraction** — invoice no., amount, currency, vendor, reference, date
- **Reconciliation Engine** — matched / partial / suspicious / unmatched
- **AI Reasoning** — structured Explain modal, powered by Chutes AI
- **AI Copilot** — scan-aware chat assistant, powered by Chutes AI
- **Fraud & Risk Detection** — duplicates, abnormal amounts, unknown vendors
- **Executive Dashboard** — KPIs, charts, confidence scores, alerts
- **Scan History** — every analysis kept for the session
- **Audit Report** — one-click professional PDF export

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI
- **Frontend:** single-file HTML / CSS / JavaScript (no framework)
- **AI:** Chutes AI (large language model) with deterministic fallback
- **Libraries:** uvicorn, openpyxl, pdfplumber, reportlab

---

## Setup — do this ONCE

### 1. Install Python
Install **Python 3.11 or newer** from https://python.org
On Windows, tick **"Add Python to PATH"** during installation.

Verify it:
```
python --version
```

### 2. Get the project
```
git clone https://github.com/Hashreena/treasury-ai.git
cd treasury-ai
```

### 3. Install dependencies
```
python -m pip install -r requirements.txt
```

---

## Running the app — EVERY time

Set the three environment variables, then start the server, **in the
same terminal window**.

### Windows (PowerShell)
```
$env:CHUTES_API_KEY = "<ask the team for the key>"
$env:CHUTES_API_URL = "https://llm.chutes.ai/v1/chat/completions"
$env:CHUTES_MODEL = "deepseek-ai/DeepSeek-V3.2-TEE"
python -m uvicorn app.main:app --reload
```

### Mac / Linux (Terminal)
```
export CHUTES_API_KEY="<ask the team for the key>"
export CHUTES_API_URL="https://llm.chutes.ai/v1/chat/completions"
export CHUTES_MODEL="deepseek-ai/DeepSeek-V3.2-TEE"
python -m uvicorn app.main:app --reload
```

Wait for `Application startup complete`, then open a browser at:
```
http://127.0.0.1:8000
```

Stop the server with `Ctrl + C`.

> **Note on the API key:** the key is NOT stored in this repository,
> for security. Without it the app still runs — the AI features use a
> built-in deterministic fallback instead of live AI.

---

## How to use it

1. The landing page opens — click **Start Analysis**
2. Upload an invoices file and a bank statement file
   (test files are in the `datasets/` folder)
3. Watch it process, then explore the results tabs:
   Overview, Reconciliation, Risk & Fraud, Audit Report
4. Click **Explain** on any transaction for AI reasoning
5. Use the **Copilot** (bottom-right) to ask questions about the scan
6. Download the **PDF audit report**
7. **Scan History** keeps every analysis run this session

---

## Test datasets

The `datasets/` folder has 7 ready-made scenarios. Each folder has an
`invoices.csv` and a `bank_statement.csv` — upload the pair.

| Folder | Scenario |
|--------|----------|
| 01_clean_books      | Mostly matched, calm baseline |
| 02_fraud_alert      | Duplicate + unknown merchant + missing reference |
| 03_fx_variances     | Currency-spread partial matches |
| 04_unpaid_invoices  | Invoices with no matching payment |
| 05_enterprise_batch | Large 10-invoice batch |
| 06_small_business   | Small and simple |
| 07_high_risk_audit  | Heaviest risk — best for a fraud demo |

---

## Project structure

```
treasury-ai/
  app/
    main.py             FastAPI server & all endpoints
    reconciliation.py   deterministic matching engine
    fraud.py            fraud & risk detection
    reasoning.py        AI layer (explain + copilot)
    extraction.py       CSV / Excel / PDF parsing
    report.py           audit report builder
    report_pdf.py       PDF generator
    sample_data.py      built-in sample data
    landing.html        landing page
    dashboard.html      the workspace UI
  datasets/             7 test datasets
  requirements.txt      Python dependencies
  README.md             this file
```

---

## Troubleshooting

**`ModuleNotFoundError`** — dependencies not installed. Run
`python -m pip install -r requirements.txt`

**`python` is not recognized** — Python is not on PATH. Reinstall
Python and tick "Add Python to PATH".

**AI features show "offline mode"** — the API key is not set, or was
set in a different terminal window than the one running the server.
Set all three variables, then start the server in the SAME window.

**Page won't load** — confirm the terminal says
`Application startup complete`, and visit `http://127.0.0.1:8000`.

---

## Notes & roadmap

- Scan history is **session-based** — it resets when the server
  restarts. Persistent storage and user accounts are the next
  milestone.
- Document extraction supports CSV, Excel and **digital** PDFs.
  OCR for scanned receipts and screenshots is on the roadmap.

---

*Built for Hackathon 2026.*
