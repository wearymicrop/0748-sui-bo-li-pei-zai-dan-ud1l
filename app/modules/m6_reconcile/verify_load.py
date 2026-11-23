from collections import defaultdict


def verify_load(drymass, loading):
    segments = defaultdict(list)
    alerts = []
    for target in loading["targets"]:
        sections = target["sections"]
        mass = sum(x["dry_g"] for x in sections)
        burden = sum(x["dry_g"] * x["impurity_ppm"] for x in sections)
        if (
            mass != target["loaded_g"]
            or mass + target["short_g"] != target["target_g"]
            or target["short_g"] < 0
        ):
            alerts.append({"key": target["target"], "code": "TARGET_BALANCE"})
        if (
            burden != target["impurity_ppm_g"]
            or burden > mass * target["max_impurity_ppm"]
        ):
            alerts.append({"key": target["target"], "code": "IMPURITY_BALANCE"})
        for part in sections:
            if (
                part["color"] not in target["colors"]
                or part["grade"] not in target["grades"]
            ):
                alerts.append({"key": target["target"], "code": "TARGET_CLASS"})
            segments[part["lot"]].append(part)
    for lot in set(segments).union(loading["remaining"]):
        if drymass["lots"].get(lot, {}).get("dry_g") is None:
            alerts.append({"key": lot, "code": "UNKNOWN_DRY_LOT"})
    for lot, item in drymass["lots"].items():
        if item["dry_g"] is None:
            continue
        edge = 0
        for part in sorted(segments[lot], key=lambda row: row["start_g"]):
            if (
                part["start_g"] != edge
                or part["end_g"] - part["start_g"] != part["dry_g"]
                or part["dry_g"] <= 0
            ):
                alerts.append({"key": lot, "code": "ALLOCATION_GAP"})
            edge = part["end_g"]
        remainder = loading["remaining"].get(lot, {})
        if (
            not 0 <= edge <= item["dry_g"]
            or remainder.get("start_g") != edge
            or remainder.get("end_g") != item["dry_g"]
            or remainder.get("remaining_g") != item["dry_g"] - edge
        ):
            alerts.append({"key": lot, "code": "REMAINDER_MISMATCH"})
    return sorted(alerts, key=lambda item: (item["key"], item["code"]))
