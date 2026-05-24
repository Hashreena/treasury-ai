"""
Treasury AI — AI Reasoning Layer
--------------------------------
Turns a structured reconciliation result into a plain-English
explanation for the treasurer.

Design:
  * The LLM only EXPLAINS — it receives the already-computed result
    and articulates it. It does not re-decide the match.
  * If no API key is configured, a deterministic template fallback
    is used so the demo always works offline.

To go live: set CHUTES_API_KEY (and optionally CHUTES_API_URL /
CHUTES_MODEL) in the environment. The call shape below follows a
standard OpenAI-compatible /chat/completions contract; adjust the
parsing if the provider differs.
"""
from __future__ import annotations
import os
import json
import urllib.request
import urllib.error


CHUTES_API_URL = os.getenv("CHUTES_API_URL",
                           "https://llm.chutes.ai/v1/chat/completions")
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", "")
CHUTES_MODEL = os.getenv("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3-0324")

SYSTEM_PROMPT = (
    "You are a treasury reconciliation analyst for a small business. "
    "You are given one already-computed reconciliation result. "
    "Explain in 2-3 sentences, in plain English, what the result means "
    "and what action the treasurer should take. Do not recompute "
    "amounts. Be concise and practical."
)


def explain(result: dict, invoice: dict, txn: dict | None) -> str:
    """
    Return a human-readable explanation for one reconciliation result.
    Uses Chutes AI if configured, otherwise a deterministic fallback.
    """
    if CHUTES_API_KEY:
        try:
            return _explain_via_llm(result, invoice, txn)
        except Exception as exc:  # never break the demo on a network error
            return _fallback(result, invoice, txn) + f"  (offline: {exc})"
    return _fallback(result, invoice, txn)


