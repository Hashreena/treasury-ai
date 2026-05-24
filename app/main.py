"""
Treasury AI — FastAPI Backend
=============================
AI-powered autonomous treasury & reconciliation for SMEs.

Run:
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000 for the dashboard,
or http://127.0.0.1:8000/docs for interactive API docs.
"""
from __future__ import annotations
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pathlib import Path
from pydantic import BaseModel
from dataclasses import asdict
from datetime import datetime, timezone

from .reconciliation import Invoice, BankTxn, reconcile
from .fraud import detect
from .reasoning import (explain, _fallback, explain_structured,
                        copilot_answer)
from .report import build_report
from .report_pdf import build_pdf
from .extraction import extract_invoices, extract_bank_txns
from .sample_data import SAMPLE_INVOICES, SAMPLE_TXNS

app = FastAPI(title="Treasury AI", version="1.1.0",
              description="Autonomous treasury & reconciliation for SMEs")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceIn(BaseModel):
    id: str
    vendor: str
    amount: float
    currency: str = "USD"
    reference: str = ""
    date: str = ""


class BankTxnIn(BaseModel):
    id: str
    description: str = ""
    amount: float
    currency: str = "USD"
    reference: str = ""
    date: str = ""


class ReconcileIn(BaseModel):
    invoices: list[InvoiceIn]
    bank_txns: list[BankTxnIn]


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    question: str
    history: list[ChatTurn] = []


def _to_invoices(items) -> list[Invoice]:
    return [Invoice(**i.model_dump()) for i in items]


def _to_txns(items) -> list[BankTxn]:
    return [BankTxn(**t.model_dump()) for t in items]


def _run_pipeline(invoices, txns, use_ai: bool = True) -> dict:
    """Full reconcile -> fraud -> explain -> report pipeline.

    use_ai=False uses fast deterministic explanations (no network calls)
    so the dashboard loads instantly; live AI is fetched per-row later.
    """
    recon = reconcile(invoices, txns)
    alerts = detect(invoices, txns, recon["results"])

    inv_map = {i.id: asdict(i) for i in invoices}
    txn_map = {t.id: asdict(t) for t in txns}
    explanations = {}
    for r in recon["results"]:
        txn = txn_map.get(r["txn_id"]) if r["txn_id"] else None
        inv = inv_map[r["invoice_id"]]
        if use_ai:
            explanations[r["invoice_id"]] = explain(r, inv, txn)
        else:
            explanations[r["invoice_id"]] = _fallback(r, inv, txn)

    report = build_report(invoices, txns, recon, alerts, explanations)
    return {
        "reconciliation": recon,
        "explanations": explanations,
        "fraud_alerts": alerts,
        "report": report,
    }


@app.get("/")
def landing():
    """Serve the marketing landing page."""
    return FileResponse(Path(__file__).parent / "landing.html")


@app.get("/app")
def dashboard():
    """Serve the Treasury AI dashboard UI."""
    return FileResponse(Path(__file__).parent / "dashboard.html")


@app.get("/health")
def health():
    return {"service": "Treasury AI", "status": "ok", "version": "1.1.0"}


@app.post("/extract")
async def extract(doc_type: str = Form(...), file: UploadFile = File(...)):
    content = await file.read()
    try:
        if doc_type == "invoice":
            records = [asdict(x) for x in
                       extract_invoices(file.filename, content)]
        elif doc_type == "bank":
            records = [asdict(x) for x in
                       extract_bank_txns(file.filename, content)]
        else:
            raise HTTPException(400, "doc_type must be 'invoice' or 'bank'")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return {"doc_type": doc_type, "count": len(records), "records": records}


@app.post("/reconcile")
def reconcile_endpoint(payload: ReconcileIn):
    return reconcile(_to_invoices(payload.invoices),
                     _to_txns(payload.bank_txns))


@app.post("/fraud")
def fraud_endpoint(payload: ReconcileIn):
    invoices = _to_invoices(payload.invoices)
    txns = _to_txns(payload.bank_txns)
    recon = reconcile(invoices, txns)
    return {"alerts": detect(invoices, txns, recon["results"])}


