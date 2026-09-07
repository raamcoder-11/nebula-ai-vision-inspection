"""Deterministic 2-D calibration with a 150 mm ruler as the reference."""
from __future__ import annotations
import cv2
import numpy as np

RULER_LENGTH_MM = 150.0
MIN_RULER_ASPECT_RATIO = 4.0
MAX_RULER_ASPECT_RATIO = 16.0

def _edges(gray):
    equalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.dilate(cv2.Canny(cv2.GaussianBlur(equalized, (5, 5), 0), 45, 130), np.ones((3, 3), np.uint8), iterations=1)

def _external_contours(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    contours, _ = cv2.findContours(_edges(gray), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return sorted(contours, key=cv2.contourArea, reverse=True)

def find_reference_card(image_bgr):
    """Locate an edge-to-edge 150 mm ruler and return its long-edge scale.

    The ruler's visible *outer end-to-end length* must actually be 150 mm.
    Do not use a longer ruler that merely has a 15 cm marking on it.
    """
    image_area = image_bgr.shape[0] * image_bgr.shape[1]
    best = None
    for contour in _external_contours(image_bgr)[:30]:
        area = cv2.contourArea(contour)
        if not 0.008 * image_area <= area <= 0.55 * image_area:
            continue
        rect = cv2.minAreaRect(contour)
        width_px, height_px = rect[1]
        if width_px < 1 or height_px < 1:
            continue
        long_px, short_px = max(width_px, height_px), min(width_px, height_px)
        aspect_ratio = long_px / short_px
        fill_ratio = area / (width_px * height_px)
        if not MIN_RULER_ASPECT_RATIO <= aspect_ratio <= MAX_RULER_ASPECT_RATIO or fill_ratio < 0.70:
            continue
        score = min(fill_ratio, 1.0) * min(1.0, aspect_ratio / MIN_RULER_ASPECT_RATIO)
        if best is None or score > best[0]:
            best = (score, rect, long_px, fill_ratio)
    if best is None:
        return None, None, 0.0
    _, rect, long_px, fill_ratio = best
    confidence = round(max(0.0, min(1.0, fill_ratio)), 2)
    return RULER_LENGTH_MM / long_px, cv2.boxPoints(rect), confidence

def _overlaps_card(box, card_box):
    if card_box is None:
        return False
    center = tuple(np.mean(box, axis=0))
    if cv2.pointPolygonTest(card_box.astype(np.float32), center, False) >= 0:
        return True
    overlap, _ = cv2.intersectConvexConvex(box.astype(np.float32), card_box.astype(np.float32))
    return overlap > 0.15 * cv2.contourArea(box.astype(np.float32))

def _find_holes(image_bgr, object_box, mm_per_pixel):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    contours, hierarchy = cv2.findContours(_edges(gray), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    holes = []
    for contour, links in zip(contours, hierarchy[0]):
        if links[3] == -1 or cv2.contourArea(contour) < 60:
            continue
        moments = cv2.moments(contour)
        if not moments["m00"]:
            continue
        center = (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])
        if cv2.pointPolygonTest(object_box.astype(np.float32), center, False) < 0:
            continue
        diameter = 2 * np.sqrt(cv2.contourArea(contour) / np.pi) * mm_per_pixel
        holes.append({"center": [round(center[0], 1), round(center[1], 1)], "diameter_mm": round(diameter, 2)})
    return holes[:8]

def measure_largest_object(image_bgr, mm_per_pixel, exclude_box=None):
    """Measure the largest plausible contour separate from the reference."""
    image_area = image_bgr.shape[0] * image_bgr.shape[1]
    for contour in _external_contours(image_bgr)[:35]:
        area = cv2.contourArea(contour)
        if not 0.002 * image_area <= area <= 0.65 * image_area:
            continue
        rect = cv2.minAreaRect(contour)
        width_px, height_px = rect[1]
        if width_px < 8 or height_px < 8:
            continue
        box = cv2.boxPoints(rect)
        if _overlaps_card(box, exclude_box):
            continue
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter else 0.0
        long_px, short_px = max(width_px, height_px), min(width_px, height_px)
        if long_px * mm_per_pixel < 2 or short_px * mm_per_pixel < 1:
            continue
        diameter_mm = None
        if circularity >= 0.78:
            (_, _), radius_px = cv2.minEnclosingCircle(contour)
            diameter_mm = round(2 * radius_px * mm_per_pixel, 2)
        holes = _find_holes(image_bgr, box, mm_per_pixel)
        hole_distance_mm = None if len(holes) < 2 else round(float(np.linalg.norm(np.array(holes[0]["center"]) - np.array(holes[1]["center"])) * mm_per_pixel), 2)
        return {"length_mm": round(long_px * mm_per_pixel, 2), "width_mm": round(short_px * mm_per_pixel, 2), "diameter_mm": diameter_mm, "circularity": round(float(circularity), 2), "holes": holes, "hole_to_hole_mm": hole_distance_mm, "box": np.round(box, 1).tolist()}
    return None

def annotate_image(image_bgr, card_box, measurement):
    """Draw reference, measured contour, and detected holes for the PDF."""
    annotated = image_bgr.copy()
    if card_box is not None:
        card = np.int32(card_box)
        cv2.polylines(annotated, [card], True, (255, 180, 0), 3)
        cv2.putText(annotated, "150 mm ruler reference", tuple(card[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 180, 0), 2)
    if measurement:
        box = np.int32(measurement["box"])
        cv2.polylines(annotated, [box], True, (0, 220, 0), 3)
        cv2.putText(annotated, f"L {measurement['length_mm']} mm | W {measurement['width_mm']} mm", tuple(box[np.argmin(box[:, 1])]), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 2)
        for hole in measurement.get("holes", []):
            center = tuple(np.int32(hole["center"]))
            cv2.circle(annotated, center, 8, (255, 0, 255), 2)
            cv2.putText(annotated, f"hole {hole['diameter_mm']} mm", center, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 1)
    return annotated
