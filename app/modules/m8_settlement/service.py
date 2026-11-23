from app.manifest import digest
from app.modules.m8_settlement.money import Decimal, display, money, yuan
from app.modules.m8_settlement.pricing import contract
from app.reasons import LABELS

BLOCKING_WEIGHING = {"BAD_TICKET", "NEGATIVE_NET", "TICKET_CONFLICT"}


def _reserve(rate, gross):
    """暂估风险暂扣：按暂扣比例对暂估毛额取整。"""
    return yuan(Decimal(gross) * Decimal(rate))


def _line(lot, weighing, moisture, grading, drymass, terms):
    wet_row = drymass["lots"][lot]
    grade = grading["lots"][lot]
    water = moisture["lots"][lot]
    wet_g = wet_row["wet_g"]
    dry_g = wet_row["dry_g"]
    line = {
        "lot": lot,
        "ticket_rows": wet_row["ticket_rows"],
        "wet_g": wet_g,
        "dry_g": dry_g,
        "water_g": wet_row["water_g"],
        "grade": grade.get("grade"),
        "color": grade.get("color"),
        "impurity_ppm": grade.get("impurity_ppm"),
        "offcolor_ppm": grade.get("offcolor_ppm"),
        "basis": None,
        "unit_price": None,
        "gross_amount": None,
        "quality_deduction": None,
        "provisional_reserve": None,
        "provisional_amount": None,
        "payable_amount": None,
        "withheld_amount": None,
        "status": None,
        "reasons": [],
    }
    floor = terms["wet_floor_price"]
    rate = terms["provisional_reserve_rate"]

    if dry_g is None:
        # 含水证据未齐：只能按湿重暂估，干重口径缺证暂扣
        line["status"] = "PROVISIONAL"
        line["basis"] = "wet"
        line["unit_price"] = floor
        gross = money(wet_g, floor)
        reserve = _reserve(rate, gross)
        line.update(
            gross_amount=display(gross),
            quality_deduction=display(Decimal("0.00")),
            provisional_reserve=display(reserve),
            provisional_amount=display(gross - reserve),
            payable_amount=display(Decimal("0.00")),
            withheld_amount=display(gross),
        )
        code = water["code"] or "BAD_MOISTURE"
        line["reasons"].append({"code": code, "message": LABELS.get(code, "含水证据未齐")})
        return line

    if grade["code"] is not None:
        # 含水已齐但分级缺证或冲突：按干重套湿料暂估价，质量风险暂扣
        line["status"] = "PROVISIONAL"
        line["basis"] = "dry"
        line["unit_price"] = floor
        gross = money(dry_g, floor)
        reserve = _reserve(rate, gross)
        line.update(
            gross_amount=display(gross),
            quality_deduction=display(Decimal("0.00")),
            provisional_reserve=display(reserve),
            provisional_amount=display(gross - reserve),
            payable_amount=display(Decimal("0.00")),
            withheld_amount=display(gross),
        )
        code = grade["code"]
        line["reasons"].append({"code": code, "message": LABELS.get(code, "分级证据未齐")})
        return line

    # 三证齐全：干重 × 色级单价，分级测值驱动质量扣减
    price = terms["grade_prices"][grade["grade"]]
    gross = money(dry_g, price)
    # 质量扣减随分级测值（异色 + 杂质 ppm）重算，分级一变即重算
    penalty_ppm = grade["offcolor_ppm"] + grade["impurity_ppm"]
    deduction = yuan(
        Decimal(gross) * Decimal(penalty_ppm) / Decimal(1_000_000)
    )
    payable = yuan(gross - deduction)
    line.update(
        status="READY",
        basis="dry",
        unit_price=price,
        gross_amount=display(gross),
        quality_deduction=display(deduction),
        provisional_reserve=display(Decimal("0.00")),
        provisional_amount=display(Decimal("0.00")),
        payable_amount=display(payable),
        withheld_amount=display(Decimal("0.00")),
    )
    return line


def _blocked_line(lot, wet_g, ticket_rows, issue):
    return {
        "lot": lot,
        "ticket_rows": ticket_rows,
        "wet_g": wet_g,
        "dry_g": None,
        "water_g": None,
        "grade": None,
        "color": None,
        "impurity_ppm": None,
        "offcolor_ppm": None,
        "basis": None,
        "unit_price": None,
        "gross_amount": None,
        "quality_deduction": None,
        "provisional_reserve": None,
        "provisional_amount": None,
        "payable_amount": display(Decimal("0.00")),
        "withheld_amount": None,
        "status": "BLOCKED",
        "reasons": [{"code": issue["code"], "message": issue["message"], "row": issue["row"]}],
    }


