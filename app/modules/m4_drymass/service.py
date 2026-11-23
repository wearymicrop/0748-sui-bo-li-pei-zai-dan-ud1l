from app.modules.m4_drymass.fold import split_wet_mass


def fold(lots, moisture):
    result = {}
    for lot, item in lots.items():
        sample = moisture["lots"][lot]
        wet = item["wet_g"]
        code = sample["code"]
        dry, water = (
            (None, None)
            if code
            else split_wet_mass(wet, sample["weighted_ppm_g"], sample["mass_g"])
        )
        result[lot] = dict(
            item,
            dry_g=dry,
            water_g=water,
            code=code,
            sample_rows=[row["row"] for row in sample["samples"]],
        )
    return {
        "lots": result,
        "effective_wet_g": sum(
            row["wet_g"] for row in result.values() if row["code"] is None
        ),
        "pending_wet_g": sum(
            row["wet_g"] for row in result.values() if row["code"] is not None
        ),
        "dry_g": sum(row["dry_g"] or 0 for row in result.values()),
        "water_g": sum(row["water_g"] or 0 for row in result.values()),
    }
