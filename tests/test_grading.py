from app.modules.m3_grading.classes import grade_for
from app.pipeline import calculate


def test_aliases_normalize_transparent_to_white(clean_result):
    # TRAP-22
    grade = clean_result["grading"]["lots"]["L03"]
    assert grade["color"] == "白料" and grade["grade"] == "B"


def test_worst_case_impurity_across_valid_samples(dirty_result):
    # TRAP-19
    grade = dirty_result["grading"]["lots"]["L04"]
    assert grade["impurity_ppm"] == 7500 and [
        row["row"] for row in grade["samples"]
    ] == [4, 8]


def test_lot_missing_grade_marked(dirty_result):
    assert dirty_result["grading"]["lots"]["L08"] == {
        "code": "MISSING_GRADE",
        "samples": [],
    }


def test_different_base_colors_do_not_average(clean):
    clean["grades"].append(dict(clean["grades"][0], color="绿料"))
    assert calculate(clean)["grading"]["lots"]["L01"]["code"] == "GRADE_CONFLICT"


def test_exact_grade_threshold_not_penalized():
    assert grade_for(30000, 10000) == "A" and grade_for(30001, 10000) == "B"
    assert grade_for(100000, 30000) == "B" and grade_for(100001, 30000) == "C"


def test_grading_shares_cannot_exceed_full_sample(clean):
    clean["grades"][0].update(offcolor="85", impurity="20")
    result = calculate(clean)["grading"]
    assert (
        result["isolated"][0]["code"] == "BAD_GRADE_SAMPLE"
        and result["lots"]["L01"]["code"] == "MISSING_GRADE"
    )
