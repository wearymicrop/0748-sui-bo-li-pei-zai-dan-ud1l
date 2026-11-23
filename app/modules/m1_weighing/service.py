from collections import defaultdict

from app.errors import BusinessError
from app.modules.m1_weighing.mass import grams
from app.quality import issue, rows, token


def weigh(data):
    try:
        batch = token(data.get("batch"))
    except ValueError as error:
        raise BusinessError("BAD_BATCH", "缺少接收批次") from error
    records = list(rows(data, "tickets"))
    keys, isolated, duplicates = defaultdict(list), [], []
    for row, raw in records:
        try:
            number, lot = token(raw["ticket"]), token(raw["lot"])
            gross, tare = (grams(raw[key], raw["unit"]) for key in ("gross", "tare"))
        except (KeyError, TypeError, ValueError):
            isolated.append(issue("BAD_TICKET", row, raw))
            continue
        keys[number].append(
            {
                "ticket": number,
                "lot": lot,
                "row": row,
                "gross_g": gross,
                "tare_g": tare,
                "raw": raw,
            }
        )
    accepted, lots = [], {}
    for bucket in keys.values():
        first, *rest = bucket
        key = first["lot"], first["gross_g"], first["tare_g"]
        if any((item["lot"], item["gross_g"], item["tare_g"]) != key for item in rest):
            isolated.extend(
                issue("TICKET_CONFLICT", item["row"], item["raw"]) for item in bucket
            )
            continue
        if first["gross_g"] <= first["tare_g"]:
            isolated.extend(
                issue("NEGATIVE_NET", item["row"], item["raw"]) for item in bucket
            )
            continue
        duplicates.extend(
            issue("DUPLICATE_TICKET", item["row"], item["raw"], kept=first["row"])
            for item in rest
        )
        lot = lots.setdefault(
            first["lot"], {"lot": first["lot"], "wet_g": 0, "ticket_rows": []}
        )
        wet = first["gross_g"] - first["tare_g"]
        lot["wet_g"] += wet
        lot["ticket_rows"].append(first["row"])
        accepted.append(dict(first, wet_g=wet))
    return {
        "batch": batch,
        "accepted": accepted,
        "lots": lots,
        "duplicates": duplicates,
        "isolated": isolated,
        "counts": {
            "input": len(records),
            "accepted": len(accepted),
            "isolated": len(isolated),
            "duplicate": len(duplicates),
        },
    }