def _explain_via_llm(result: dict, invoice: dict, txn: dict | None) -> str:
    user_content = (
        "Reconciliation result:\n"
        f"{json.dumps(result, indent=2)}\n\n"
        "Invoice:\n"
        f"{json.dumps(invoice, indent=2)}\n\n"
        "Bank transaction:\n"
        f"{json.dumps(txn, indent=2) if txn else 'none found'}"
    )
    payload = {
        "model": CHUTES_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 200,
    }
    req = urllib.request.Request(
        CHUTES_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHUTES_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def _fallback(result: dict, invoice: dict, txn: dict | None) -> str:
    """Deterministic explanation — no API needed."""
    status = result["status"]
    flags = result.get("flags", [])
    delta = abs(result.get("delta", 0.0))
    ccy = invoice["currency"]
    inv_id = invoice["id"]

    if "duplicate_invoice" in flags:
        return (
            f"Duplicate exposure: {inv_id} is identical to an earlier "
            f"invoice from {invoice['vendor']} (same amount and reference). "
            f"This is a common double-billing pattern — hold payment until "
            f"the vendor confirms."
        )
    if status == "matched":
        return (
            f"Clean match. {inv_id} ties to {txn['id']} on reference and "
            f"exact {ccy} amount. No action needed — safe to mark reconciled."
        )
    if status == "partial" and "missing_reference" in flags:
        return (
            f"Amount and currency align with {txn['id']}, but {inv_id} has "
            f"no payment reference. Likely the same payment — ask the vendor "
            f"to reissue with a reference so the audit trail is complete."
        )
    if status == "partial":
        return (
            f"Small variance of {delta:,.2f} {ccy} between {inv_id} and "
            f"{txn['id']}. Consistent with cross-border FX spread or bank "
            f"fees — within tolerance; flag for treasurer sign-off."
        )
    if status == "suspicious":
        where = (f"Bank transaction {txn['id']} differs materially."
                 if txn else "No corresponding bank movement found.")
        return (
            f"Significant mismatch of {delta:,.2f} {ccy}. {where} "
            f"Recommend manual review before releasing payment."
        )
    return (
        f"No bank transaction found for {inv_id}. Payment may be pending, "
        f"or the invoice was never paid. Verify with accounts payable."
    )


# ---------------------------------------------------------------------------
# Structured explanation — powers the AI Explain modal
# ---------------------------------------------------------------------------
STRUCT_SYSTEM = (
    "You are a treasury reconciliation analyst. You are given one "
    "already-computed reconciliation result. Return ONLY a JSON object "
    "(no markdown, no prose outside the JSON) with exactly these keys: "
    '"why_flagged" (1-2 sentences on why this status was assigned), '
    '"reasoning" (a list of 3-4 short strings, each one step of the '
    'reasoning chain), "risk" (1-2 sentences on the financial/fraud risk), '
    '"action" (1 sentence, the concrete recommended next step), '
    '"confidence_note" (1 sentence explaining the confidence score). '
    "Do not recompute amounts. Be concise and practical."
)


def explain_structured(result: dict, invoice: dict,
                        txn: dict | None) -> dict:
    """
    Return a structured explanation with five sections for the
    AI Explain modal. Uses Chutes AI when configured, otherwise a
    deterministic fallback. Always returns the same dict shape.
    """
    if CHUTES_API_KEY:
        try:
            return _structured_via_llm(result, invoice, txn)
        except Exception:
            data = _structured_fallback(result, invoice, txn)
            data["source"] = "offline"
            return data
    data = _structured_fallback(result, invoice, txn)
    data["source"] = "offline"
    return data


def _structured_via_llm(result: dict, invoice: dict,
                        txn: dict | None) -> dict:
    user = (
        "Reconciliation result:\n" + json.dumps(result, indent=2) +
        "\n\nInvoice:\n" + json.dumps(invoice, indent=2) +
        "\n\nBank transaction:\n" +
        (json.dumps(txn, indent=2) if txn else "none found")
    )
    payload = {
        "model": CHUTES_MODEL,
        "messages": [
            {"role": "system", "content": STRUCT_SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    req = urllib.request.Request(
        CHUTES_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHUTES_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw = data["choices"][0]["message"]["content"].strip()

    # the model may wrap JSON in ```json fences — strip them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw)

    # normalise: guarantee every field exists and has the right type
    out = _structured_fallback(result, invoice, txn)
    if isinstance(parsed.get("why_flagged"), str):
        out["why_flagged"] = parsed["why_flagged"]
    if isinstance(parsed.get("reasoning"), list):
        out["reasoning"] = [str(x) for x in parsed["reasoning"]][:5]
    if isinstance(parsed.get("risk"), str):
        out["risk"] = parsed["risk"]
    if isinstance(parsed.get("action"), str):
        out["action"] = parsed["action"]
    if isinstance(parsed.get("confidence_note"), str):
        out["confidence_note"] = parsed["confidence_note"]
    out["source"] = "chutes"
    return out


def _structured_fallback(result: dict, invoice: dict,
                         txn: dict | None) -> dict:
    """Deterministic structured explanation — no API needed."""
    status = result["status"]
    flags = result.get("flags", [])
    conf = result.get("confidence", 0.0)
    delta = abs(result.get("delta", 0.0))
    ccy = invoice["currency"]
    inv_id = invoice["id"]
    txn_id = txn["id"] if txn else None

    reasoning = ["Invoice and bank records were compared by the "
                 "deterministic matching engine."]
    if txn:
        reasoning.append(
            f"A candidate bank transaction ({txn_id}) was located by "
            f"{result.get('match_basis', 'amount')} matching.")
    else:
        reasoning.append("No bank transaction could be linked to this "
                          "invoice.")

    if "duplicate_invoice" in flags:
        why = (f"{inv_id} was flagged because it is identical to an "
               f"earlier invoice from {invoice['vendor']} — same amount "
               f"and reference.")
        reasoning.append("A second invoice with matching vendor, amount "
                          "and reference was detected in the batch.")
        reasoning.append("Duplicate billing is a common fraud and error "
                          "pattern, so confidence was reduced.")
        risk = ("High risk of paying the same bill twice. Duplicate "
                "invoices are a frequent source of financial loss.")
        action = ("Hold payment and contact the vendor to confirm before "
                  "releasing funds.")
    elif status == "matched":
        why = (f"{inv_id} was marked matched: the amount and reference "
               f"agree exactly with {txn_id}.")
        reasoning.append("Amount and currency agree exactly with the "
                         "bank record.")
        risk = "Low risk. The transaction is fully supported by bank data."
        action = "No action needed — safe to mark as reconciled."
    elif status == "partial" and "missing_reference" in flags:
        why = (f"{inv_id} was marked partial: amount and currency align "
               f"with {txn_id}, but the invoice has no payment reference.")
        reasoning.append("Amounts align, but no reference is present to "
                          "confirm the link.")
        risk = ("Moderate risk. The payment is likely correct but the "
                "audit trail is incomplete without a reference.")
        action = ("Ask the vendor to reissue the invoice with a purchase "
                  "order or payment reference.")
    elif status == "partial":
        why = (f"{inv_id} was marked partial: a small variance of "
               f"{delta:,.2f} {ccy} exists against {txn_id}.")
        reasoning.append(f"The {delta:,.2f} {ccy} variance is within the "
                         f"tolerance band for FX spread and bank fees.")
        risk = ("Low to moderate risk. Variance is consistent with normal "
                "cross-border fees rather than error or fraud.")
        action = "Flag for treasurer sign-off, then mark reconciled."
    elif status == "suspicious":
        why = (f"{inv_id} was marked suspicious due to a material "
               f"discrepancy" +
               (f" against {txn_id}." if txn else " with no bank match."))
        reasoning.append("The discrepancy exceeds the acceptable "
                          "tolerance band.")
        risk = ("High risk. A material mismatch can indicate error, "
                "fraud, or an unrecorded transaction.")
        action = "Escalate for manual review before any payment is made."
    else:  # unmatched
        why = (f"{inv_id} is unmatched: no bank transaction corresponds "
               f"to this invoice.")
        risk = ("Moderate risk. The invoice may be unpaid, or a payment "
                "may be missing from the records.")
        action = ("Verify with accounts payable whether this invoice has "
                  "been paid.")

    conf_pct = int(round(conf * 100))
    if conf >= 0.85:
        cnote = (f"Confidence is high ({conf_pct}%) — the match rests on "
                 f"strong, direct evidence.")
    elif conf >= 0.6:
        cnote = (f"Confidence is moderate ({conf_pct}%) — the match is "
                 f"plausible but has a gap such as a variance or missing "
                 f"reference.")
    else:
        cnote = (f"Confidence is low ({conf_pct}%) — the evidence is weak "
                 f"or contradicted by a risk flag.")

    return {
        "why_flagged": why,
        "reasoning": reasoning,
        "risk": risk,
        "action": action,
        "confidence_note": cnote,
        "source": "offline",
    }


# ---------------------------------------------------------------------------
# Copilot chat — scan-aware conversational assistant
# ---------------------------------------------------------------------------
COPILOT_SYSTEM = (
    "You are Treasury AI Copilot, a treasury reconciliation assistant. "
    "You are given a JSON snapshot of the user's current reconciliation "
    "scan: invoices, bank transactions, match results, and fraud alerts. "
    "Answer the user's question using ONLY this data. Be concise (2-4 "
    "sentences), practical, and specific — cite invoice IDs and amounts "
    "from the data when relevant. If the question cannot be answered from "
    "the scan, say so briefly and suggest what the user could check. "
    "Do not invent transactions that are not in the data."
)


def copilot_answer(question: str, scan_context: dict,
                   history: list | None = None) -> dict:
    """
    Answer a user question about the current scan.

    scan_context is a compact dict (summary, results, alerts).
    history is an optional list of prior {role, content} turns.
    Returns {"answer": str, "source": "chutes"|"offline"}.
    """
    if CHUTES_API_KEY:
        try:
            return {"answer": _copilot_via_llm(question, scan_context,
                                               history or []),
                    "source": "chutes"}
        except Exception as exc:
            return {"answer": _copilot_fallback(question, scan_context),
                    "source": "offline"}
    return {"answer": _copilot_fallback(question, scan_context),
            "source": "offline"}


def _copilot_via_llm(question: str, ctx: dict, history: list) -> str:
    messages = [{"role": "system", "content": COPILOT_SYSTEM},
                {"role": "system",
                 "content": "Current scan data:\n" + json.dumps(ctx)}]
    # include up to the last 6 turns of conversation for context
    for turn in history[-6:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": question})

    payload = {
        "model": CHUTES_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 320,
    }
    req = urllib.request.Request(
        CHUTES_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHUTES_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def _copilot_fallback(question: str, ctx: dict) -> str:
    """
    Deterministic copilot answer — no API. Handles common question
    shapes by looking up the scan data directly, so the copilot is
    still useful offline.
    """
    q = question.lower()
    summary = ctx.get("summary", {})
    results = ctx.get("results", [])
    alerts = ctx.get("alerts", [])

    # try to find a specific invoice ID mentioned in the question
    target = None
    for r in results:
        if r["invoice_id"].lower() in q:
            target = r
            break

    if target:
        st = target["status"]
        note = target.get("ai_note", "")
        return (f"{target['invoice_id']} is currently '{st}'. {note} "
                f"You can open its Explain panel for a full breakdown.")

    if any(w in q for w in ("risk", "fraud", "suspicious", "alert")):
        if not alerts:
            return "No risk alerts were raised on this scan."
        lines = "; ".join(f"{a['title']}" for a in alerts[:3])
        return (f"This scan raised {len(alerts)} alert(s): {lines}. "
                f"Open the Risk & Fraud tab for the full detail.")

    if any(w in q for w in ("summary", "overview", "how many",
                            "matched", "result")):
        return (f"This scan reviewed {summary.get('total_invoices', 0)} "
                f"invoices: {summary.get('matched', 0)} matched, "
                f"{summary.get('needs_attention', 0)} need attention. "
                f"Average confidence is "
                f"{int(summary.get('avg_confidence', 0) * 100)}%.")

    if any(w in q for w in ("unmatched", "unpaid", "missing")):
        un = [r["invoice_id"] for r in results
              if r["status"] == "unmatched"]
        if un:
            return (f"Unmatched invoices: {', '.join(un)}. These have no "
                    f"corresponding bank transaction — verify with "
                    f"accounts payable.")
        return "Every invoice in this scan was matched to a transaction."

    return ("I can answer questions about this scan — try asking about a "
            "specific invoice (e.g. 'Why is INV-1601 risky?'), the risk "
            "alerts, or the overall summary.")
