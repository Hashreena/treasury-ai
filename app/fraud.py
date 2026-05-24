"""
Treasury AI — Fraud & Risk Detection
------------------------------------
Rule-based anomaly scanning over invoices, bank transactions and
reconciliation results. Each finding has a severity and a plain
description. Like the reconciliation engine, this is deterministic
so that alerts are explainable and defensible in an audit.
"""
from __future__ import annotations
from collections import Counter


SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Amount above which a missing reference becomes a material concern.
LARGE_AMOUNT = 10_000.0


def detect(invoices: list, txns: list, recon_results: list[dict]) -> list[dict]:
    """
    Run all fraud/risk rules. `invoices` and `txns` are dataclass
    instances; `recon_results` is the list produced by reconcile().
    Returns a list of alert dicts sorted by severity.
    """
    alerts: list[dict] = []

    alerts += _duplicate_invoices(invoices)
    alerts += _unknown_merchant_outflows(txns, recon_results)
    alerts += _large_missing_reference(invoices)
    alerts += _amount_mismatches(recon_results, invoices, txns)
    alerts += _vendor_frequency(invoices)
    alerts += _abnormal_patterns(invoices, txns)

    order = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}
    alerts.sort(key=lambda a: order.get(a["severity"], 3))
    return alerts


def _duplicate_invoices(invoices: list) -> list[dict]:
    seen: dict[tuple, str] = {}
    out: list[dict] = []
    for inv in invoices:
        key = (inv.vendor, round(inv.amount, 2), inv.reference)
        if key in seen:
            out.append({
                "type": "duplicate_invoice",
                "severity": SEVERITY_HIGH,
                "title": "Duplicate invoice detected",
                "entities": [seen[key], inv.id],
                "description": (
                    f"{inv.id} is identical to {seen[key]} — same vendor "
                    f"({inv.vendor}), amount {inv.amount:,.2f} {inv.currency} "
                    f"and reference {inv.reference or 'N/A'}. Possible "
                    f"double-billing; hold payment pending vendor confirmation."
                ),
            })
        else:
            seen[key] = inv.id
    return out


def _unknown_merchant_outflows(txns: list, recon_results: list[dict]) -> list[dict]:
    matched_txn_ids = {r["txn_id"] for r in recon_results if r["txn_id"]}
    out: list[dict] = []
    for t in txns:
        if t.id in matched_txn_ids:
            continue
        desc = t.description.upper()
        if "UNKNOWN" in desc or "MERCHANT" in desc:
            out.append({
                "type": "unknown_merchant",
                "severity": SEVERITY_HIGH,
                "title": "Unrecognized merchant outflow",
                "entities": [t.id],
                "description": (
                    f"{t.id} — {t.amount:,.2f} {t.currency} to "
                    f"'{t.description}'. No matching invoice or purchase "
                    f"order. Verify against approved vendor list."
                ),
            })
    return out


def _large_missing_reference(invoices: list) -> list[dict]:
    out: list[dict] = []
    for inv in invoices:
        if not inv.reference and inv.amount >= LARGE_AMOUNT:
            out.append({
                "type": "missing_reference",
                "severity": SEVERITY_MEDIUM,
                "title": "Large payment missing reference",
                "entities": [inv.id],
                "description": (
                    f"{inv.id} ({inv.vendor}, {inv.amount:,.2f} "
                    f"{inv.currency}) has no payment reference. Large "
                    f"amount with a weak audit trail — request supporting "
                    f"documentation before release."
                ),
            })
    return out


def _amount_mismatches(recon_results: list[dict], invoices: list,
                       txns: list) -> list[dict]:
    inv_map = {i.id: i for i in invoices}
    out: list[dict] = []
    for r in recon_results:
        if "amount_mismatch" not in r["flags"]:
            continue
        inv = inv_map.get(r["invoice_id"])
        out.append({
            "type": "amount_mismatch",
            "severity": SEVERITY_HIGH,
            "title": "Material amount mismatch",
            "entities": [r["invoice_id"], r["txn_id"]],
            "description": (
                f"{r['invoice_id']} differs from bank transaction "
                f"{r['txn_id']} by {abs(r['delta']):,.2f} "
                f"{inv.currency if inv else ''}. Exceeds FX tolerance — "
                f"requires manual review."
            ),
        })
    return out


def _vendor_frequency(invoices: list) -> list[dict]:
    """Flag a vendor billing unusually often in the period."""
    counts = Counter(i.vendor for i in invoices)
    out: list[dict] = []
    for vendor, n in counts.items():
        if n >= 3:
            out.append({
                "type": "vendor_frequency",
                "severity": SEVERITY_LOW,
                "title": "High invoice frequency from one vendor",
                "entities": [vendor],
                "description": (
                    f"{vendor} submitted {n} invoices this period. "
                    f"Not necessarily fraud, but worth confirming the "
                    f"billing schedule is expected."
                ),
            })
    return out


def _abnormal_patterns(invoices: list, txns: list) -> list[dict]:
    """
    Statistical outlier detection over transaction amounts.

    Flags any invoice whose amount is far above the typical spend
    (more than 2x the average of the rest). This catches abnormal
    one-off charges that the other rules would miss.
    """
    out: list[dict] = []
    if len(invoices) < 3:
        return out

    amounts = [i.amount for i in invoices]
    for inv in invoices:
        others = [a for a in amounts if a is not inv.amount]
        if not others:
            continue
        avg_others = sum(others) / len(others)
        if avg_others > 0 and inv.amount > avg_others * 2.0:
            ratio = inv.amount / avg_others
            out.append({
                "type": "abnormal_amount",
                "severity": SEVERITY_MEDIUM,
                "title": "Abnormal transaction amount",
                "entities": [inv.id],
                "description": (
                    f"{inv.id} ({inv.vendor}) is {inv.amount:,.2f} "
                    f"{inv.currency} — about {ratio:.1f}x the average "
                    f"invoice in this batch. Unusually large; confirm "
                    f"the charge is expected."
                ),
            })

    # round-number outflows can indicate manual / suspicious entries
    for t in txns:
        if t.amount >= 5000 and t.amount % 1000 == 0:
            out.append({
                "type": "round_amount",
                "severity": SEVERITY_LOW,
                "title": "Large round-number payment",
                "entities": [t.id],
                "description": (
                    f"{t.id} is an exact round amount of "
                    f"{t.amount:,.0f} {t.currency}. Round-number "
                    f"transfers are worth a quick sanity check."
                ),
            })
    return out
