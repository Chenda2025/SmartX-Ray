"""
PDF report generator — Pro tier only.

Produces a multi-page diagnostic PDF containing:
  - Patient & date header
  - AI result summary (prediction + confidence bar)
  - Original X-ray image
  - Grad-CAM heatmap image
  - Disclaimer footer
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── ReportLab imports ──────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm

# Brand colours
BRAND_BLUE  = colors.HexColor("#1A73E8")
BRAND_RED   = colors.HexColor("#D93025")
BRAND_GREY  = colors.HexColor("#5F6368")
PNEUMONIA_C = colors.HexColor("#D93025")
NORMAL_C    = colors.HexColor("#1E8E3E")


def generate_report(scan, user, output_dir: str) -> tuple[str, int]:
    """
    Build the PDF report for a single scan.

    Parameters
    ----------
    scan       : Scan ORM object
    user       : User ORM object
    output_dir : absolute path to static/reports/

    Returns
    -------
    (filename, file_size_bytes)
    """
    from flask import current_app

    filename = f"report_scan{scan.id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    story = []
    styles = _build_styles()

    # ── Header ─────────────────────────────────────────────────────────────
    story.append(Paragraph("SmartX-Ray", styles["brand"]))
    story.append(Paragraph("AI-Powered Pneumonia Detection Report", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BRAND_BLUE))
    story.append(Spacer(1, 0.4 * cm))

    # ── Patient & scan info table ───────────────────────────────────────────
    scan_date = scan.created_at.strftime("%d %B %Y, %H:%M UTC") if scan.created_at else "N/A"
    info_data = [
        ["Patient Name",   user.full_name,  "Scan Date",   scan_date],
        ["Patient Email",  user.email,       "Scan ID",     f"#{scan.id}"],
        ["Model Version",  scan.model_version or "v1.0",
         "Report Generated", datetime.now(timezone.utc).strftime("%d %B %Y")],
    ]
    info_table = Table(info_data, colWidths=[3.5*cm, 7*cm, 3.5*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME",    (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",    (2, 0), (2, -1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 0), (0, -1),  BRAND_GREY),
        ("TEXTCOLOR",   (2, 0), (2, -1),  BRAND_GREY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
        ("GRID",        (0, 0), (-1, -1), 0.25, colors.HexColor("#DADCE0")),
        ("PADDING",     (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.6 * cm))

    # ── AI Result ──────────────────────────────────────────────────────────
    result_color = PNEUMONIA_C if scan.prediction == "PNEUMONIA" else NORMAL_C
    story.append(Paragraph("Diagnosis Result", styles["section_heading"]))
    story.append(Spacer(1, 0.2 * cm))

    result_label = Paragraph(
        f'<font color="{result_color.hexval()}" size="22"><b>{scan.prediction}</b></font>',
        styles["center"],
    )
    confidence_pct = round(scan.confidence * 100, 2)
    confidence_label = Paragraph(
        f'Confidence: <b>{confidence_pct}%</b>',
        styles["center"],
    )
    story += [result_label, Spacer(1, 0.1*cm), confidence_label, Spacer(1, 0.15*cm)]

    # Confidence bar (drawn as a table)
    bar_width   = PAGE_W - 2 * MARGIN
    filled_w    = bar_width * (confidence_pct / 100)
    empty_w     = bar_width - filled_w
    bar_table   = Table(
        [["", ""]],
        colWidths=[filled_w, empty_w],
        rowHeights=[12],
    )
    bar_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), result_color),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E8EAED")),
        ("LINEABOVE",  (0, 0), (-1, 0), 0, colors.white),
    ]))
    story.append(bar_table)
    story.append(Spacer(1, 0.6 * cm))

    # ── Clinical note ──────────────────────────────────────────────────────
    if scan.prediction == "PNEUMONIA":
        note = (
            "The AI model detected patterns consistent with <b>pneumonia</b> in the "
            "uploaded chest X-ray. This is an AI-assisted finding and must be reviewed "
            "by a qualified radiologist or physician before any clinical decision is made."
        )
    else:
        note = (
            "The AI model found <b>no significant pneumonia-like patterns</b> in the "
            "uploaded chest X-ray. This does not constitute a medical clearance. "
            "Please consult a physician if you have clinical symptoms."
        )
    story.append(Paragraph("Clinical Note", styles["section_heading"]))
    story.append(Paragraph(note, styles["body"]))
    story.append(Spacer(1, 0.6 * cm))

    # ── Images side-by-side ────────────────────────────────────────────────
    static_dir = os.path.join(current_app.root_path, "..", "static")
    orig_path  = os.path.join(static_dir, scan.image_path)
    heat_path  = os.path.join(static_dir, scan.heatmap_path) if scan.heatmap_path else None

    img_w = (PAGE_W - 2 * MARGIN - 1 * cm) / 2  # two columns with 1cm gap

    image_row = []
    for path, caption in [(orig_path, "Original X-Ray"), (heat_path, "Grad-CAM Heatmap")]:
        if path and os.path.exists(path):
            img = RLImage(path, width=img_w, height=img_w * 0.85)
            cap = Paragraph(caption, styles["caption"])
            image_row.append([img, cap])
        else:
            image_row.append([Paragraph(f"<i>{caption} not available</i>", styles["body"]), ""])

    if image_row:
        story.append(Paragraph("Imaging", styles["section_heading"]))
        story.append(Spacer(1, 0.2 * cm))
        img_table = Table(
            [[image_row[0][0], image_row[1][0]],
             [image_row[0][1], image_row[1][1]]],
            colWidths=[img_w, img_w],
            hAlign="LEFT",
        )
        img_table.setStyle(TableStyle([
            ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(img_table)

    story.append(Spacer(1, 0.8 * cm))

    # ── Disclaimer ─────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_GREY))
    story.append(Spacer(1, 0.2 * cm))
    disclaimer = (
        "<b>Disclaimer:</b> SmartX-Ray is a computer-aided detection tool intended to "
        "assist trained medical professionals. It is NOT a substitute for professional "
        "medical advice, diagnosis, or treatment. Always seek the guidance of a qualified "
        "health provider with any questions you may have regarding a medical condition."
    )
    story.append(Paragraph(disclaimer, styles["disclaimer"]))

    doc.build(story)

    file_size = os.path.getsize(filepath)
    logger.info("PDF report generated: %s (%d bytes)", filepath, file_size)
    return filename, file_size


# ── Style helpers ──────────────────────────────────────────────────────────

def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=base["Title"],
            fontSize=22, textColor=BRAND_BLUE, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontSize=11, textColor=BRAND_GREY, spaceAfter=8,
        ),
        "section_heading": ParagraphStyle(
            "section_heading", parent=base["Heading2"],
            fontSize=12, textColor=BRAND_BLUE, spaceBefore=6, spaceAfter=4,
        ),
        "center": ParagraphStyle(
            "center", parent=base["Normal"],
            alignment=TA_CENTER, fontSize=11,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=10, leading=14,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"],
            fontSize=8, textColor=BRAND_GREY, alignment=TA_CENTER,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer", parent=base["Normal"],
            fontSize=8, textColor=BRAND_GREY, leading=11,
        ),
    }
