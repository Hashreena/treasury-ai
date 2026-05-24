"""
Treasury AI — PDF Audit Report
------------------------------
Renders a reconciliation audit report dict (from report.build_report)
into a professional, multi-section PDF document using reportlab.
"""
from __future__ import annotations
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)

# ---- brand palette ------------------------------------------------------
NAVY = colors.HexColor("#101a30")
BLUE = colors.HexColor("#3d7eff")
INK = colors.HexColor("#1c2433")
MUTE = colors.HexColor("#5e6c8c")
LINE = colors.HexColor("#d4dae6")
GREEN = colors.HexColor("#1f9d6b")
AMBER = colors.HexColor("#c98a1e")
ORANGE = colors.HexColor("#d4691f")
RED = colors.HexColor("#c93b48")

SEV = {"high": RED, "medium": ORANGE, "low": AMBER}
STATUS = {"matched": GREEN, "partial": AMBER,
          "suspicious": ORANGE, "unmatched": RED}


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("TitleBig", parent=s["Title"], fontSize=22,
                         textColor=colors.white, alignment=TA_CENTER,
                         spaceAfter=2, leading=26))
    s.add(ParagraphStyle("TitleSub", parent=s["Normal"], fontSize=10,
                         textColor=colors.HexColor("#aeb9d2"),
                         alignment=TA_CENTER))
    s.add(ParagraphStyle("Section", parent=s["Heading2"], fontSize=12.5,
                         textColor=BLUE, spaceBefore=16, spaceAfter=7,
                         leading=15))
    s.add(ParagraphStyle("Body", parent=s["Normal"], fontSize=9.5,
                         textColor=INK, leading=14, alignment=TA_LEFT))
    s.add(ParagraphStyle("Small", parent=s["Normal"], fontSize=8,
                         textColor=MUTE, leading=11))
    s.add(ParagraphStyle("Note", parent=s["Normal"], fontSize=8.5,
                         textColor=MUTE, leading=12, leftIndent=8))
    s.add(ParagraphStyle("Meta", parent=s["Normal"], fontSize=9,
                         textColor=colors.white, leading=14))
    return s


