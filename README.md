# Treasury AI — Backend

Autonomous treasury & reconciliation API for SMEs. Reads financial
documents, reconciles transactions across currencies, detects fraud,
explains discrepancies with AI, and generates audit-ready reports.

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive API docs, or hit
**http://127.0.0.1:8000/demo** to run the whole pipeline on built-in
sample data — no upload needed. Great for a live demo.

## Endpoints

| Method | Path        | Purpose                                        |
|--------|-------------|------------------------------------------------|
| GET    | `/`         | Health check                                   |
| POST   | `/extract`  | Upload a CSV/XLSX/PDF → structured records      |
| POST   | `/reconcile`| Match invoices against bank transactions        |
| POST   | `/fraud`    | Run fraud / risk detection                      |
| POST   | `/report`   | Full audit report (reconcile + fraud + AI)      |
| GET    | `/demo`     | Run the entire pipeline on sample data          |

## Architecture in one line

**Deterministic engine decides the match; the LLM only explains it.**
Reconciliation math (`reconciliation.py`) and fraud rules (`fraud.py`)
are plain, auditable code. The AI layer (`reasoning.py`) turns a
finished result into plain-English advice for the treasurer.

## Enabling real AI reasoning (Chutes AI)

By default the reasoning layer uses a deterministic template so the
demo works offline. To use a real LLM:

```bash
export CHUTES_API_KEY="your-key"
export CHUTES_API_URL="https://llm.chutes.ai/v1/chat/completions"
export CHUTES_MODEL="deepseek-ai/DeepSeek-V3-0324"
```

The call uses a standard OpenAI-compatible contract. If the provider's
shape differs, adjust `_explain_via_llm()` in `app/reasoning.py`.

## File extraction support

| Format        | Status                                    |
|---------------|-------------------------------------------|
| CSV / TSV     | Fully working                             |
| XLSX / XLS    | Fully working (openpyxl)                  |
| Digital PDF   | Working for PDFs with real text tables    |
| Scanned image | Stub — needs OCR (Tesseract / vision LLM) |

For the hackathon demo, prefer CSV/XLSX sample files. Expected column
headers (case-insensitive, flexible aliases): `id`, `vendor`/`supplier`,
`amount`, `currency`, `reference`/`ref`/`po`, `date`.

## Project layout

```
app/
  main.py            FastAPI app & endpoints
  reconciliation.py  Deterministic matching engine
  fraud.py           Rule-based fraud / risk detection
  reasoning.py       AI explanation layer (Chutes AI hook)
  extraction.py      Document parsing (CSV/XLSX/PDF)
  report.py          Audit report assembly
  sample_data.py     Built-in demo data
```
