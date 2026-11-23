from app.quality import number

MULTIPLIERS = {"%": 10000, "fraction": 1000000, "ppm": 1}


def ppm(value, unit, upper=1000000):
    converted = number(value) * MULTIPLIERS[unit]
    if not 0 <= converted <= upper or converted != converted.to_integral_value():
        raise ValueError("比例超出范围或精度")
    return int(converted)