def build_pdf(rep: dict) -> bytes:
    """Render an audit report dict to PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title="Treasury AI Audit Report",
    )
    st = _styles()
    flow = []
    s = rep["summary"]

    # ---- header band ----
    head = Table(
        [[Paragraph("TREASURY AI", st["TitleBig"])],
         [Paragraph("Reconciliation &amp; Audit Report", st["TitleSub"])]],
        colWidths=[doc.width],
    )
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, 0), 16),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
    ]))
    flow.append(head)
    flow.append(Spacer(1, 4))

    # ---- metadata ----
    meta = Table([
        ["Report reference", rep.get("engine", "Treasury AI"),
         "Reporting period", rep.get("period", "n/a")],
        ["Generated (UTC)", rep.get("generated_at", ""),
         "Classification", "Internal — Audit Use"],
    ], colWidths=[doc.width * 0.20, doc.width * 0.30,
                  doc.width * 0.20, doc.width * 0.30])
    meta.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTE),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTE),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("TEXTCOLOR", (3, 0), (3, -1), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, LINE),
    ]))
    flow.append(meta)

    # ---- 1. executive summary ----
    flow.append(Paragraph("1.  Executive Summary", st["Section"]))
    flow.append(Paragraph(rep["executive_summary"], st["Body"]))

    # ---- 2. key metrics ----
    flow.append(Paragraph("2.  Key Metrics", st["Section"]))
    mrows = [
        ["Total invoices reviewed", str(s["total_invoices"]),
         "Items needing attention", str(s["needs_attention"])],
        ["Cleanly reconciled", str(s["matched"]),
         "High-risk alerts", str(s.get("high_risk_alerts", 0))],
        ["Partially matched", str(s.get("partial", 0)),
         "Total alerts raised", str(s.get("total_alerts", 0))],
        ["Suspicious / unmatched",
         f"{s.get('suspicious', 0)} / {s.get('unmatched', 0)}",
         "Average confidence",
         f"{s['avg_confidence'] * 100:.0f}%"],
    ]
    mt = Table(mrows, colWidths=[doc.width * 0.30, doc.width * 0.20,
                                 doc.width * 0.30, doc.width * 0.20])
    mt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTE),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTE),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("TEXTCOLOR", (3, 0), (3, -1), INK),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#f4f6fb"), colors.white]),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
    ]))
    flow.append(mt)

    # ---- 3. reconciliation detail ----
    flow.append(Paragraph("3.  Reconciliation Detail", st["Section"]))
    head_row = ["Invoice", "Status", "Variance", "Basis"]
    drows = [head_row]
    note_rows = []
    for r in rep["reconciliation_detail"]:
        drows.append([
            r["invoice_id"], r["status"].title(),
            f"{r['delta']:,.2f}", r.get("match_basis", "-"),
        ])
        note_rows.append(r.get("ai_note", ""))
    dt = Table(drows, colWidths=[doc.width * 0.22, doc.width * 0.22,
                                 doc.width * 0.28, doc.width * 0.28])
    dstyle = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ]
    for i, r in enumerate(rep["reconciliation_detail"], start=1):
        c = STATUS.get(r["status"], MUTE)
        dstyle.append(("TEXTCOLOR", (1, i), (1, i), c))
        dstyle.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
    dt.setStyle(TableStyle(dstyle))
    flow.append(dt)
    flow.append(Spacer(1, 4))
    for r, note in zip(rep["reconciliation_detail"], note_rows):
        flow.append(Paragraph(
            f"<b>{r['invoice_id']}</b> &nbsp; {note}", st["Note"]))

    # ---- 4. anomaly & risk log ----
    flow.append(Paragraph("4.  Anomaly &amp; Risk Log", st["Section"]))
    if rep["anomaly_log"]:
        for i, a in enumerate(rep["anomaly_log"], 1):
            sev = a["severity"].upper()
            col = SEV.get(a["severity"], MUTE)
            flow.append(Paragraph(
                f'<font color="#{col.hexval()[2:]}"><b>[{sev}]</b></font> '
                f'<b>{a["title"]}</b>', st["Body"]))
            flow.append(Paragraph(a["description"], st["Note"]))
            ents = ", ".join(a.get("entities", []))
            if ents:
                flow.append(Paragraph(f"Affected: {ents}", st["Small"]))
            flow.append(Spacer(1, 5))
    else:
        flow.append(Paragraph("No anomalies detected.", st["Body"]))

    # ---- 5. audit trail ----
    flow.append(Paragraph("5.  Audit Trail", st["Section"]))
    arows = [["Type", "Reference", "Amount", "Currency", "Date"]]
    for t in rep["audit_trail"]:
        arows.append([
            t["doc_type"], t["id"], f"{t['amount']:,.2f}",
            t["currency"], t["date"],
        ])
    at = Table(arows, colWidths=[doc.width * 0.18, doc.width * 0.22,
                                 doc.width * 0.22, doc.width * 0.16,
                                 doc.width * 0.22])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f6fb")]),
    ]))
    flow.append(at)

    # ---- 6. methodology ----
    flow.append(Paragraph("6.  Methodology &amp; Disclaimer", st["Section"]))
    flow.append(Paragraph(
        "Reconciliation matching is performed by a deterministic, "
        "auditable engine. Transaction matches are decided by exact "
        "reference and amount-proximity rules; artificial intelligence is "
        "used only to generate plain-language explanations and is not used "
        "to decide matches. This report is generated automatically and is "
        "intended to support, not replace, professional review by a "
        "qualified treasurer or auditor.", st["Note"]))

    flow.append(Spacer(1, 14))
    flow.append(HRFlowable(width="100%", color=LINE, thickness=0.5))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph(
        "Treasury AI — Autonomous Treasury &amp; Reconciliation for SMEs",
        st["Small"]))

    doc.build(flow)
    return buf.getvalue()
