import pytest
from app.modules.m1_weighing.mass import grams
from app.modules.m1_weighing.service import weigh


def test_clean_tickets_and_wet_total(clean_result):
    result = clean_result["weighing"]
    assert (
        len(result["accepted"]) == 24
        and sum(row["wet_g"] for row in result["accepted"]) == 8340000
    )


def test_negative_net_has_source_row(dirty_result):
    item = next(
        row
        for row in dirty_result["weighing"]["isolated"]
        if row["code"] == "NEGATIVE_NET"
    )
    assert item["row"] == 25 and item["raw"]["gross"] == 201


def test_cross_unit_duplicate_is_ignored(dirty_result):
    assert dirty_result["weighing"]["duplicates"][0]["kept"] == 1
    assert dirty_result["weighing"]["lots"]["L01"]["ticket_rows"] == [1, 2, 3]


def test_conflicting_ticket_rejects_both_not_just_later(dirty_result):
    # TRAP-14
    rows = [
        row["row"]
        for row in dirty_result["weighing"]["isolated"]
        if row["code"] == "TICKET_CONFLICT"
    ]
    assert (
        rows == [4, 27] and dirty_result["weighing"]["lots"]["L02"]["wet_g"] == 675000
    )


def test_thousands_and_subgram():
    # TRAP-06
    assert grams("１,２３４.５", "kg") == 1234500
    with pytest.raises(ValueError):
        grams("1.001", "g")


def test_zero_net_isolated_and_identifier_kept(clean):
    # TRAP-08
    clean["tickets"][0]["gross"] = clean["tickets"][0]["tare"]
    result = weigh(clean)
    assert (
        result["isolated"][0]["code"] == "NEGATIVE_NET"
        and result["accepted"][0]["ticket"] == "01002"
    )
