"""
Treasury AI — Reconciliation Engine
-----------------------------------
DETERMINISTIC matching logic. This is intentionally NOT AI:
treasury reconciliation must be auditable and reproducible.
The AI layer (see reasoning.py) only EXPLAINS and FLAGS results
produced here — it never decides the math.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import date


# ---------- Domain models ------------------------------------------------
@dataclass
class Invoice:
    id: str
    vendor: str
    amount: float
    currency: str
    reference: str          # PO / payment reference, "" if missing
    date: str               # ISO date string


@dataclass
class BankTxn:
    id: str
    description: str
    amount: float
    currency: str
    reference: str
    date: str


@dataclass
class ReconResult:
    invoice_id: str
    txn_id: Optional[str]
    status: str             # matched | partial | suspicious | unmatched
    confidence: float       # 0.0 - 1.0
    delta: float            # invoice.amount - txn.amount (invoice currency)
    match_basis: str        # reference | amount | none
    flags: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


# ---------- Config -------------------------------------------------------
# Variance below this fraction is treated as a tolerable FX / fee spread.
FX_TOLERANCE = 0.05


# ---------- Core engine --------------------------------------------------
def reconcile(invoices: list[Invoice], txns: list[BankTxn]) -> dict:
    """
    Match each invoice to at most one bank transaction.

    Matching strategy, in priority order:
      1. Exact reference match (strongest signal)
      2. Same-currency amount proximity within FX_TOLERANCE

    Returns a dict with `results` (one row per invoice) and
    `unmatched_txns` (bank movements with no invoice).
    """
    used: set[str] = set()
    results: list[ReconResult] = []

    for inv in invoices:
        txn, basis = _find_match(inv, txns, used)
        if txn:
            used.add(txn.id)

        result = _evaluate(inv, txn, basis, invoices)
        results.append(result)

    unmatched = [t for t in txns if t.id not in used]
    return {
        "results": [r.dict() for r in results],
        "unmatched_txns": [asdict(t) for t in unmatched],
        "summary": _summary(results, unmatched),
    }


def _find_match(inv: Invoice, txns: list[BankTxn],
                used: set[str]) -> tuple[Optional[BankTxn], str]:
    # 1. reference match
    for t in txns:
        if t.id in used:
            continue
        if inv.reference and t.reference and inv.reference == t.reference:
            return t, "reference"
    # 2. amount proximity, same currency
    for t in txns:
        if t.id in used or t.currency != inv.currency:
            continue
        if inv.amount and abs(t.amount - inv.amount) / inv.amount < FX_TOLERANCE:
            return t, "amount"
    return None, "none"


def _evaluate(inv: Invoice, txn: Optional[BankTxn], basis: str,
              all_invoices: list[Invoice]) -> ReconResult:
    flags: list[str] = []

    # duplicate invoice detection
    is_dup = any(
        o.id != inv.id and o.vendor == inv.vendor
        and abs(o.amount - inv.amount) < 0.01
        and o.reference == inv.reference
        for o in all_invoices
    )
    if is_dup:
        flags.append("duplicate_invoice")
    if not inv.reference:
        flags.append("missing_reference")

    if txn is None:
        return ReconResult(inv.id, None, "unmatched", 0.0, 0.0, "none", flags)

    delta = round(inv.amount - txn.amount, 2)
    pct = abs(delta) / inv.amount if inv.amount else 0.0

    if pct == 0:
        status, confidence = "matched", 0.99 if basis == "reference" else 0.92
    elif pct < FX_TOLERANCE:
        status, confidence = "partial", 0.74
        flags.append("fx_variance")
    else:
        status, confidence = "suspicious", 0.41
        flags.append("amount_mismatch")

    # downgrade on risk flags
    if "duplicate_invoice" in flags and status == "matched":
        status, confidence = "suspicious", 0.38
    if "missing_reference" in flags and status == "matched":
        status, confidence = "partial", 0.66

    return ReconResult(inv.id, txn.id, status, round(confidence, 2),
                       delta, basis, flags)


def _summary(results: list[ReconResult],
             unmatched: list[BankTxn]) -> dict:
    def count(s: str) -> int:
        return sum(1 for r in results if r.status == s)

    avg_conf = (sum(r.confidence for r in results) / len(results)
                if results else 0.0)
    # `needs_attention` aggregates everything a treasurer must review:
    # partial + suspicious invoices + bank txns with no invoice at all.
    return {
        "total_invoices": len(results),
        "matched": count("matched"),
        "partial": count("partial"),
        "suspicious": count("suspicious"),
        "unmatched": count("unmatched"),
        "unmatched_bank_txns": len(unmatched),
        "needs_attention": count("partial") + count("suspicious")
        + count("unmatched") + len(unmatched),
        "avg_confidence": round(avg_conf, 3),
    }
