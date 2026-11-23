from app.modules.m6_reconcile.verify_load import verify_load


def reconcile(weighing, drymass, loading):
    received = sum(item["wet_g"] for item in weighing["accepted"])
    counts = weighing["counts"]
    remaining = sum(row["remaining_g"] for row in loading["remaining"].values())
    gaps = {
        "ticket_difference": counts["input"]
        - counts["accepted"]
        - counts["isolated"]
        - counts["duplicate"],
        "received_difference_g": received
        - drymass["effective_wet_g"]
        - drymass["pending_wet_g"],
        "wet_difference_g": drymass["effective_wet_g"]
        - drymass["water_g"]
        - drymass["dry_g"],
        "dry_difference_g": drymass["dry_g"] - loading["loaded_g"] - remaining,
    }
    alerts = verify_load(drymass, loading)
    return {
        "status": "MISMATCH" if alerts or any(gaps.values()) else "MATCHED",
        "alerts": alerts,
        **gaps,
        "accepted_wet_g": received,
        "effective_wet_g": drymass["effective_wet_g"],
        "pending_wet_g": drymass["pending_wet_g"],
        "water_g": drymass["water_g"],
        "dry_g": drymass["dry_g"],
        "loaded_g": loading["loaded_g"],
        "remaining_g": remaining,
        "short_g": loading["short_g"],
    }
