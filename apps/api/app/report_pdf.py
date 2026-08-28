"""PDF export for immutable investigation report snapshots."""

from html import escape
from io import BytesIO
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


def _ascii(value: str) -> str:
    return value.replace("\u2014", "-").replace("\u2013", "-").replace("\u2018", "'").replace("\u2019", "'").replace("\u00b7", "|").replace("â€”", "-").replace("â€“", "-")


def render_report_pdf(report) -> bytes:
    """Render a stored report snapshot as a readable, paginated PDF."""
    output = BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=colors.HexColor("#123047"), alignment=TA_LEFT, spaceAfter=8)
    subtitle = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=15, textColor=colors.HexColor("#526b7a"), spaceAfter=5)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#0b5d7a"), spaceBefore=10, spaceAfter=5, keepWithNext=True)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.8, leading=12.2, textColor=colors.HexColor("#243744"), spaceAfter=3)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=12, firstLineIndent=-8, bulletIndent=0, spaceAfter=2)
    note = ParagraphStyle("Note", parent=body, fontSize=8, leading=11, textColor=colors.HexColor("#526b7a"), backColor=colors.HexColor("#eef5f8"), borderPadding=7, spaceBefore=6, spaceAfter=7)

    story = [
        Spacer(1, 28 * mm),
        Paragraph("CRYPTO FRAUD INTELLIGENCE", ParagraphStyle("Kicker", parent=subtitle, fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#0b7898"), tracking=1.2)),
        Spacer(1, 8 * mm),
        Paragraph(escape(_ascii(report.title)), title),
        Paragraph("Evidence-backed blockchain cybersecurity investigation report", ParagraphStyle("Lead", parent=subtitle, fontSize=13, leading=18, textColor=colors.HexColor("#123047"))),
        Spacer(1, 14 * mm),
        Paragraph(f"Report ID: {escape(report.report_id)}<br/>Case ID: {escape(report.case_id)}<br/>Generated: {escape(_ascii(report.created_at.isoformat()))}<br/>Classification: INVESTIGATIVE WORK PRODUCT", subtitle),
        Spacer(1, 10 * mm),
        Paragraph("This export is a point-in-time analytical snapshot. It distinguishes observed blockchain facts, source-backed intelligence, analytical inferences, and recommended actions.", note),
        Spacer(1, 45 * mm),
        Paragraph(f"Content integrity hash (SHA-256): {escape(report.content_hash)}", ParagraphStyle("Hash", parent=subtitle, fontName="Courier", fontSize=7.5, leading=10)),
        PageBreak(),
    ]

    for line in _ascii(report.content).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("="):
            continue
        if re.match(r"^\d+\.\s+.+$", stripped):
            story.append(Paragraph(escape(stripped), section))
        elif stripped.startswith("-") or stripped.startswith("*"):
            story.append(Paragraph("- " + escape(stripped[1:].strip()), bullet))
        else:
            story.append(Paragraph(escape(stripped), body))

    story.extend([
        Spacer(1, 8),
        Paragraph("Export notes", section),
        Paragraph("The PDF is generated from the persisted report content and its recorded SHA-256 hash. It does not silently refresh chain data at download time. Re-run the investigation when a new evidence snapshot is required.", note),
    ])

    def decorate(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#c8d9e1"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, height - 16 * mm, width - 18 * mm, height - 16 * mm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(colors.HexColor("#0b5d7a"))
        canvas.drawString(18 * mm, height - 12 * mm, "CRYPTO FRAUD INTELLIGENCE")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6b7f89"))
        canvas.drawRightString(width - 18 * mm, height - 12 * mm, "CONFIDENTIAL | INVESTIGATIVE WORK PRODUCT")
        canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
        canvas.drawString(18 * mm, 9 * mm, f"Report {report.report_id[:8]} | SHA-256 {report.content_hash[:12]}...")
        canvas.drawRightString(width - 18 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=23 * mm, bottomMargin=20 * mm, title=_ascii(report.title), author="Crypto Fraud Intelligence")
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()
