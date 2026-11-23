from app.errors import BusinessError


def approval(result):
    balance = result["reconcile"]
    if balance["status"] != "MATCHED":
        raise BusinessError("UNBALANCED", "湿干双账尚未对平", 409)
    isolated = sum(
        len(result[key]["isolated"])
        for key in ("weighing", "moisture", "grading", "loading")
    )
    ungraded = sum(
        item["code"] is not None for item in result["grading"]["lots"].values()
    )
    hold = bool(
        isolated
        or ungraded
        or balance["pending_wet_g"]
        or balance["short_g"]
        or not result["loading"]["targets"]
    )
    return {
        "status": "REVIEW" if hold else "SIGNED",
        "isolated": isolated,
        "ungraded_lots": ungraded,
        "decision": "配载记录待复核" if hold else "配载记录已签单",
    }
