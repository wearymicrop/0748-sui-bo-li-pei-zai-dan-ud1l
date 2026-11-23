from app.quality import number

UNITS = {"g": 1, "kg": 1000, "t": 1000000}


def grams(value, unit):
    parsed = number(value) * UNITS[unit]
    if not 0 <= parsed <= 100_000_000 or parsed != parsed.to_integral_value():
        raise ValueError("重量须以整克计")
    return int(parsed)
