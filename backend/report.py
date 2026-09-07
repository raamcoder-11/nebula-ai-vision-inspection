"""
PDF inspection report. Mostly templating -- the low-difficulty stage.
"""
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_report(pdf_path, image_path, result: dict):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "Nebula KnowLab - AI Vision Inspection Report")
    y -= 10 * mm

    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    y -= 12 * mm

    try:
        c.drawImage(image_path, 20 * mm, y - 60 * mm, width=70 * mm, height=60 * mm,
                    preserveAspectRatio=True)
    except Exception:
        pass

    tx, ty = 100 * mm, y
    c.setFont("Helvetica-Bold", 11)
    c.drawString(tx, ty, f"Component: {result.get('component_type', 'unknown')}")
    ty -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(tx, ty, f"AI identification confidence: {result.get('identification_confidence', 0)}%")
    ty -= 6 * mm
    c.drawString(tx, ty, f"Calibration confidence (classical CV): "
                          f"{round(result.get('calibration_confidence', 0) * 100)}%")
    ty -= 10 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(tx, ty, "Measured dimensions - directly measured")
    ty -= 6 * mm
    c.setFont("Helvetica", 9)
    any_measurement = False
    for label in ("length_mm", "width_mm", "diameter_mm"):
        val = result.get(label)
        if val is not None:
            c.drawString(tx, ty, f"{label.replace('_', ' ')}: {val} mm")
            ty -= 5 * mm
            any_measurement = True
    if not any_measurement:
        c.drawString(tx, ty, "insufficient data")
        ty -= 5 * mm

    y -= 65 * mm

    if result.get("fastener"):
        f = result["fastener"]
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y, "Fastener match - standards database (matched, not measured)")
        y -= 6 * mm
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, y,
                     f"Standard: {f['standard']}   Nominal: {f['nominal_size']}   "
                     f"Pitch: {f['thread_pitch_mm']} mm   Confidence: {f['match_confidence']}")
        y -= 10 * mm

    defects = result.get("visible_defects") or []
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Defect check - AI-estimated, not ground truth")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    if defects:
        for d in defects:
            c.drawString(20 * mm, y, f"- {d}")
            y -= 5 * mm
    else:
        c.drawString(20 * mm, y, "No defects flagged")
        y -= 5 * mm
    c.drawString(20 * mm, y, f"Defect confidence: {result.get('defect_confidence', 0)}%")
    y -= 12 * mm

    verdict = result.get("verdict", "REVIEW")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, f"Result: {verdict}")

    c.showPage()
    c.save()
    return pdf_path
