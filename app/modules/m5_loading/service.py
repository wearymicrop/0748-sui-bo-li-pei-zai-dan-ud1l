from app.modules.m5_loading.allocator import allocate
from app.modules.m5_loading.targets import target_list
from app.quality import rows


def load(data, drymass, grading):
    targets, isolated = target_list(rows(data, "targets"))
    stock = {
        lot: row for lot, row in drymass["lots"].items() if row["dry_g"] is not None
    }
    consumed = dict.fromkeys(stock, 0)
    results = [allocate(target, grading["lots"], stock, consumed) for target in targets]
    remaining = {
        lot: {
            "lot": lot,
            "start_g": consumed[lot],
            "end_g": row["dry_g"],
            "remaining_g": row["dry_g"] - consumed[lot],
            "code": grading["lots"][lot]["code"],
        }
        for lot, row in stock.items()
    }
    return {
        "targets": results,
        "remaining": remaining,
        "isolated": isolated,
        "loaded_g": sum(target["loaded_g"] for target in results),
        "short_g": sum(target["short_g"] for target in results),
    }
