from app.pipeline import calculate


def test_weighted_representative_sample_not_mean(clean_result):
    result = clean_result["moisture"]["lots"]["L01"]
    assert result["weighted_ppm_g"] == 28000000 and result["mass_g"] == 400
    assert result["weighted_ppm_g"] // result["mass_g"] == 70000


def test_mixed_unit_converted_same_ratio(dirty_result):
    # TRAP-15
    lots = dirty_result["moisture"]["lots"]
    assert (
        lots["L01"]["samples"][1]["water_ppm"]
        == lots["L05"]["samples"][1]["water_ppm"]
        == 80000
    )


def test_missing_position_is_not_zero(dirty_result):
    # TRAP-07
    sample = dirty_result["moisture"]["lots"]["L07"]
    assert sample["positions"] == ["上层"] and sample["code"] == "MISSING_MOISTURE"


def test_identical_sample_does_not_add_weight(clean):
    clean["moisture"].append(dict(clean["moisture"][0], water="40000", unit="ppm"))
    result = calculate(clean)["moisture"]
    assert (
        result["duplicates"][0]["code"] == "DUPLICATE_MOISTURE"
        and result["lots"]["L01"]["mass_g"] == 400
    )


def test_changed_same_id_quarantines_both(clean):
    clean["moisture"].append(dict(clean["moisture"][0], water="6"))
    result = calculate(clean)["moisture"]
    assert [row["code"] for row in result["isolated"]] == ["MOISTURE_CONFLICT"] * 2
    assert result["lots"]["L01"]["code"] == "MISSING_MOISTURE"


def test_unit_must_be_explicit_and_known(clean):
    clean["moisture"][0]["unit"] = "未知"
    result = calculate(clean)["moisture"]
    assert result["isolated"][0]["code"] == "BAD_MOISTURE"
