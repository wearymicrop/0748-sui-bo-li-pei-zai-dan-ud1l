def round_half_up(numerator, denominator):
    floor, remainder = divmod(numerator, denominator)
    return floor + (remainder * 2 >= denominator)


def split_wet_mass(wet, numerator, sample_mass):
    water = round_half_up(wet * numerator, sample_mass * 1_000_000)
    return wet - water, water