@app.post("/report")
def report_endpoint(payload: ReconcileIn):
    return _run_pipeline(_to_invoices(payload.invoices),
                         _to_txns(payload.bank_txns))


@app.get("/demo")
def demo():
    """Pipeline on sample data — INSTANT (no AI calls up front)."""
    return _run_pipeline(SAMPLE_INVOICES, SAMPLE_TXNS, use_ai=False)


@app.get("/explain/{invoice_id}")
def explain_one(invoice_id: str):
    """Live AI explanation for a single invoice — one LLM call."""
    recon = reconcile(SAMPLE_INVOICES, SAMPLE_TXNS)
    inv_map = {i.id: asdict(i) for i in SAMPLE_INVOICES}
    txn_map = {t.id: asdict(t) for t in SAMPLE_TXNS}

    row = next((r for r in recon["results"]
                if r["invoice_id"] == invoice_id), None)
    if row is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")

    txn = txn_map.get(row["txn_id"]) if row["txn_id"] else None
    text = explain(row, inv_map[invoice_id], txn)
    return {"invoice_id": invoice_id, "explanation": text,
            "match_basis": row["match_basis"]}


# ---- Scan history (session-scoped, in memory) --------------------------
# Each analysis the user runs is saved here as a "scan". This persists
# while the server runs; restarting clears it. A production build would
# back this with a database.
_SCANS: list[dict] = []
_scan_counter = {"n": 0}


def _new_scan_id() -> str:
    _scan_counter["n"] += 1
    return f"SCAN-{_scan_counter['n']:04d}"


@app.post("/upload-reconcile")
async def upload_reconcile(invoices_file: UploadFile = File(...),
                           bank_file: UploadFile = File(...)):
    """
    Upload an invoices file and a bank-statement file, run the full
    pipeline, and save the result to scan history.
    """
    inv_bytes = await invoices_file.read()
    bank_bytes = await bank_file.read()
    try:
        invoices = extract_invoices(invoices_file.filename, inv_bytes)
        txns = extract_bank_txns(bank_file.filename, bank_bytes)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    if not invoices or not txns:
        raise HTTPException(422, "One or both files had no rows. "
                                 "Check the column headers.")

    result = _run_pipeline(invoices, txns, use_ai=False)
    scan_id = _new_scan_id()
    scan = {
        "scan_id": scan_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "invoices_filename": invoices_file.filename,
        "bank_filename": bank_file.filename,
        "_invoices": invoices,   # kept for later AI explanations
        "_txns": txns,
        "result": result,
    }
    _SCANS.insert(0, scan)       # newest first
    return {"scan_id": scan_id, **result}


@app.get("/scans")
def list_scans():
    """Return a summary of every scan run this session (newest first)."""
    out = []
    for s in _SCANS:
        summ = s["result"]["reconciliation"]["summary"]
        out.append({
            "scan_id": s["scan_id"],
            "created_at": s["created_at"],
            "invoices_filename": s["invoices_filename"],
            "bank_filename": s["bank_filename"],
            "total_invoices": summ["total_invoices"],
            "matched": summ["matched"],
            "needs_attention": summ["needs_attention"],
            "alerts": len(s["result"]["fraud_alerts"]),
        })
    return {"scans": out, "count": len(out)}


@app.get("/scans/{scan_id}")
def get_scan(scan_id: str):
    """Return the full result of one past scan."""
    scan = next((s for s in _SCANS if s["scan_id"] == scan_id), None)
    if scan is None:
        raise HTTPException(404, f"Scan {scan_id} not found")
    return {"scan_id": scan_id, **scan["result"]}


@app.get("/scans/{scan_id}/explain/{invoice_id}")
def explain_scan(scan_id: str, invoice_id: str):
    """Live AI explanation for one invoice within a saved scan."""
    scan = next((s for s in _SCANS if s["scan_id"] == scan_id), None)
    if scan is None:
        raise HTTPException(404, f"Scan {scan_id} not found")
    invoices, txns = scan["_invoices"], scan["_txns"]
    recon = reconcile(invoices, txns)
    inv_map = {i.id: asdict(i) for i in invoices}
    txn_map = {t.id: asdict(t) for t in txns}
    row = next((r for r in recon["results"]
                if r["invoice_id"] == invoice_id), None)
    if row is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    txn = txn_map.get(row["txn_id"]) if row["txn_id"] else None
    text = explain(row, inv_map[invoice_id], txn)
    return {"invoice_id": invoice_id, "explanation": text,
            "match_basis": row["match_basis"]}


