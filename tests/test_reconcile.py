import pytest
from app.errors import BusinessError
from app.modules.m6_reconcile.service import reconcile
from app.modules.m7_archive.signoff import approval


def audit(result):
    return reconcile(result["weighing"], result["drymass"], result["loading"])


def test_dirty_inbound_dry_and_water_balance(dirty_result):
    data = audit(dirty_result)
    assert (
        data["accepted_wet_g"],
        data["pending_wet_g"],
        data["dry_g"],
        data["water_g"],
    ) == (8010000, 1080000, 6444900, 485100)
    assert data["wet_difference_g"] == data["received_difference_g"] == 0


def test_dirty_loading_balance(dirty_result):
    data = audit(dirty_result)
    assert (data["loaded_g"], data["remaining_g"], data["short_g"]) == (
        3797050,
        2647850,
        702950,
    ) and data["status"] == "MATCHED"


def test_discontinuous_ranges_detected_when_totals_same(dirty_result):
    span = dirty_result["loading"]["targets"][2]["sections"][0]
    span["start_g"] -= 1
    span["end_g"] -= 1
    assert {"key": "L03", "code": "ALLOCATION_GAP"} in audit(dirty_result)["alerts"]


def test_impurity_rechecks_segments(clean_result):
    clean_result["loading"]["targets"][0]["sections"][0]["impurity_ppm"] = 100000
    assert audit(clean_result)["alerts"][0]["code"] == "IMPURITY_BALANCE"


def test_remainder_is_per_lot_not_globally_nettable(clean_result):
    remain = clean_result["loading"]["remaining"]
    remain["L02"]["remaining_g"] += 1
    remain["L03"]["remaining_g"] -= 1
    result = audit(clean_result)
    assert result["dry_difference_g"] == 0 and result["status"] == "MISMATCH"


def test_signoff_follows_evidence(dirty_result, clean_result):
    assert (
        approval(dirty_result)["status"] == "REVIEW"
        and approval(clean_result)["status"] == "SIGNED"
    )
    dirty_result["reconcile"]["status"] = "MISMATCH"
    with pytest.raises(BusinessError, match="尚未对平"):
        approval(dirty_result)
