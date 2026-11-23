import copy

import pytest

from app.modules.m8_settlement.money import money, yuan
from app.modules.m8_settlement.service import settle
from app.pipeline import calculate


def settled(data):
    return settle(calculate(data), data)


def test_clean_batch_all_ready_and_payable(clean):
    doc = settled(clean)
    assert doc["status"] == "READY" and not doc["blockers"]
    assert doc["totals"]["ready_lots"] == 8
    assert doc["totals"]["provisional_lots"] == doc["totals"]["blocked_lots"] == 0
    assert doc["totals"]["withheld_amount"] == "0.00"
    assert doc["totals"]["payable_amount"] == "5976.74"


def test_money_half_up_to_cent():
    # 1 kg × 0.005 元/kg = 0.005 元，四舍五入到分应为 0.01
    assert money(1000, "0.005") == yuan("0.01")
    assert money(1000, "0.004") == yuan("0.00")


def test_ticket_conflict_blocks_whole_lot_from_payable(dirty):
    doc = settled(dirty)
    blocked = {line["lot"]: line for line in doc["lines"] if line["status"] == "BLOCKED"}
    assert set(blocked) == {"L02", "L03"}
    for line in blocked.values():
        # 冲突来源不得计价、不得进入应付
        assert line["payable_amount"] == "0.00"
        assert line["gross_amount"] is None and line["withheld_amount"] is None
    assert {b["code"] for b in doc["blockers"]} == {"TICKET_CONFLICT", "NEGATIVE_NET"}
    assert doc["totals"]["blocked_wet_g"] == 1695000
    assert doc["status"] == "BLOCKED"


def test_missing_moisture_is_wet_basis_provisional(dirty):
    line = next(line for line in settled(dirty)["lines"] if line["lot"] == "L07")
    assert line["status"] == "PROVISIONAL" and line["basis"] == "wet"
    # 湿重 1080kg × 暂估底价 0.42 = 453.60，暂扣 20% 后可看 362.88
    assert line["gross_amount"] == "453.60"
    assert line["provisional_reserve"] == "90.72"
    assert line["provisional_amount"] == "362.88"
    assert line["payable_amount"] == "0.00" and line["withheld_amount"] == "453.60"
    assert line["reasons"][0]["code"] == "MISSING_MOISTURE"


def test_missing_grade_keeps_dry_basis_but_holds_quality_risk(dirty):
    line = next(line for line in settled(dirty)["lines"] if line["lot"] == "L08")
    assert line["status"] == "PROVISIONAL" and line["basis"] == "dry"
    assert line["dry_g"] == 1018350 and line["grade"] is None
    assert line["gross_amount"] == "427.71"
    assert line["provisional_amount"] == "342.17"
    assert line["payable_amount"] == "0.00"
    assert line["reasons"][0]["code"] == "MISSING_GRADE"


def test_grade_conflict_holds_lot_not_payable(clean):
    clean["grades"].append(dict(clean["grades"][0], color="绿料"))
    line = next(line for line in settled(clean)["lines"] if line["lot"] == "L01")
    assert line["status"] == "PROVISIONAL"
    assert line["reasons"][0]["code"] == "GRADE_CONFLICT"
    assert line["payable_amount"] == "0.00"


def test_quality_deduction_recalculates_when_grade_evidence_changes(clean):
    before = next(line for line in settled(clean)["lines"] if line["lot"] == "L01")
    changed = copy.deepcopy(clean)
    for grade in changed["grades"]:
        if grade["lot"] == "L01":
            grade["impurity"] = "0.9"
    after = next(line for line in settled(changed)["lines"] if line["lot"] == "L01")
    assert after["grade"] == before["grade"] == "A"
    assert after["quality_deduction"] > before["quality_deduction"]
    assert after["payable_amount"] < before["payable_amount"]
    # 毛额不变，扣减增加恰好挤压应付
    assert after["gross_amount"] == before["gross_amount"]


def test_grade_downgrade_switches_unit_price(clean):
    changed = copy.deepcopy(clean)
    for grade in changed["grades"]:
        if grade["lot"] == "L01":
            grade["offcolor"] = "12"
    line = next(line for line in settled(changed)["lines"] if line["lot"] == "L01")
    assert line["grade"] == "C" and line["unit_price"] == "0.55"


def test_provisional_and_payable_never_overlap(dirty):
    totals = settled(dirty)["totals"]
    assert totals["payable_amount"] == "2969.44"
    assert totals["provisional_amount"] == "705.05"
    assert totals["withheld_amount"] == "881.31"


def test_fully_isolated_lot_still_blocks_batch(clean):
    # L01 的磅单全部做成净重无效：该批不进采信 lots，但冲突仍须阻断整单
    for ticket in clean["tickets"]:
        if ticket["lot"] == "L01":
            ticket["gross"] = ticket["tare"]
    doc = settled(clean)
    assert doc["status"] == "BLOCKED"
    assert any(b["lot"] == "L01" and b["code"] == "NEGATIVE_NET" for b in doc["blockers"])
    # 其余批料仍可正常结算，冲突来源不进应付
    assert "L01" not in {line["lot"] for line in doc["lines"]}


def test_missing_contract_returns_no_contract_status(clean):
    del clean["contract"]
    doc = settled(clean)
    assert doc["status"] == "NO_CONTRACT" and doc["lines"] == []


@pytest.mark.parametrize(
    "patch",
    [
        {"wet_floor_price": "-1"},
        {"provisional_reserve_rate": "1.5"},
        {"grade_prices": {"A": "0.88", "B": "0.72"}},
        {"grade_prices": {"A": "x", "B": "0.72", "C": "0.55"}},
        {"currency": ""},
    ],
)
def test_bad_contract_rejected(clean, patch):
    from app.errors import BusinessError

    clean["contract"].update(patch)
    with pytest.raises(BusinessError) as info:
        settled(clean)
    assert info.value.code == "BAD_CONTRACT"
