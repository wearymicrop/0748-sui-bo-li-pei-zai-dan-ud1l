from collections import defaultdict

from app.modules.m1_weighing.mass import grams
from app.modules.m2_moisture.ratio import ppm
from app.modules.m3_grading.classes import GRADES, normalize_color
from app.quality import integer, issue, token


def target_list(records):
    buckets, isolated = defaultdict(list), []
    for row, raw in records:
        try:
            identifier = token(raw["target"])
            if not isinstance(raw["colors"], list) or not isinstance(
                raw["grades"], list
            ):
                raise ValueError
            colors = sorted({normalize_color(color) for color in raw["colors"]})
            grades = sorted({token(grade) for grade in raw["grades"]})
            mass = grams(raw["mass"], raw["unit"])
            limit = ppm(raw["max_impurity"], raw["impurity_unit"])
            if not mass or not colors or not grades or not set(grades).issubset(GRADES):
                raise ValueError
            priority = integer(raw["priority"], 1, 10000)
            buckets[identifier].append(
                (
                    row,
                    raw,
                    {
                        "target": identifier,
                        "row": row,
                        "colors": colors,
                        "grades": grades,
                        "target_g": mass,
                        "max_impurity_ppm": limit,
                        "priority": priority,
                    },
                )
            )
        except (KeyError, ValueError, TypeError):
            isolated.append(issue("BAD_TARGET", row, raw))
    valid = []
    for items in buckets.values():
        if len(items) != 1:
            isolated.extend(issue("TARGET_CONFLICT", row, raw) for row, raw, _ in items)
        else:
            valid.append(items[0][2])
    return sorted(valid, key=lambda item: (item["priority"], item["row"])), isolated
