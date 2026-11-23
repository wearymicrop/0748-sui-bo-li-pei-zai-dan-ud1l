from collections import defaultdict

from app.modules.m1_weighing.mass import grams
from app.modules.m2_moisture.ratio import ppm
from app.quality import issue, rows, token


def water_samples(data, lots):
    buckets, isolated, duplicates = defaultdict(list), [], []
    for row, raw in rows(data, "moisture"):
        try:
            lot, sample, position = (
                token(raw[key]) for key in ("lot", "sample", "position")
            )
            mass = grams(raw["mass"], raw["mass_unit"])
            value = ppm(raw["water"], raw["unit"], 300000)
            if (
                lot not in lots
                or position not in ("上层", "中层", "下层")
                or not 0 < mass <= 30000
            ):
                raise ValueError
            buckets[lot, sample].append((row, raw, position, mass, value))
        except (KeyError, TypeError, ValueError):
            isolated.append(issue("BAD_MOISTURE", row, raw))
    valid = defaultdict(list)
    for (lot, sample), items in buckets.items():
        first, *rest = items
        if any(item[2:] != first[2:] for item in rest):
            isolated.extend(
                issue("MOISTURE_CONFLICT", item[0], item[1]) for item in items
            )
            continue
        row, _, position, mass, value = first
        valid[lot].append(
            {
                "sample": sample,
                "row": row,
                "position": position,
                "mass_g": mass,
                "water_ppm": value,
            }
        )
        duplicates.extend(
            issue("DUPLICATE_MOISTURE", item[0], item[1], kept=row) for item in rest
        )
    result = {}
    for lot in lots:
        specimens = valid[lot]
        positions = sorted({item["position"] for item in specimens})
        enough = {"上层", "下层"}.issubset(positions)
        total = sum(item["mass_g"] for item in specimens)
        numerator = sum(item["mass_g"] * item["water_ppm"] for item in specimens)
        result[lot] = {
            "samples": specimens,
            "positions": positions,
            "mass_g": total,
            "weighted_ppm_g": numerator,
            "code": None if enough else "MISSING_MOISTURE",
        }
    return {"lots": result, "isolated": isolated, "duplicates": duplicates}
