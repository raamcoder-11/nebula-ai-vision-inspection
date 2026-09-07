"""Nebula Vision Inspection Flask application."""
import os
import uuid
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory
from calibration import annotate_image, find_reference_card, measure_largest_object
from identify import identify_component
from fasteners import match_fastener
from report import build_report

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR, UPLOAD_DIR = BASE_DIR.parent / "frontend", BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
LAST_RESULT = {}

@app.get("/")
def index(): return send_from_directory(FRONTEND_DIR, "index.html")
@app.get("/<path:filename>")
def static_files(filename): return send_from_directory(FRONTEND_DIR, filename)

def _number(name):
    try:
        value = float(request.form.get(name, ""))
        return value if value > 0 else None
    except (TypeError, ValueError): return None

def _reject(code, message, status, **details):
    LAST_RESULT.clear()
    return jsonify({"error": code, "message": message, "report_available": False, **details}), status

def _evaluate(measurement, spec):
    tolerance = spec["tolerance_mm"]
    targets = [(measurement["length_mm"], spec["length_nominal_mm"], "Length"), (measurement["width_mm"], spec["width_nominal_mm"], "Width")]
    supplied = [(actual, target, label) for actual, target, label in targets if target is not None]
    if tolerance is None or not supplied:
        return "REVIEW", ["No complete dimensional tolerance was supplied; automatic PASS is disabled."]
    failures = [f"{label} deviation {abs(actual - target):.2f} mm exceeds +/-{tolerance:.2f} mm" for actual, target, label in supplied if abs(actual - target) > tolerance]
    return ("FAIL", failures) if failures else ("PASS", ["Measured supplied dimensions are within configured tolerance."])

def _handle_image(image_bgr):
    spec = {"length_nominal_mm": _number("length_nominal_mm"), "width_nominal_mm": _number("width_nominal_mm"), "tolerance_mm": _number("tolerance_mm")}
    scale, card_box, calibration_confidence = find_reference_card(image_bgr)
    if scale is None: return _reject("reference_not_found", "No 150 mm ruler was detected. Keep the whole ruler flat and beside the part.", 422)
    if calibration_confidence < .55: return _reject("calibration_unreliable", "The ruler outline is too unclear for a trustworthy measurement. Photograph directly above it.", 422, calibration_confidence=calibration_confidence)
    measurement = measure_largest_object(image_bgr, scale, card_box)
    if measurement is None: return _reject("component_contour_not_found", "No separate measurable object was found beside the visiting card.", 422)
    ok, encoded = cv2.imencode(".jpg", image_bgr)
    if not ok: return _reject("encode_failed", "Could not prepare this image.", 500)
    ai = identify_component(encoded.tobytes())
    if ai.get("identification_error"):
        return _reject("verification_unavailable", "Component verification is unavailable. The inspection was not accepted.", 503, verification_hint=ai.get("verification_hint", "Check GEMINI_API_KEY and the laptop internet connection."))
    if not ai["is_mechanical_component"]:
        return _reject("unsupported_image", "Inspection rejected: the image is not clearly a supported mechanical component.", 422, reject_reason=ai["reject_reason"])
    verdict, reasons = _evaluate(measurement, spec)
    if ai["visible_defects"]: verdict, reasons = "FAIL", ["Visible defects were reported by AI verification."]
    image_path = UPLOAD_DIR / f"inspection_{uuid.uuid4().hex}.jpg"
    cv2.imwrite(str(image_path), annotate_image(image_bgr, card_box, measurement))
    result = {"timestamp": datetime.now().isoformat(timespec="seconds"), "inspection_status": "accepted", "report_available": True, "calibration_reference": "Ruler: 150.0 mm end-to-end", "calibration_confidence": calibration_confidence, "mm_per_pixel": round(scale, 5), "card_box": np.round(card_box, 1).tolist(), **measurement, **ai, "fastener": match_fastener(measurement["diameter_mm"]) if measurement["diameter_mm"] else None, "tolerance_spec": spec, "verdict": verdict, "verdict_reasons": reasons, "_image_path": str(image_path)}
    LAST_RESULT.clear(); LAST_RESULT.update(result)
    return jsonify({k:v for k,v in result.items() if not k.startswith("_")})

@app.post("/api/inspect")
def inspect_photo():
    image = request.files.get("image")
    if image is None or not image.filename: return _reject("no_image", "Choose or capture an image first.", 400)
    image_bgr = cv2.imdecode(np.frombuffer(image.read(), np.uint8), cv2.IMREAD_COLOR)
    if image_bgr is None: return _reject("decode_failed", "The selected file is not a readable image.", 400)
    return _handle_image(image_bgr)

@app.post("/api/report")
def report():
    if not LAST_RESULT.get("report_available"):
        return jsonify({"error": "no_reportable_inspection", "message": "Run an accepted component inspection before downloading a PDF."}), 409
    pdf_path = UPLOAD_DIR / f"report_{uuid.uuid4().hex}.pdf"
    build_report(str(pdf_path), LAST_RESULT["_image_path"], LAST_RESULT)
    response = send_file(pdf_path, mimetype="application/pdf", as_attachment=True, download_name="nebula-inspection-report.pdf", conditional=False)
    response.headers["X-Content-Type-Options"], response.headers["Cache-Control"] = "nosniff", "no-store"
    return response

@app.errorhandler(413)
def too_large(_): return _reject("file_too_large", "The file is larger than the 30 MB limit.", 413)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
