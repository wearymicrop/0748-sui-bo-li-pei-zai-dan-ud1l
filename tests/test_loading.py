from app.pipeline import calculate


def test_budget_limits_exact_last_gram(dirty_result):
    # TRAP-24
    target = dirty_result["loading"]["targets"][0]
    assert (target["loaded_g"], target["short_g"], target["code"]) == (
        2419914,
        180086,
        "IMPURITY_LIMIT",
    )
    limit = target["max_impurity_ppm"]
    last = target["sections"][-1]
    assert target["impurity_ppm_g"] <= target["loaded_g"] * limit
    assert (
        target["impurity_ppm_g"] + last["impurity_ppm"]
        > (target["loaded_g"] + 1) * limit
    )


def test_one_lot_contiguous_across_vehicles(dirty_result):
    # TRAP-23
    targets = dirty_result["loading"]["targets"]
    part = targets[0]["sections"][-1]
    later = targets[2]["sections"][0]
    assert (
        part["lot"] == later["lot"] == "L03"
        and part["end_g"] == later["start_g"] == 871464
    )
    assert later["end_g"] == 948600


def test_missing_grade_stock_held_out(dirty_result):
    loading = dirty_result["loading"]
    assert loading["remaining"]["L08"]["remaining_g"] == 1018350
    assert not any(
        row["lot"] == "L08"
        for target in loading["targets"]
        for row in target["sections"]
    )


def test_invalid_target_grade_isolated(clean):
    clean["targets"][0]["grades"] = ["X"]
    loading = calculate(clean)["loading"]
    assert (
        len(loading["targets"]) == 2 and loading["isolated"][0]["code"] == "BAD_TARGET"
    )


def test_duplicate_load_target_does_not_consume_material(clean):
    clean["targets"].append(dict(clean["targets"][0], mass=200))
    loading = calculate(clean)["loading"]
    assert (
        loading["loaded_g"] == 1600000
        and [row["code"] for row in loading["isolated"]] == ["TARGET_CONFLICT"] * 2
    )


def test_priority_precedes_source_order(clean):
    clean["targets"].reverse()
    assert [r["priority"] for r in calculate(clean)["loading"]["targets"]] == [1, 2, 3]
