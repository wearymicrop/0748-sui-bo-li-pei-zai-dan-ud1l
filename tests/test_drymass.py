from app.modules.m4_drymass.fold import split_wet_mass
from app.pipeline import calculate


def test_integer_grams_of_first_lot(clean_result):
    lot = clean_result["drymass"]["lots"]["L01"]
    assert (lot["wet_g"], lot["dry_g"], lot["water_g"]) == (990000, 920700, 69300)


def test_half_gram_rounding_assigned_to_water():
    assert split_wet_mass(5, 100000, 1) == (4, 1)


def test_fraction_precision_carried_to_final_gram():
    # TRAP-10
    assert split_wet_mass(10000000, 1000001, 3) == (6666663, 3333337)


def test_incomplete_samples_excluded_from_effective_wet(dirty_result):
    result = dirty_result["drymass"]
    assert result["pending_wet_g"] == 1080000 and result["effective_wet_g"] == 6930000
    assert result["lots"]["L07"]["dry_g"] is None


def test_idempotent_fold_on_same_lot_under_unit_conversion(clean, clean_result):
    clean["moisture"][0].update(
        mass="0.1", mass_unit="kg", unit="fraction", water="0.04"
    )
    assert calculate(clean)["drymass"] == clean_result["drymass"]


def test_zero_water_valid_dry_mass(clean):
    for row in clean["moisture"][:2]:
        row["water"] = 0
    assert calculate(clean)["drymass"]["lots"]["L01"]["dry_g"] == 990000