def settle(result, data):
    """依据已齐证据生成批次结算单（纯函数，不落库）。"""
    terms = contract(data)
    if terms is None:
        return {
            "batch": result["weighing"]["batch"],
            "contract": None,
            "status": "NO_CONTRACT",
            "lines": [],
            "blockers": [],
            "totals": _empty_totals(None),
            "evidence": _evidence_summary(result),
        }

    weighing = result["weighing"]
    blocked_lots = {}
    for item in weighing["isolated"]:
        if item["code"] in BLOCKING_WEIGHING:
            raw = item.get("raw") or {}
            lot = raw.get("lot") if isinstance(raw, dict) else None
            blocked_lots.setdefault(lot, item)

    lines, blockers = [], []
    for lot, row in sorted(weighing["lots"].items()):
        if lot in blocked_lots:
            issue = blocked_lots[lot]
            lines.append(_blocked_line(lot, row["wet_g"], row["ticket_rows"], issue))
            blockers.append(
                {
                    "lot": lot,
                    "code": issue["code"],
                    "message": issue["message"],
                    "row": issue["row"],
                }
            )
            continue
        lines.append(
            _line(
                lot,
                weighing,
                result["moisture"],
                result["grading"],
                result["drymass"],
                terms,
            )
        )
    # 全部磅单都被隔离、未形成采信批料的冲突来源也要显式阻断，不得静默消失
    for lot, issue in blocked_lots.items():
        if lot is not None and lot in weighing["lots"]:
            continue
        blockers.append(
            {
                "lot": lot or "未识别批料",
                "code": issue["code"],
                "message": issue["message"],
                "row": issue["row"],
            }
        )

    totals = _summarize(lines, terms["currency"])
    status = (
        "BLOCKED"
        if blockers
        else "PROVISIONAL"
        if any(line["status"] == "PROVISIONAL" for line in lines)
        else "READY"
    )
    document = {
        "batch": weighing["batch"],
        "contract": terms,
        "status": status,
        "lines": lines,
        "blockers": blockers,
        "totals": totals,
        "evidence": _evidence_summary(result),
    }
    document["digest"] = digest(
        {key: value for key, value in document.items() if key != "digest"}
    )
    return document


def _evidence_summary(result):
    grading = result["grading"]
    moisture = result["moisture"]
    return {
        "ticket_issues": len(result["weighing"]["isolated"]),
        "moisture_issues": len(moisture["isolated"]),
        "grade_issues": len(grading["isolated"]),
        "pending_moisture_lots": sorted(
            lot for lot, row in moisture["lots"].items() if row["code"] is not None
        ),
        "ungraded_lots": sorted(
            lot for lot, row in grading["lots"].items() if row["code"] is not None
        ),
        "accepted_wet_g": result["reconcile"]["accepted_wet_g"],
        "dry_g": result["reconcile"]["dry_g"],
        "pending_wet_g": result["reconcile"]["pending_wet_g"],
    }


def _empty_totals(currency):
    zero = display(Decimal("0.00"))
    return {
        "currency": currency,
        "lot_count": 0,
        "ready_lots": 0,
        "provisional_lots": 0,
        "blocked_lots": 0,
        "blocked_wet_g": 0,
        "payable_amount": zero,
        "provisional_amount": zero,
        "withheld_amount": zero,
        "quality_deduction": zero,
    }


def _summarize(lines, currency):
    def total(key):
        return display(sum((Decimal(line[key]) for line in lines if line[key]), Decimal()))

    return {
        "currency": currency,
        "lot_count": len(lines),
        "ready_lots": sum(line["status"] == "READY" for line in lines),
        "provisional_lots": sum(line["status"] == "PROVISIONAL" for line in lines),
        "blocked_lots": sum(line["status"] == "BLOCKED" for line in lines),
        "blocked_wet_g": sum(
            line["wet_g"] for line in lines if line["status"] == "BLOCKED"
        ),
        "payable_amount": total("payable_amount"),
        "provisional_amount": total("provisional_amount"),
        "withheld_amount": total("withheld_amount"),
        "quality_deduction": total("quality_deduction"),
    }
