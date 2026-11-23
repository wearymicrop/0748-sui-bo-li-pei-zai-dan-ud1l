from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def yuan(value):
    """金额统一为两位小数，四舍五入（半值向上）。"""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def money(grams, price_per_kg):
    """整克质量乘以每千克单价，折为元。"""
    amount = Decimal(grams) * Decimal(price_per_kg) / Decimal(1000)
    return yuan(amount)


def display(amount):
    """输出为 JSON 友好的字符串，保留两位小数。"""
    return format(amount, ".2f")
