from collections import defaultdict

from app.modules.m2_moisture.ratio import ppm
from app.modules.m3_grading.classes import grade_for, normalize_color
from app.quality import issue, rows, token


def grade_lots(data, lots):
    samples, isolated = defaultdict(list), []
    for row, raw in rows(data, "grades"):
        try:
            lot = token(raw["lot"])
            if lot not in lots:
                raise ValueError
            color = normalize_color(raw["color"])
            offcolor = ppm(raw["offcolor"], raw["unit"])
            impurity = ppm(raw["impurity"], raw["unit"])
            if offcolor + impurity > 1000000:
                raise ValueError
            samples[lot].append(
                {
                    "row": row,
                    "color": color,
                    "offcolor_ppm": offcolor,
                    "impurity_ppm": impurity,
                }
            )
        except (KeyError, ValueError, TypeError):
            isolated.append(issue("BAD_GRADE_SAMPLE", row, raw))
    result = {}
    for lot in lots:
        evidence = samples[lot]
        colors = {item["color"] for item in evidence}
        if len(colors) != 1:
            result[lot] = {
                "code": "GRADE_CONFLICT" if colors else "MISSING_GRADE",
                "samples": evidence,
            }
            continue
        offcolor = max(item["offcolor_ppm"] for item in evidence)
        impurity = max(item["impurity_ppm"] for item in evidence)
        result[lot] = {
            "grade": grade_for(offcolor, impurity),
            "color": next(iter(colors)),
            "code": None,
            "samples": evidence,
            "offcolor_ppm": offcolor,
            "impurity_ppm": impurity,
        }
    return {"lots": result, "isolated": isolated}