@app.get("/scans/{scan_id}/explain-detail/{invoice_id}")
def explain_scan_detail(scan_id: str, invoice_id: str):
    """
    Structured AI explanation for one invoice — powers the Explain
    modal. Returns why_flagged, reasoning chain, risk, action and a
    confidence note.
    """
    scan = next((s for s in _SCANS if s["scan_id"] == scan_id), None)
    if scan is None:
        raise HTTPException(404, f"Scan {scan_id} not found")
    invoices, txns = scan["_invoices"], scan["_txns"]
    recon = reconcile(invoices, txns)
    inv_map = {i.id: asdict(i) for i in invoices}
    txn_map = {t.id: asdict(t) for t in txns}
    row = next((r for r in recon["results"]
                if r["invoice_id"] == invoice_id), None)
    if row is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    txn = txn_map.get(row["txn_id"]) if row["txn_id"] else None
    detail = explain_structured(row, inv_map[invoice_id], txn)
    return {
        "invoice_id": invoice_id,
        "status": row["status"],
        "confidence": row["confidence"],
        "delta": row["delta"],
        "match_basis": row["match_basis"],
        "txn_id": row["txn_id"],
        "detail": detail,
    }


def _scan_context(scan: dict) -> dict:
    """Build a compact data snapshot of a scan for the copilot."""
    result = scan["result"]
    recon = result["reconciliation"]
    expl = result.get("explanations", {})
    results = []
    for r in recon["results"]:
        results.append({
            "invoice_id": r["invoice_id"],
            "txn_id": r["txn_id"],
            "status": r["status"],
            "confidence": r["confidence"],
            "delta": r["delta"],
            "flags": r["flags"],
            "ai_note": expl.get(r["invoice_id"], ""),
        })
    alerts = [{"severity": a["severity"], "title": a["title"],
               "description": a["description"]}
              for a in result["fraud_alerts"]]
    return {
        "scan_id": scan["scan_id"],
        "summary": recon["summary"],
        "results": results,
        "alerts": alerts,
    }


@app.post("/scans/{scan_id}/chat")
def copilot_chat(scan_id: str, payload: ChatIn):
    """
    Scan-aware AI copilot. Answers questions about a specific scan
    using its actual data. Falls back to a deterministic answer if
    the LLM is unavailable.
    """
    scan = next((s for s in _SCANS if s["scan_id"] == scan_id), None)
    if scan is None:
        raise HTTPException(404, f"Scan {scan_id} not found")
    if not payload.question.strip():
        raise HTTPException(422, "Question is empty")

    ctx = _scan_context(scan)
    history = [{"role": t.role, "content": t.content}
               for t in payload.history]
    result = copilot_answer(payload.question, ctx, history)
    return {"scan_id": scan_id, **result}


