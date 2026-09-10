"""Exports journal entries as clean PDFs -- something you could literally
hand to an auditor. A single entry gets its full support detail (reason,
references, preparer/reviewer, any system warnings raised at creation); a
batch export is a period listing/support schedule."""
from __future__ import annotations

import sqlite3
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import entries as entries_module

STYLES = getSampleStyleSheet()


def _p(text: str, style) -> Paragraph:
    """A Paragraph flowable parses its text as mini-XML, so free-text
    fields (description, reason, warnings -- anything a preparer typed)
    must be escaped first, or a stray '&'/'<' renders garbled instead of
    raising an error."""
    return Paragraph(escape(text), style)


def _entry_header_table(entry: sqlite3.Row, preparer_name: str, reviewer_name: str | None) -> Table:
    rows = [
        ["Entry #", str(entry["id"]), "Status", entry["status"].replace("_", " ").title()],
        ["Date", entry["entry_date"], "Type", entry["entry_type"].replace("_", " ").title()],
        ["Preparer", preparer_name, "Reviewer", reviewer_name or "(not yet reviewed)"],
        ["Reference", entry["supporting_reference"] or "-", "", ""],
    ]
    table = Table(rows, colWidths=[1.1 * inch, 2.4 * inch, 1.1 * inch, 2.4 * inch])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _lines_table(lines: list[sqlite3.Row]) -> Table:
    header = ["Account", "Debit", "Credit", "Memo"]
    rows = [header]
    total_debit = total_credit = 0.0
    for line in lines:
        debit = f"{line['amount']:,.2f}" if line["side"] == "debit" else ""
        credit = f"{line['amount']:,.2f}" if line["side"] == "credit" else ""
        if line["side"] == "debit":
            total_debit += line["amount"]
        else:
            total_credit += line["amount"]
        rows.append([f"{line['account_code']} - {line['account_name']}", debit, credit, line["memo"] or ""])
    rows.append(["Total", f"{total_debit:,.2f}", f"{total_credit:,.2f}", ""])

    table = Table(rows, colWidths=[2.6 * inch, 1.1 * inch, 1.1 * inch, 2.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
                ("ALIGN", (1, 0), (2, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#cccccc")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def export_entry_pdf(
    conn: sqlite3.Connection,
    entry_id: int,
    org_name: str,
    preparer_name: str,
    reviewer_name: str | None,
    outpath: str,
) -> None:
    entry = entries_module.get_entry(conn, entry_id)
    lines = entries_module.get_lines(conn, entry_id)

    doc = SimpleDocTemplate(outpath, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = [
        _p(f"{org_name} -- Journal Entry Support", STYLES["Title"]),
        Spacer(1, 0.15 * inch),
        _p(entry["description"], STYLES["Heading3"]),
        _entry_header_table(entry, preparer_name, reviewer_name),
        Spacer(1, 0.15 * inch),
        Paragraph("<b>Reason / Justification</b>", STYLES["Normal"]),
        _p(entry["reason"], STYLES["Normal"]),
        Spacer(1, 0.15 * inch),
        _lines_table(lines),
    ]

    if entry["creation_warnings"]:
        story += [
            Spacer(1, 0.15 * inch),
            Paragraph("<b>System warnings raised at creation</b>", STYLES["Normal"]),
            _p(entry["creation_warnings"], STYLES["Normal"]),
        ]
    if entry["review_note"]:
        story += [
            Spacer(1, 0.15 * inch),
            Paragraph("<b>Review note</b>", STYLES["Normal"]),
            _p(entry["review_note"], STYLES["Normal"]),
        ]

    doc.build(story)


def export_period_listing_pdf(
    conn: sqlite3.Connection,
    org_id: int,
    org_name: str,
    period_label: str,
    outpath: str,
    **filters,
) -> None:
    entry_rows = entries_module.list_entries(conn, org_id, **filters)

    doc = SimpleDocTemplate(outpath, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = [
        _p(f"{org_name} -- Journal Entry Listing", STYLES["Title"]),
        _p(period_label, STYLES["Heading3"]),
        Spacer(1, 0.15 * inch),
    ]

    header = ["Date", "Entry #", "Type", "Description", "Status", "Amount"]
    rows = [header]
    for entry in entry_rows:
        lines = entries_module.get_lines(conn, entry["id"])
        amount = sum(l["amount"] for l in lines if l["side"] == "debit")
        rows.append(
            [
                entry["entry_date"],
                str(entry["id"]),
                entry["entry_type"].replace("_", " ").title(),
                entry["description"],
                entry["status"].replace("_", " ").title(),
                f"{amount:,.2f}",
            ]
        )

    table = Table(rows, colWidths=[0.8 * inch, 0.5 * inch, 1.1 * inch, 2.6 * inch, 1.0 * inch, 0.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (5, 0), (5, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    story.append(table)
    doc.build(story)
