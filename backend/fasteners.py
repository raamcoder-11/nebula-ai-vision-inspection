"""
Deterministic database lookup -- not AI. Matches a measured diameter
against common ISO metric coarse-thread fastener sizes.
Extend this table if you demonstrate imperial or fine-thread fasteners.
"""

# (nominal_mm, coarse_pitch_mm, typical_hex_head_across_flats_mm)
ISO_METRIC_COARSE = [
    (3, 0.50, 5.5),
    (4, 0.70, 7.0),
    (5, 0.80, 8.0),
    (6, 1.00, 10.0),
    (8, 1.25, 13.0),
    (10, 1.50, 17.0),
    (12, 1.75, 19.0),
    (16, 2.00, 24.0),
    (20, 2.50, 30.0),
]


def match_fastener(measured_diameter_mm):
    if measured_diameter_mm is None:
        return None
    nominal, pitch, head_af = min(
        ISO_METRIC_COARSE, key=lambda row: abs(row[0] - measured_diameter_mm)
    )
    error_mm = round(abs(nominal - measured_diameter_mm), 2)
    return {
        "standard": "ISO metric (coarse thread)",
        "nominal_size": f"M{nominal}",
        "thread_pitch_mm": pitch,
        "typical_head_af_mm": head_af,
        "measured_vs_nominal_error_mm": error_mm,
        "match_confidence": "high" if error_mm < 0.4 else "low - verify manually",
    }