def _format_report(rep: dict) -> str:
    """Render the audit report as a professional plain-text document."""
    s = rep["summary"]
    W = 72
    L = []

    def rule(ch="="):
        L.append(ch * W)

    def section(title):
        L.append("")
        rule("-")
        L.append(f"  {title}")
        rule("-")

    rule()
    L.append("  TREASURY AI".center(W))
    L.append("  RECONCILIATION & AUDIT REPORT".center(W))
    rule()
    L.append(f"  Report reference : {rep.get('engine', 'Treasury AI')}")
    L.append(f"  Generated (UTC)  : {rep['generated_at']}")
    L.append(f"  Reporting period : {rep['period']}")
    L.append(f"  Prepared by      : Treasury AI — Autonomous Reconciliation Engine")
    L.append(f"  Classification   : Internal — Audit Use")

    section("1.  EXECUTIVE SUMMARY")
    for line in _wrap(rep["executive_summary"], W - 4):
        L.append(f"  {line}")

    section("2.  KEY METRICS")
    L.append(f"  Total invoices reviewed ........ {s['total_invoices']}")
    L.append(f"  Cleanly reconciled ............. {s['matched']}")
    L.append(f"  Partially matched .............. {s.get('partial', 0)}")
    L.append(f"  Suspicious ..................... {s.get('suspicious', 0)}")
    L.append(f"  Unmatched ...................... {s.get('unmatched', 0)}")
    L.append(f"  Items needing attention ........ {s['needs_attention']}")
    L.append(f"  High-risk alerts ............... {s.get('high_risk_alerts', 0)}")
    L.append(f"  Total alerts raised ............ {s.get('total_alerts', 0)}")
    L.append(f"  Average match confidence ....... "
             f"{s['avg_confidence'] * 100:.0f}%")

    section("3.  RECONCILIATION DETAIL")
    L.append(f"  {'INVOICE':<12}{'STATUS':<14}{'VARIANCE':<14}{'BASIS':<12}")
    L.append("  " + "." * (W - 4))
    for r in rep["reconciliation_detail"]:
        L.append(f"  {r['invoice_id']:<12}{r['status']:<14}"
                 f"{r['delta']:<14,.2f}{r.get('match_basis', '-'):<12}")
        for line in _wrap("Note: " + r.get("ai_note", ""), W - 8):
            L.append(f"      {line}")
        L.append("")

    section("4.  ANOMALY & RISK LOG")
    if rep["anomaly_log"]:
        for i, a in enumerate(rep["anomaly_log"], 1):
            L.append(f"  {i}. [{a['severity'].upper()}]  {a['title']}")
            for line in _wrap(a["description"], W - 8):
                L.append(f"      {line}")
            ents = ", ".join(a.get("entities", []))
            if ents:
                L.append(f"      Affected: {ents}")
            L.append("")
    else:
        L.append("  No anomalies detected.")

    section("5.  AUDIT TRAIL")
    L.append(f"  {'TYPE':<12}{'REFERENCE':<14}{'AMOUNT':>16}  {'DATE':<12}")
    L.append("  " + "." * (W - 4))
    for t in rep["audit_trail"]:
        L.append(f"  {t['doc_type']:<12}{t['id']:<14}"
                 f"{t['amount']:>16,.2f}  {t['date']:<12}")

    section("6.  METHODOLOGY & DISCLAIMER")
    note = ("Reconciliation matching is performed by a deterministic, "
            "auditable engine. Transaction matches are decided by exact "
            "reference and amount-proximity rules; artificial intelligence "
            "is used only to generate plain-language explanations and is "
            "not used to decide matches. This report is generated "
            "automatically and is intended to support, not replace, "
            "professional review by a qualified treasurer or auditor.")
    for line in _wrap(note, W - 4):
        L.append(f"  {line}")

    L.append("")
    rule()
    L.append("  END OF REPORT".center(W))
    L.append("  Treasury AI — Autonomous Treasury & Reconciliation".center(W))
    rule()
    return "\n".join(L)


def _wrap(text: str, width: int) -> list[str]:
    """Simple greedy word-wrap."""
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]
    L.append("=" * 64)
    return "\n".join(L)


@app.get("/report-export")
def report_export(scan_id: str | None = None):
    """
    Download a professional audit report as a PDF.
    Pass ?scan_id=SCAN-0001 to export a specific scan; otherwise the
    most recent scan (or built-in sample data) is used.
    """
    if scan_id:
        scan = next((s for s in _SCANS if s["scan_id"] == scan_id), None)
        if scan is None:
            raise HTTPException(404, f"Scan {scan_id} not found")
        report = scan["result"]["report"]
    elif _SCANS:
        report = _SCANS[0]["result"]["report"]
    else:
        report = _run_pipeline(SAMPLE_INVOICES, SAMPLE_TXNS,
                               use_ai=False)["report"]
    pdf_bytes = build_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 "attachment; filename=treasury-ai-audit-report.pdf"},
    )
