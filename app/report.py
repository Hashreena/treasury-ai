"""
Treasury AI — Audit Report Generation
-------------------------------------
Assembles a structured, audit-ready report from reconciliation
results, fraud alerts and AI commentary. Returns JSON; a PDF/CSV
exporter can render from the same structure.
"""
from __future__ import annotations
from datetime import datetime, timezone


def build_report(invoices: list, txns: list, recon: dict,
                 alerts: list[dict], explanations: dict[str, str]) -> dict:
    """
    Compose the full audit report payload.

    `recon`        -> output of reconciliation.reconcile()
    `alerts`       -> output of fraud.detect()
    `explanations` -> {invoice_id: ai_explanation_text}
    """
    summary = recon["summary"]
    high = sum(1 for a in alerts if a["severity"] == "high")

    return {
        "title": "Reconciliation Audit Report",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": "Treasury AI v1.0",
        "period": _period(invoices),
        "summary": {
            **summary,
            "high_risk_alerts": high,
            "total_alerts": len(alerts),
        },
        "executive_summary": _exec_summary(summary, alerts),
        "reconciliation_detail": [
            {**r, "ai_note": explanations.get(r["invoice_id"], "")}
            for r in recon["results"]
        ],
        "unmatched_transactions": recon["unmatched_txns"],
        "anomaly_log": alerts,
        "audit_trail": _trail(invoices, txns),
    }


def _period(invoices: list) -> str:
    dates = sorted(i.date for i in invoices if i.date)
    if not dates:
        return "n/a"
    return f"{dates[0]} to {dates[-1]}"


def _exec_summary(summary: dict, alerts: list[dict]) -> str:
    high = [a for a in alerts if a["severity"] == "high"]
    parts = [
        f"Of {summary['total_invoices']} invoices reviewed, "
        f"{summary['matched']} reconciled cleanly against bank records."
    ]
    if summary["needs_attention"]:
        parts.append(
            f"{summary['needs_attention']} item(s) require attention."
        )
    if high:
        titles = "; ".join(a["title"].lower() for a in high)
        parts.append(f"High-risk findings: {titles}.")
    parts.append(
        f"Average model confidence across all matches is "
        f"{summary['avg_confidence'] * 100:.0f}%."
    )
    return " ".join(parts)


def _trail(invoices: list, txns: list) -> list[dict]:
    """Immutable record of every document ingested."""
    trail = []
    for i in invoices:
        trail.append({"doc_type": "invoice", "id": i.id,
                       "amount": i.amount, "currency": i.currency,
                       "date": i.date})
    for t in txns:
        trail.append({"doc_type": "bank_txn", "id": t.id,
                       "amount": t.amount, "currency": t.currency,
                       "date": t.date})
    return trail
